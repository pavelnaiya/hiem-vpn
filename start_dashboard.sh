#!/bin/bash

# Exit on error
set -e

echo "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt

echo "======================================"
echo " Starting Web Dashboard... "
echo " Access it at: http://localhost:8080 "
echo "======================================"

cd webapp
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
