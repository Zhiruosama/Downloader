$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = Join-Path $Root "desktop"

Write-Host "Starting Downloader dev environment..." -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $Desktop "node_modules"))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $Desktop
    npm install
    Pop-Location
}

$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"

$ExistingBackend = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($ExistingBackend) {
    Write-Host "Port 8765 is already in use. Stopping old backend process..." -ForegroundColor Yellow
    Stop-Process -Id $ExistingBackend.OwningProcess -Force
    Start-Sleep -Seconds 1
}

Write-Host "Starting Python backend at http://127.0.0.1:8765 ..." -ForegroundColor Green
$Backend = Start-Process powershell -PassThru -WorkingDirectory $Root -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "python main.py"
)

Start-Sleep -Seconds 2

Write-Host "Starting Tauri GUI..." -ForegroundColor Green
Push-Location $Desktop
npm run tauri:dev
Pop-Location

if ($Backend -and -not $Backend.HasExited) {
    Write-Host "Backend is still running in a separate PowerShell window." -ForegroundColor Cyan
}
