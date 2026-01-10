# NVIDIA Network Health Check Platform - Testing Guide

## 📋 Overview

This document describes the comprehensive test suite for the NVIDIA Network Health Check Platform backend.

## 🎯 Test Coverage

### Test Structure

```
test/
├── conftest.py                    # Pytest configuration and fixtures
├── requirements-test.txt          # Test dependencies
├── unit/                          # Unit tests (70+ tests)
│   ├── test_dbcsv_parser.py      # db_csv parsing (12 tests)
│   ├── test_health_score.py      # Health score calculation (18 tests)
│   ├── test_cable_service.py     # Cable analysis (10 tests)
│   └── ...
├── integration/                   # Integration tests (15+ tests)
│   ├── test_api_upload.py        # API endpoints (15 tests)
│   └── test_analysis_service.py  # Full pipeline (10 tests)
└── test_data/                     # Test data (copied from uploads)
    └── sample_ibdiagnet/
```

### Coverage Goals

- **Overall Coverage**: ≥70%
- **Critical Services**: ≥85%
  - `health_score.py`
  - `analysis_service.py`
  - `dbcsv.py`
- **API Layer**: ≥80%
- **Service Layer**: ≥75%

## 🚀 Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install -r test/requirements-test.txt
```

### Quick Start

```bash
# Run all tests (Linux/Mac)
./run_tests.sh

# Run all tests (Windows)
run_tests.bat

# Run specific test suites
./run_tests.sh unit          # Unit tests only
./run_tests.sh integration   # Integration tests only
./run_tests.sh api          # API tests only
./run_tests.sh coverage     # With detailed coverage report
./run_tests.sh quick        # Skip slow tests
```

### Manual Pytest Commands

```bash
# Run all tests
pytest

# Run specific test file
pytest test/unit/test_health_score.py

# Run specific test
pytest test/unit/test_health_score.py::TestHealthScoreCalculation::test_perfect_health_score

# Run with coverage
pytest --cov=backend --cov-report=html

