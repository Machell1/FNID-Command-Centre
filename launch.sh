#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt --quiet 2>/dev/null

# Launch
echo "Starting FNID Portal at http://localhost:5000"
python main.py
