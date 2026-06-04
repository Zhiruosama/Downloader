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
