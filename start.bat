@echo off
title FNID Portal
cd /d "%~dp0"

echo ============================================
echo    FNID Area 3 Operational Portal
echo ============================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create venv if missing
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet 2>nul

:: Launch
echo.
echo Starting FNID Portal...
echo Portal will open in your browser automatically.
echo Press Ctrl+C to stop the server.
echo.
python main.py

pause
