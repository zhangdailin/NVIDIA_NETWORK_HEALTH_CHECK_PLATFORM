#!/bin/bash

# Test runner script for NVIDIA Network Health Check Platform
# This script runs all tests and generates coverage reports

set -e

echo "=========================================="
echo "NVIDIA Network Health Check Platform"
echo "Test Suite Runner"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "backend/.venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    cd backend
    python -m venv .venv
    cd ..
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source backend/.venv/Scripts/activate
else
    source backend/.venv/bin/activate
fi

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
pip install -q -r backend/requirements.txt
pip install -q -r test/requirements-test.txt

# Create test data directory if it doesn't exist
mkdir -p test/test_data

# Copy sample data from uploads if available
echo -e "${GREEN}Preparing test data...${NC}"
if [ -d "backend/uploads" ]; then
    # Find the most recent upload with extracted data
    LATEST_UPLOAD=$(find backend/uploads -type d -name "extracted" | head -1)
    if [ ! -z "$LATEST_UPLOAD" ]; then
        # Find db_csv file
        DB_CSV=$(find "$LATEST_UPLOAD" -name "*.db_csv" | head -1)
        if [ ! -z "$DB_CSV" ]; then
            DATA_DIR=$(dirname "$DB_CSV")
            SAMPLE_DIR="test/test_data/sample_ibdiagnet"

            if [ ! -d "$SAMPLE_DIR" ]; then
                echo -e "${GREEN}Copying sample data from uploads...${NC}"
                mkdir -p "$SAMPLE_DIR"
                cp -r "$DATA_DIR"/* "$SAMPLE_DIR/"
                echo -e "${GREEN}Sample data prepared at $SAMPLE_DIR${NC}"
            else
                echo -e "${YELLOW}Sample data already exists${NC}"
            fi
        fi
    fi
fi

echo ""
echo "=========================================="
echo "Running Tests"
echo "=========================================="
echo ""

# Run different test suites based on argument
case "${1:-all}" in
    unit)
        echo -e "${GREEN}Running unit tests only...${NC}"
        pytest test/unit -m unit
        ;;
    integration)
        echo -e "${GREEN}Running integration tests only...${NC}"
        pytest test/integration -m integration
        ;;
    api)
        echo -e "${GREEN}Running API tests only...${NC}"
        pytest test/integration/test_api_upload.py
        ;;
    coverage)
        echo -e "${GREEN}Running all tests with coverage...${NC}"
        pytest --cov-report=html --cov-report=term
        echo ""
        echo -e "${GREEN}Coverage report generated at test/htmlcov/index.html${NC}"
        ;;
    quick)
        echo -e "${GREEN}Running quick tests (no slow tests)...${NC}"
        pytest -m "not slow"
        ;;
    all)
        echo -e "${GREEN}Running all tests...${NC}"
        pytest
        ;;
    *)
        echo -e "${RED}Unknown test suite: $1${NC}"
        echo "Usage: $0 {unit|integration|api|coverage|quick|all}"
        exit 1
        ;;
esac

TEST_EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
fi

echo ""
echo "Coverage report: test/htmlcov/index.html"
echo ""

exit $TEST_EXIT_CODE
