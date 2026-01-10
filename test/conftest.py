"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path
import pytest
import shutil

# Add backend to Python path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture(scope="session")
def sample_ibdiagnet_dir(test_data_dir):
    """
    Path to sample IBDiagnet data.

    This fixture copies real data from uploads directory for testing.
    """
    sample_dir = test_data_dir / "sample_ibdiagnet"

    # If sample data doesn't exist, copy from uploads
    if not sample_dir.exists():
        uploads_dir = Path(__file__).parent.parent / "backend" / "uploads"

        # Find the most recent upload with extracted data
        upload_dirs = sorted(
            [d for d in uploads_dir.iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        for upload_dir in upload_dirs:
            extracted_dir = upload_dir / "extracted"
            if extracted_dir.exists():
                # Find db_csv file
                db_csv_files = list(extracted_dir.rglob("*.db_csv"))
                if db_csv_files:
                    source_data_dir = db_csv_files[0].parent
                    sample_dir.mkdir(parents=True, exist_ok=True)

                    # Copy all files from source
                    for item in source_data_dir.iterdir():
                        if item.is_file():
                            shutil.copy2(item, sample_dir / item.name)
                    break

    if not sample_dir.exists():
        pytest.skip("No sample IBDiagnet data available")

    return sample_dir


@pytest.fixture
def db_csv_file(sample_ibdiagnet_dir):
    """Path to the main db_csv file."""
    db_csv_files = list(sample_ibdiagnet_dir.glob("*.db_csv"))
    if not db_csv_files:
        pytest.skip("No db_csv file found in sample data")
    return db_csv_files[0]


@pytest.fixture
def mock_health_data():
    """Mock health data for testing health score calculation."""
    # IMPORTANT: Use correct column names from anomalies.py
    # IBH_ANOMALY_AGG_COL = "IBH Anomaly"
    # IBH_ANOMALY_AGG_WEIGHT = "IBH Anomaly Weight"
    return {
        "analysis_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "IBH Anomaly": "High xmit-wait",
                "IBH Anomaly Weight": 5.0,
            }
        ],
        "cable_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "Temperature (c)": 75,
                "IBH Anomaly": "Optical Temperature High",
                "IBH Anomaly Weight": 3.0,
            }
        ],
        "xmit_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "WaitRatioPct": 6.5,
                "IBH Anomaly": "Transmit Time Congestion",
                "IBH Anomaly Weight": 8.0,
            }
        ],
        "ber_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "SymbolBER": 1e-6,
                "IBH Anomaly": "High Symbol BER",
                "IBH Anomaly Weight": 10.0,
            }
        ],
        "hca_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "FW": "28.39.1002",
                "PSID_Compliant": True,
                "FW_Compliant": True,
            }
        ],
    }


@pytest.fixture
def mock_empty_health_data():
    """Mock empty health data (healthy network)."""
    return {
        "analysis_data": [],
        "cable_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "Temperature (c)": 45,
            }
        ],
        "xmit_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "WaitRatioPct": 0.1,
            }
        ],
        "ber_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "SymbolBER": 1e-12,
            }
        ],
        "hca_data": [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "FW": "28.39.1002",
                "PSID_Compliant": True,
                "FW_Compliant": True,
            }
        ],
    }
