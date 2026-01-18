@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo Luna Wallet - Build and Run
echo ========================================
echo.

REM Clean previous build
echo Cleaning previous build...
flet build windows --cleanup-app --cleanup-packages

if !errorlevel! neq 0 (
    echo Build failed with error code !errorlevel!
    pause
    exit /b !errorlevel!
)

echo.
echo Build completed successfully!
echo.
echo Launching application with console...
echo.

REM Run the compiled exe with console window
set EXE_PATH=build\windows\LunaWallet.exe

if exist "!EXE_PATH!" (
    echo Starting: !EXE_PATH!
    "!EXE_PATH!"
) else (
    echo ERROR: Executable not found at !EXE_PATH!
    echo Checking build directory...
    dir build\windows\
    pause
)

pause
