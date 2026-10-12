# One-command setup + start for Windows. Needs only Python 3.11+.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = if ($env:PYTHON) { $env:PYTHON } else { "python" }
& $py -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python 3.11+ is required. Install from https://www.python.org/downloads/"
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    & $py -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Error "Could not create virtual environment."; exit 1 }
}

$marker = ".venv\.deps-installed"
if (-not (Test-Path $marker) -or ((Get-Item requirements.txt).LastWriteTime -gt (Get-Item $marker).LastWriteTime)) {
    Write-Host "Installing dependencies..."
    & .venv\Scripts\python.exe -m pip install -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip install failed. Behind a corporate proxy, set PIP_CERT to your CA bundle and retry."
        exit 1
    }
    New-Item -ItemType File -Force $marker | Out-Null
}

if (-not (Test-Path "data\sandbox.db")) {
    Write-Host "Generating dataset..."
    & .venv\Scripts\python.exe -m datagen
    if ($LASTEXITCODE -ne 0) { Write-Error "Dataset generation failed."; exit 1 }
}

$port = if ($env:PORT) { $env:PORT } else { "8000" }
if ($port -notmatch "^\d{2,5}$") { Write-Error "PORT must be a number."; exit 1 }
Write-Host ""
Write-Host "  T-Mobile Hackathon Sandbox (STUB DATA ONLY)"
Write-Host "  API docs:  http://localhost:$port/docs"
Write-Host ""
& .venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port $port
