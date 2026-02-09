@echo off
REM =============================================================================
REM Nexus Startup Script (Windows)
REM =============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo    NEXUS - Personal AI Assistant
echo ========================================
echo.

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%

REM Check for virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
pip install -q --upgrade pip
pip install -q -e .

REM Check for .env file
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy .env.example .env
        echo.
        echo Please edit .env with your API keys before continuing.
        echo At minimum, set ANTHROPIC_API_KEY for LLM functionality.
        echo.
        pause
        exit /b 1
    )
)

REM Initialize Nexus
echo Initializing Nexus...
nexus init

echo.
echo Starting Nexus server...
echo Dashboard: http://127.0.0.1:8430
echo API Docs:  http://127.0.0.1:8430/docs
echo.
echo Press Ctrl+C to stop
echo.

REM Start the server
nexus serve
