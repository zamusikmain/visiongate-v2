# VisionGate launcher for Windows PowerShell 5.1+ (ASCII only on purpose: 5.1 reads BOM-less files as ANSI).
#   .\run.ps1            HTTPS on :8443 (needed for the phone camera)
#   .\run.ps1 -Http      HTTP on :8000, local debugging only
#   .\run.ps1 -NoDocker  skip Ollama (background screen-photo check will be unavailable)
param([switch]$Http, [int]$Port = 0, [switch]$NoDocker)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Python virtual environment
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "Python 3.11+ not found in PATH. Install it from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
        exit 1
    }
    Write-Host "Creating virtual environment and installing dependencies (first run only)..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Failed to create .venv" -ForegroundColor Red; exit 1 }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed, see the output above" -ForegroundColor Red; exit 1 }
}

# 2. Ollama in Docker. Not fatal: the fast checks work without it.
function Start-Ollama {
    # In 5.1, redirecting a native command's stderr under "Stop" throws even on success: check exit codes instead.
    $ErrorActionPreference = "Continue"
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return "docker is not installed" }
    docker info *> $null
    if ($LASTEXITCODE -ne 0) { return "Docker Desktop is not running" }
    $existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq "vg-ollama" }
    if ($existing) { docker start vg-ollama *> $null } else { docker compose up -d *> $null }
    if ($LASTEXITCODE -ne 0) { return "could not start the vg-ollama container" }
    $models = (docker exec vg-ollama ollama list 2> $null) | Out-String
    if ($models -notmatch "qwen2\.5vl:3b") {
        Write-Host "Downloading model qwen2.5vl:3b (~3 GB, first run only)..."
        docker exec vg-ollama ollama pull qwen2.5vl:3b
        if ($LASTEXITCODE -ne 0) { return "model download failed" }
    }
    return ""
}

if (-not $NoDocker) {
    try { $problem = Start-Ollama } catch { $problem = "$_" }
    if ($problem) {
        Write-Warning "Ollama unavailable ($problem). Background screen-photo check will not run; such submissions go to manual review."
    } else {
        Write-Host "Ollama is running (container vg-ollama)."
    }
}

# 3. Web server
$pyArgs = @()
if ($Http) { $pyArgs += "--http" }
if ($Port) { $pyArgs += @("--port", $Port) }
$scheme = if ($Http) { "http" } else { "https" }
$shownPort = if ($Port) { $Port } elseif ($Http) { 8000 } else { 8443 }
Write-Host "Starting VisionGate: ${scheme}://<laptop-IP>:$shownPort  (Ctrl+C to stop)"
& .\.venv\Scripts\python.exe -m visiongate @pyArgs
