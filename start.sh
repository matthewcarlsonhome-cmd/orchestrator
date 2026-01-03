#!/bin/bash
echo "========================================"
echo "   Orchestrator - Multi-Agent System"
echo "========================================"
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.11+"
    exit 1
fi

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "WARNING: ANTHROPIC_API_KEY is not set"
    echo
    read -p "Enter your Anthropic API key: " ANTHROPIC_API_KEY
    export ANTHROPIC_API_KEY
fi

# Install dependencies if needed
if [ ! -f ".installed" ]; then
    echo "Installing dependencies..."
    pip install -e . > /dev/null 2>&1
    touch .installed
fi

echo
echo "Starting Orchestrator Server..."
echo
echo "========================================"
echo "  Dashboard: http://localhost:8420"
echo "========================================"
echo
echo "Open your browser to http://localhost:8420"
echo "Press Ctrl+C to stop the server"
echo

# Start the server
python -m orchestrator.cli server --host 0.0.0.0 --port 8420
