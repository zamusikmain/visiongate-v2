# Public link to VisionGate from this laptop via Cloudflare Quick Tunnel (free, no account), with a password.
# ASCII only on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI.
#   .\tunnel.ps1                         random password, login "samsung"
#   .\tunnel.ps1 -Password "MyPass123"   your own password (8+ chars)
# Needs cloudflared once:  winget install --id Cloudflare.cloudflared
# The link works while this window is open and the laptop is awake. Ctrl+C stops everything.
param([string]$Password = "", [string]$User = "samsung", [int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    $guess = "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe", "$env:ProgramFiles\cloudflared\cloudflared.exe"
    $found = $guess | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($found) { $cf = Get-Command $found }
}
if (-not $cf) {
    Write-Host "cloudflared is not installed. Install it once (no account needed):" -ForegroundColor Yellow
    Write-Host "    winget install --id Cloudflare.cloudflared"
    Write-Host "then open a NEW PowerShell window and run .\tunnel.ps1 again."
    exit 1
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Run .\run.ps1 once first (it creates .venv and installs dependencies)." -ForegroundColor Red
    exit 1
}
if (-not $Password) {
    $chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789".ToCharArray()
    $bytes = New-Object byte[] 12
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $Password = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}
if ($Password.Length -lt 8) { Write-Host "Password must be at least 8 characters." -ForegroundColor Red; exit 1 }

# Ollama (background screen-photo check). Not fatal.
function Start-Ollama {
    $ErrorActionPreference = "Continue"
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { Write-Warning "Docker Desktop is not running: screen-photo check unavailable"; return }
    $existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq "vg-ollama" }
    if ($existing) { docker start vg-ollama *> $null } else { docker compose up -d *> $null }
}
Start-Ollama

$logDir = Join-Path $env:TEMP "visiongate-tunnel"
New-Item -ItemType Directory -Force $logDir | Out-Null
$cfLog = Join-Path $logDir "cloudflared.log"
$appLog = Join-Path $logDir "app.log"
Remove-Item $cfLog, $appLog -ErrorAction SilentlyContinue

# 1. Web app with password, listening on 127.0.0.1 only (password passed via env, not command line)
$env:VG_PUBLIC_USER = $User
$env:VG_PUBLIC_PASSWORD = $Password
function Stop-App {
    # .venv\Scripts\python.exe is a launcher: the real server is its child, so stop by command line
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match "serve_public\.py" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

# Ready = OUR server answers: 401 with realm "VisionGate" (no password sent on purpose), so another
# program on the same port is not mistaken for the app.
# Direct request with no proxy: Invoke-WebRequest in 5.1 may send 127.0.0.1 to a corporate proxy.
function Test-AppReady([int]$p) {
    try {
        $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$p/api/health")
        $req.Proxy = $null
        $req.Timeout = 3000
        # New connection every time: with keep-alive .NET reuses the first socket, and if that one went
        # to another program on the same port (e.g. Docker on 0.0.0.0/::), our server is never seen.
        $req.KeepAlive = $false
        $req.ConnectionGroupName = [guid]::NewGuid().ToString()
        $req.GetResponse().Close()
        return $false  # 200 without a password: not our protected app
    } catch {
        $e = $_.Exception
        while ($e -and -not ($e -is [System.Net.WebException])) { $e = $e.InnerException }  # PS wraps it
        if (-not $e -or -not $e.Response) { return $false }  # connection refused / timeout: still starting
        $resp = $e.Response
        $ok = ([int]$resp.StatusCode -eq 401) -and ("$($resp.Headers['WWW-Authenticate'])" -match "VisionGate")
        $resp.Close()
        return $ok
    }
}

Stop-App  # leftovers of a previous run would hold the port
Start-Sleep -Milliseconds 500

# The port must be free on ALL addresses: Windows lets us bind 127.0.0.1:N even when another program
# (e.g. a Docker container) listens on 0.0.0.0:N / [::]:N, and then requests may reach that program.
function Test-PortBusy([int]$p) {
    return [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}
if (Test-PortBusy $Port) {
    $owner = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { (Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName } |
        Select-Object -Unique
    $free = ($Port + 1)..($Port + 50) | Where-Object { -not (Test-PortBusy $_) } | Select-Object -First 1
    if (-not $free) { Write-Host "Port $Port and the next 50 ports are busy. Use -Port <free port>." -ForegroundColor Red; exit 1 }
    Write-Host "Port $Port is already used by: $($owner -join ', '). Using port $free instead." -ForegroundColor Yellow
    $Port = $free
}

$app = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "tools\serve_public.py", "--port", "$Port" `
    -RedirectStandardOutput $appLog -RedirectStandardError "$appLog.err" -WindowStyle Hidden -PassThru
Remove-Item Env:\VG_PUBLIC_PASSWORD
$waitSec = 90  # first start loads OCR models; on a cold laptop this can take tens of seconds
$up = $false
Write-Host -NoNewline "Starting the app (up to $waitSec s) "
$sw = [System.Diagnostics.Stopwatch]::StartNew()
while (-not $up -and $sw.Elapsed.TotalSeconds -lt $waitSec) {
    if ($app.HasExited) { break }  # crashed: no point waiting
    if (Test-AppReady $Port) { $up = $true; break }
    Write-Host -NoNewline "."
    Start-Sleep -Seconds 2
}
Write-Host ""
if (-not $up) {
    $why = if ($app.HasExited) { "the app exited" } else { "no answer in $waitSec s" }
    Write-Host "The app did not start ($why). Last lines of $appLog.err :" -ForegroundColor Red
    if (Test-Path "$appLog.err") {
        $tail = Get-Content "$appLog.err" -Tail 15 -Encoding UTF8
        $tail
        if ($tail -match "10048|address already in use") {
            Write-Host "Port $Port is busy (another program or a running run.ps1). Close it or use: .\tunnel.ps1 -Port 8001" -ForegroundColor Yellow
        }
    }
    Stop-App
    exit 1
}
Write-Host ("App is ready in {0:N0} s." -f $sw.Elapsed.TotalSeconds)

# 2. Cloudflare Quick Tunnel -> random https://<words>.trycloudflare.com
$tunnel = Start-Process -FilePath $cf.Source -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:$Port" `
    -RedirectStandardError $cfLog -RedirectStandardOutput "$cfLog.out" -WindowStyle Hidden -PassThru
$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $cfLog) {
        $m = Select-String -Path $cfLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
        if ($m) { $url = $m.Matches[0].Value }
    }
}
try {
    if (-not $url) { throw "Tunnel did not start, see $cfLog" }
    Write-Host ""
    Write-Host "VisionGate is available at:" -ForegroundColor Green
    Write-Host "    $url"
    Write-Host "    login:    $User"
    Write-Host "    password: $Password"
    Write-Host ""
    Write-Host "Send the link and the password separately. Keep this window open; Ctrl+C to stop."
    Write-Host "Settings are read-only through the link. Logs: $logDir"
    Wait-Process -Id $tunnel.Id
} finally {
    Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
    Stop-App
    Write-Host "Tunnel and app stopped."
}
