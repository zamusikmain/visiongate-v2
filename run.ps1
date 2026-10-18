# Запуск VisionGate на Windows: .\run.ps1   (или .\run.ps1 -Http для локальной отладки без HTTPS)
param([switch]$Http, [int]$Port = 0)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv\Scripts\python.exe)) {
    Write-Host "Создаю виртуальное окружение и ставлю зависимости..."
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

# Ollama в Docker (если Docker запущен). Ошибки не фатальны: быстрые проверки работают и без неё.
try {
    $existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq "vg-ollama" }
    if ($existing) { docker start vg-ollama | Out-Null } else { docker compose up -d | Out-Null }
    $models = docker exec vg-ollama ollama list 2>$null | Out-String
    if ($models -notmatch "qwen2.5vl:3b") {
        Write-Host "Скачиваю модель qwen2.5vl:3b (~3 ГБ, один раз)..."
        docker exec vg-ollama ollama pull qwen2.5vl:3b
    }
} catch { Write-Warning "Docker/Ollama недоступны: фоновая проверка экрана не будет работать ($_)" }

$pyArgs = @()
if ($Http) { $pyArgs += "--http" }
if ($Port) { $pyArgs += @("--port", $Port) }
.\.venv\Scripts\python.exe -m visiongate @pyArgs
