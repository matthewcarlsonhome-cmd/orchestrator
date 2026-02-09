#!/bin/bash
# =============================================================================
# Nexus Startup Script (Linux/macOS)
# =============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   NEXUS - Personal AI Assistant${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Check Python version
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}Error: Python not found. Please install Python 3.10+${NC}"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "Python version: ${GREEN}$PYTHON_VERSION${NC}"

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -e .

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${RED}Please edit .env with your API keys before continuing.${NC}"
        echo -e "At minimum, set ANTHROPIC_API_KEY for LLM functionality."
        exit 1
    fi
fi

# Initialize Nexus (creates directories and database)
echo -e "${YELLOW}Initializing Nexus...${NC}"
nexus init

echo
echo -e "${GREEN}Starting Nexus server...${NC}"
echo -e "Dashboard: ${GREEN}http://127.0.0.1:8430${NC}"
echo -e "API Docs:  ${GREEN}http://127.0.0.1:8430/docs${NC}"
echo
echo -e "Press ${RED}Ctrl+C${NC} to stop"
echo

# Start the server
nexus serve
