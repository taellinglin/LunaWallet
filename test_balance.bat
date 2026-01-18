@echo off
REM Test runner for balance display tests

echo.
echo ===================================
echo  LunaWallet Balance Display Tests
echo ===================================
echo.

cd /d "%~dp0"

REM Run the balance display tests
python test_balance_display.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] All balance tests passed!
    exit /b 0
) else (
    echo.
    echo [FAILED] Some balance tests failed
    exit /b 1
)
