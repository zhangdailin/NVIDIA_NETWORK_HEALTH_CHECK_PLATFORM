@echo off
REM Test runner script for Windows
REM NVIDIA Network Health Check Platform

echo ==========================================
echo NVIDIA Network Health Check Platform
echo Test Suite Runner (Windows)
echo ==========================================
echo.

REM Check if virtual environment exists
if not exist "backend\.venv" (
    echo Virtual environment not found. Creating...
    cd backend
    python -m venv .venv
    cd ..
)

REM Activate virtual environment
echo Activating virtual environment...
call backend\.venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -q -r backend\requirements.txt
pip install -q -r test\requirements-test.txt

REM Create test data directory
if not exist "test\test_data" mkdir test\test_data

REM Copy sample data from uploads if available
echo Preparing test data...
if exist "backend\uploads" (
    for /d %%D in (backend\uploads\*) do (
        if exist "%%D\extracted" (
            for /r "%%D\extracted" %%F in (*.db_csv) do (
                set "DB_CSV=%%F"
                goto :found_data
            )
        )
    )
    :found_data
    if defined DB_CSV (
        for %%F in ("%DB_CSV%") do set "DATA_DIR=%%~dpF"
        if not exist "test\test_data\sample_ibdiagnet" (
            echo Copying sample data from uploads...
            mkdir test\test_data\sample_ibdiagnet
            xcopy /E /I /Q "!DATA_DIR!" test\test_data\sample_ibdiagnet\
            echo Sample data prepared
        ) else (
            echo Sample data already exists
        )
    )
)

echo.
echo ==========================================
echo Running Tests
echo ==========================================
echo.

REM Run tests based on argument
if "%1"=="unit" (
    echo Running unit tests only...
    pytest test\unit -m unit
) else if "%1"=="integration" (
    echo Running integration tests only...
    pytest test\integration -m integration
) else if "%1"=="api" (
    echo Running API tests only...
    pytest test\integration\test_api_upload.py
) else if "%1"=="coverage" (
    echo Running all tests with coverage...
    pytest --cov-report=html --cov-report=term
    echo.
    echo Coverage report generated at test\htmlcov\index.html
) else if "%1"=="quick" (
    echo Running quick tests (no slow tests)...
    pytest -m "not slow"
) else (
    echo Running all tests...
    pytest
)

set TEST_EXIT_CODE=%ERRORLEVEL%

echo.
echo ==========================================
echo Test Results
echo ==========================================

if %TEST_EXIT_CODE%==0 (
    echo [32m✓ All tests passed![0m
) else (
    echo [31m✗ Some tests failed[0m
)

echo.
echo Coverage report: test\htmlcov\index.html
echo.

exit /b %TEST_EXIT_CODE%
