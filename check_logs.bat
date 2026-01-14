@echo off
echo Checking for LunaWallet debug logs...
echo.

set LOG_DIR=%USERPROFILE%\LunaWallet_Logs

if exist "%LOG_DIR%" (
    echo Found log directory: %LOG_DIR%
    echo.
    echo Recent log files:
    dir /b /o-d "%LOG_DIR%\*.log" 2>nul
    echo.
    echo Opening log directory...
    explorer "%LOG_DIR%"
) else (
    echo Log directory not found at: %LOG_DIR%
    echo The app may not have created logs yet.
    echo Try running the built app first, then check again.
)

pause
