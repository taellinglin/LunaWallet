#!/usr/bin/env pwsh

Write-Host ""
Write-Host "========================================"
Write-Host "Luna Wallet - Build and Run"
Write-Host "========================================"
Write-Host ""

# Clean previous build
Write-Host "Cleaning previous build..."
flet build windows --cleanup-app --cleanup-packages

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed with error code $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Build completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Launching application with console..." -ForegroundColor Cyan
Write-Host ""

# Run the compiled exe with console window
$exePath = "build\windows\LunaWallet.exe"

if (Test-Path $exePath) {
    Write-Host "Starting: $exePath"
    & $exePath
} else {
    Write-Host "ERROR: Executable not found at $exePath" -ForegroundColor Red
    Write-Host "Checking build directory..."
    Get-ChildItem build\windows\ -ErrorAction SilentlyContinue
    Read-Host "Press Enter to exit"
}

Read-Host "Press Enter to exit"
