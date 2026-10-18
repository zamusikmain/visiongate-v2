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
$app = Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "tools\serve_public.py", "--port", "$Port" `
    -RedirectStandardOutput $appLog -RedirectStandardError "$appLog.err" -WindowStyle Hidden -PassThru
Remove-Item Env:\VG_PUBLIC_PASSWORD
$up = $false
for ($i = 0; $i -lt 60 -and -not $up; $i++) {
    Start-Sleep -Seconds 1
    try { Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true }
    catch { if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { $up = $true } }
}
if (-not $up) {
    Write-Host "The app did not start, see $appLog.err" -ForegroundColor Red
    Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

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
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match "serve_public\.py" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "Tunnel and app stopped."
}
