# LunaWallet Environment Launcher
# This script activates the virtual environment and sets up all required environment variables

param(
    [string]$Command = "run",
    [switch]$BuildWindows,
    [switch]$BuildWeb,
    [switch]$Test
)

# Get the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Load .env file manually (PowerShell doesn't have built-in dotenv support)
function Load-EnvFile {
    param([string]$EnvFile)
    
    if (-not (Test-Path $EnvFile)) {
        Write-Host "⚠ .env file not found at $EnvFile" -ForegroundColor Yellow
        return
    }
    
    $content = Get-Content $EnvFile
    foreach ($line in $content) {
        # Skip comments and empty lines
        if ($line -match '^\s*#' -or $line -match '^\s*$') {
            continue
        }
        
        # Parse KEY=VALUE
        if ($line -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "✓ Loaded environment from $EnvFile" -ForegroundColor Green
}

# Load environment variables
Load-EnvFile (Join-Path $ScriptDir ".env")

# Activate virtual environment
$venvPath = ".venv"
$activateScript = Join-Path $venvPath "Scripts" "Activate.ps1"

if (Test-Path $activateScript) {
    Write-Host "✓ Activating virtual environment..." -ForegroundColor Green
    & $activateScript
} else {
    Write-Host "⚠ Virtual environment not found at $venvPath" -ForegroundColor Yellow
}

# Print configuration
Write-Host "`n" + ("="*50)
Write-Host "LunaWallet Environment Configuration"
Write-Host ("="*50)
Write-Host "Python: $(python --version)"
Write-Host "Virtual Environment: $venvPath"
Write-Host "CMake Generator: $($env:CMAKE_GENERATOR)"
Write-Host "CMake Platform: $($env:CMAKE_GENERATOR_PLATFORM)"
Write-Host "Working Directory: $(Get-Location)"
Write-Host ("="*50) -ForegroundColor Cyan
Write-Host ""

# Execute the requested command
if ($BuildWindows) {
    Write-Host "Building Windows application..." -ForegroundColor Cyan
    flet build windows
}
elseif ($BuildWeb) {
    Write-Host "Building web application..." -ForegroundColor Cyan
    flet build web
}
elseif ($Test) {
    Write-Host "Running tests..." -ForegroundColor Cyan
    python -m pytest
}
else {
    Write-Host "Running LunaWallet..." -ForegroundColor Cyan
    python main.py
}
