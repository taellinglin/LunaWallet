param(
    [string]$ProjectRoot = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Building APK (release)..." -ForegroundColor Cyan
$ProjectRoot = @($ProjectRoot)[0]
$ProjectRoot = (Resolve-Path -Path $ProjectRoot).Path
Push-Location $ProjectRoot

# Ensure flet uses repo root
$env:FLET_APP_DIR = $ProjectRoot
Remove-Item Env:FLET_APP_PATH -ErrorAction SilentlyContinue
if (-not (Test-Path (Join-Path $ProjectRoot "pyproject.toml"))) {
    Write-Host "ERROR: pyproject.toml not found in $ProjectRoot" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Ensure Flutter on PATH resolves to flutter.bat (Windows)
$flutterCmd = Get-Command flutter -ErrorAction SilentlyContinue
if (-not $flutterCmd -or -not $flutterCmd.Source -or ($flutterCmd.Source -notlike "*.bat")) {
    Write-Host "ERROR: Flutter not found (flutter.bat). Please add Flutter to PATH (e.g., C:\\src\\flutter\\bin)." -ForegroundColor Red
    Pop-Location
    exit 1
}

# Resolve venv tools (prefer repo venvs)
$pythonExe = $null
$fletExe = $null
$candidates = @(
    "$ProjectRoot\.venv-win\Scripts",
    "$ProjectRoot\.venv\Scripts",
    "$ProjectRoot\venv\Scripts"
)
foreach ($dir in $candidates) {
    if (Test-Path $dir) {
        if (-not $pythonExe -and (Test-Path "$dir\python.exe")) { $pythonExe = "$dir\python.exe" }
        if (-not $fletExe -and (Test-Path "$dir\flet.exe")) { $fletExe = "$dir\flet.exe" }
    }
}
if (-not $pythonExe) { $pythonExe = "python" }

# Clean stale build/flutter if pubspec is missing
$flutterRoot = "$ProjectRoot\build\flutter"
if (Test-Path $flutterRoot) {
    $pubspec = Join-Path $flutterRoot "pubspec.yaml"
    if (-not (Test-Path $pubspec)) {
        Write-Host "Stale build/flutter detected (missing pubspec). Cleaning..." -ForegroundColor Yellow
        $gradleWrapper = Join-Path $flutterRoot "android\gradlew.bat"
        if (Test-Path $gradleWrapper) {
            & $gradleWrapper --stop | Out-Null
        }
        if ($flutterRoot -and ($flutterRoot -like "$ProjectRoot*")) {
            Remove-Item -LiteralPath $flutterRoot -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "Refusing to delete unexpected path: $flutterRoot" -ForegroundColor Red
            Pop-Location
            exit 1
        }
    }
}

# Ensure flet-cli is installed and use its console entry point
& $pythonExe -m pip install -U flet-cli | Out-Null
if (-not $fletExe) {
    foreach ($dir in $candidates) {
        if (Test-Path "$dir\flet.exe") { $fletExe = "$dir\flet.exe"; break }
    }
}
if (-not $fletExe) {
    Write-Host "ERROR: flet.exe not found after installing flet-cli." -ForegroundColor Red
    Pop-Location
    exit 1
}

& $fletExe build apk

Write-Host "Patching Android Gradle for ProGuard/R8..." -ForegroundColor Cyan
& $pythonExe scripts\patch_android_proguard.py

Write-Host "Rebuilding APK with ProGuard/R8..." -ForegroundColor Cyan
$flutterRoot = "$ProjectRoot\build\flutter"
$pythonBuildRoot = "$flutterRoot\build"
$sitePackages = Get-ChildItem -Path $pythonBuildRoot -Directory -Filter "build_python_*" -ErrorAction SilentlyContinue |
    Select-Object -First 1 |
    ForEach-Object { Join-Path $_.FullName "python\Lib\site-packages" }
if ($sitePackages -and (Test-Path $sitePackages)) {
    $env:SERIOUS_PYTHON_SITE_PACKAGES = $sitePackages
    Write-Host "SERIOUS_PYTHON_SITE_PACKAGES=$sitePackages" -ForegroundColor DarkGray
}

Push-Location $flutterRoot
flutter build apk --release
Pop-Location

Write-Host "Done." -ForegroundColor Green
Pop-Location
