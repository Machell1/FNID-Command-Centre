# FNID Portal One-Click Launcher (Windows PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Create venv if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

# Activate venv
& .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt --quiet

# Launch
Write-Host "Starting FNID Portal at http://localhost:5000"
python main.py