# Run with markers
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only
pytest -m "not slow"        # Skip slow tests

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l
```

## 📊 Test Categories

### 1. Unit Tests

#### `test_dbcsv_parser.py` - Data Parsing Layer
- ✅ Index table parsing
- ✅ Table reading with correct offsets
- ✅ Caching mechanism
- ✅ Error handling (missing files, invalid tables)
- ✅ Encoding (latin-1)
- ✅ N/A and ERR value handling

#### `test_health_score.py` - Health Score Calculation
- ✅ Score calculation (0-100 range)
- ✅ Grade assignment (A-F)
- ✅ Category weights (ber, errors, congestion, etc.)
- ✅ Severity multipliers (critical, warning, info)
- ✅ Anomaly detection and aggregation
- ✅ Temperature threshold detection
- ✅ Link down event detection
- ✅ Link error recovery detection
- ✅ Node and port counting
- ✅ Knowledge base attachment

#### `test_cable_service.py` - Cable Analysis
- ✅ Basic cable info parsing
- ✅ Temperature warning detection (70°C, 80°C)
- ✅ Optical alarm detection (TX/RX power, bias, voltage)
- ✅ Vendor distribution statistics
- ✅ Cable compliance checking
- ✅ Empty data handling

### 2. Integration Tests

#### `test_api_upload.py` - API Endpoints
- ✅ Health check endpoint
- ✅ File upload validation
  - File type validation
  - File size limits (500MB)
  - Magic bytes verification
  - Path traversal prevention
- ✅ IBDiagnet upload and analysis
- ✅ UFM CSV upload and parsing
- ✅ Rate limiting (10 req/min)
- ✅ Request ID tracking
- ✅ CORS headers
- ✅ Error handling

#### `test_analysis_service.py` - Full Pipeline
- ✅ Complete analysis pipeline
- ✅ Dataset loading
- ✅ Parallel service execution
- ✅ Error handling (missing tables)
- ✅ Topology generation
- ✅ Anomaly detection integration
- ✅ Result consistency

## 🔍 Key Test Scenarios

### Scenario 1: Healthy Network
```python
# Input: Network with no issues
# Expected: Score ≥90, Grade A/B, Status "Healthy"
```

### Scenario 2: High Temperature
```python
# Input: Cable temperature ≥80°C
# Expected: Critical issue, IBH_OPTICAL_TEMP_HIGH anomaly
```

### Scenario 3: Link Down Events
```python
# Input: LinkDownedCounter > 0
# Expected: Critical issue, score penalty
```

### Scenario 4: BER Issues
```python
# Input: High Symbol BER (>1e-6)
# Expected: IBH_HIGH_SYMBOL_BER, category "ber" penalty
```

### Scenario 5: Congestion
```python
# Input: WaitRatioPct ≥5%
# Expected: IBH_XMIT_TIME_CONG, category "congestion" penalty
```

## 🐛 Known Issues to Test For

Based on code analysis, these are potential issues to verify:

### 1. **Data Parsing Issues**
- [ ] Empty tables causing crashes
- [ ] Missing required columns
- [ ] Invalid GUID formats
- [ ] Unicode/encoding errors

### 2. **Health Score Calculation**
- [ ] Division by zero when no data
- [ ] Score exceeding 100 or below 0
- [ ] Category weight miscalculation
- [ ] Duplicate anomaly counting

### 3. **Service Layer**
- [ ] Race conditions in parallel execution
- [ ] Memory leaks with large datasets
- [ ] Timeout handling
- [ ] Cache invalidation

### 4. **API Layer**
- [ ] Path traversal vulnerabilities
- [ ] File handle leaks
- [ ] Rate limit bypass
- [ ] CORS misconfiguration

## 📈 Coverage Report

After running tests with coverage:

```bash
./run_tests.sh coverage
```

Open the HTML report:
```
test/htmlcov/index.html
```

### Expected Coverage

| Module | Target | Critical |
|--------|--------|----------|
| `health_score.py` | 85% | ✅ |
| `analysis_service.py` | 80% | ✅ |
| `dbcsv.py` | 90% | ✅ |
| `cable_service.py` | 75% | ⚠️ |
| `ber_service.py` | 75% | ⚠️ |
| `xmit_service.py` | 75% | ⚠️ |
| `api.py` | 80% | ✅ |
| `main.py` | 70% | ⚠️ |

## 🔧 Troubleshooting

### Issue: No test data available
```bash
# Copy data from uploads manually
cp -r backend/uploads/<latest>/extracted/var/tmp/ibdiagnet2/* test/test_data/sample_ibdiagnet/
```

### Issue: Import errors
```bash
# Ensure backend is in Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"
```

### Issue: Async test failures
```bash
# Install pytest-asyncio
pip install pytest-asyncio
```

### Issue: Coverage not generated
```bash
# Install coverage tools
pip install pytest-cov coverage
```

## 📝 Adding New Tests

### Template for Unit Test

```python
"""Unit tests for <module_name>."""

import pytest
from services.<module_name> import <function_name>


class Test<ModuleName>:
    """Test <module> functionality."""

    def test_<scenario>_success(self):
        """Test successful <scenario>."""
        # Arrange
        input_data = {...}

        # Act
        result = <function_name>(input_data)

        # Assert
        assert result is not None
        assert result["expected_field"] == expected_value

    def test_<scenario>_error_handling(self):
        """Test error handling for <scenario>."""
        with pytest.raises(ExpectedException):
            <function_name>(invalid_input)
```

### Template for Integration Test

```python
"""Integration tests for <feature>."""

import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


class Test<Feature>Integration:
    """Integration tests for <feature>."""

    def test_<scenario>_end_to_end(self, sample_data):
        """Test complete <scenario> flow."""
        # Arrange
        request_data = {...}

        # Act
        response = client.post("/api/<endpoint>", json=request_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data
```

## 🎯 Next Steps

1. **Run Initial Tests**: `./run_tests.sh coverage`
2. **Review Coverage Report**: Check `test/htmlcov/index.html`
3. **Identify Gaps**: Focus on modules with <70% coverage
4. **Fix Failing Tests**: Address any test failures
5. **Add Missing Tests**: Cover edge cases and error paths
6. **Verify with Real Data**: Test with actual IBDiagnet outputs
7. **Performance Testing**: Add tests for large datasets
8. **CI/CD Integration**: Set up automated testing

## 📚 References

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py](https://coverage.readthedocs.io/)
