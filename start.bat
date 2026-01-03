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
    setx ANTHROPIC_API_KEY "%ANTHROPIC_API_KEY%" >nul 2>&1
)

:: Always install/reinstall the package
echo.
echo Installing dependencies (this may take a minute)...
pip install -e . --quiet
if errorlevel 1 (
    echo.
    echo Trying alternative install method...
    pip install anthropic fastapi uvicorn websockets pydantic pydantic-settings pyyaml rich typer aiosqlite gitpython httpx --quiet
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

:: Start the server using the module directly
python -c "from orchestrator.api.main import run_server; run_server(host='0.0.0.0', port=8420)"

:: If that fails, try running uvicorn directly
if errorlevel 1 (
    echo.
    echo Trying alternative startup...
    set PYTHONPATH=%CD%\src
    python -c "import sys; sys.path.insert(0, 'src'); from orchestrator.api.main import run_server; run_server(host='0.0.0.0', port=8420)"
)

pause
