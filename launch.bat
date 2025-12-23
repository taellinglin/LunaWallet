@echo off
REM LunaWallet Environment Launcher for Command Prompt
REM This script activates the virtual environment and sets up all required environment variables

setlocal enabledelayedexpansion

REM Get the script directory
set SCRIPT_DIR=%~dp0

REM Load .env file variables
if exist "%SCRIPT_DIR%.env" (
    echo Loading environment from .env...
    for /f "tokens=1,2 delims==" %%a in ('findstr /v "^#" "%SCRIPT_DIR%.env"') do (
        if not "%%a"=="" if not "%%b"=="" (
            set "%%a=%%b"
        )
    )
    echo [OK] Environment loaded
) else (
    echo [WARNING] .env file not found
)

REM Activate virtual environment
if exist "%SCRIPT_DIR%.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
) else (
    echo [WARNING] Virtual environment not found at .venv
)

REM Print configuration
echo.
echo ==================================================
echo LunaWallet Environment Configuration
echo ==================================================
python --version
echo Virtual Environment: .venv
echo CMake Generator: %CMAKE_GENERATOR%
echo CMake Platform: %CMAKE_GENERATOR_PLATFORM%
echo Working Directory: %cd%
echo ==================================================
echo.

REM Execute commands based on arguments
if "%1"=="build-windows" (
    echo Building Windows application...
    flet build windows
) else if "%1"=="build-web" (
    echo Building web application...
    flet build web
) else if "%1"=="test" (
    echo Running tests...
    python -m pytest
) else (
    echo Running LunaWallet...
    python main.py
)

endlocal
