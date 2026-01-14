@echo off
echo Running built LunaWallet with console output...
echo.

set EXE_PATH=build\windows\LunaWallet.exe

if exist "%EXE_PATH%" (
    "%EXE_PATH%"
) else (
    echo ERROR: Executable not found at %EXE_PATH%
    echo Please build first using: flet build windows
)

pause
