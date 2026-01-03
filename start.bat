@echo off
echo ========================================
echo    Orchestrator - Multi-Agent System
echo ========================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

:: Check for API key
if "%ANTHROPIC_API_KEY%"=="" (
    echo WARNING: ANTHROPIC_API_KEY is not set
    echo.
    set /p ANTHROPIC_API_KEY="Enter your Anthropic API key: "
)

:: Install dependencies if needed
if not exist ".installed" (
    echo Installing dependencies...
    pip install -e . >nul 2>&1
    echo. > .installed
)

echo.
echo Starting Orchestrator Server...
echo.
echo ========================================
echo   Dashboard: http://localhost:8420
echo ========================================
echo.
echo Open your browser to http://localhost:8420
echo Press Ctrl+C to stop the server
echo.

:: Start the server
python -m orchestrator.cli server --host 0.0.0.0 --port 8420
