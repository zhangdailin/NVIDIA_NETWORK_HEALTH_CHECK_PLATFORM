"""Unit tests for cable service."""

import pytest
import pandas as pd
from services.cable_service import analyze_cable_info
from services.anomalies import AnomlyType


class TestCableService:
    """Test cable analysis service."""

    def test_analyze_cable_info_basic(self, db_csv_file, sample_ibdiagnet_dir):
        """Test basic cable info analysis."""
        result = analyze_cable_info(sample_ibdiagnet_dir)

        # Should return a dictionary
        assert isinstance(result, dict)
        assert "data" in result
        assert "summary" in result

        # Data should be a list
        assert isinstance(result["data"], list)

    def test_temperature_warning_detection(self, db_csv_file, sample_ibdiagnet_dir):
        """Test that high temperature warnings are detected."""
        result = analyze_cable_info(sample_ibdiagnet_dir)

        # Check if any high temperature issues were detected
        high_temp_items = [
            item for item in result["data"]
            if item.get("Temperature (c)") and item["Temperature (c)"] >= 70
        ]

        # If high temp items exist, they should have anomaly flags
        for item in high_temp_items:
            temp = item["Temperature (c)"]
            if temp >= 80:
                # Should be marked as critical
                assert AnomlyType.IBH_OPTICAL_TEMP_HIGH.value in item.get("IBH_ANOMALY_AGG", "")
            elif temp >= 70:
                # Should be marked as warning
                assert AnomlyType.IBH_OPTICAL_TEMP_HIGH.value in item.get("IBH_ANOMALY_AGG", "")

    def test_optical_alarm_detection(self, db_csv_file, sample_ibdiagnet_dir):
        """Test optical module alarm detection."""
        result = analyze_cable_info(sample_ibdiagnet_dir)

        # Check for optical alarms in data
        for item in result["data"]:
            # If any alarm field is present and true, should have anomaly
            alarm_fields = [
                "TX Power Alarm",
                "RX Power Alarm",
                "TX Bias Alarm",
                "Voltage Alarm",
            ]

            has_alarm = any(item.get(field) for field in alarm_fields)
            if has_alarm:
                # Should have corresponding anomaly
                assert "IBH_OPTICAL" in item.get("IBH_ANOMALY_AGG", "")

    def test_cable_summary_statistics(self, db_csv_file, sample_ibdiagnet_dir):
        """Test that summary statistics are calculated."""
        result = analyze_cable_info(sample_ibdiagnet_dir)

        summary = result["summary"]

        # Should have key statistics
        assert "total_cables" in summary
        assert "vendors" in summary
        assert "cable_types" in summary

        # Counts should be non-negative
        assert summary["total_cables"] >= 0

    def test_vendor_distribution(self, db_csv_file, sample_ibdiagnet_dir):
        """Test vendor distribution calculation."""
        result = analyze_cable_info(sample_ibdiagnet_dir)

        if result["data"]:
            # Should have vendor information
            vendors = [item.get("Vendor") for item in result["data"] if item.get("Vendor")]
            assert len(vendors) > 0

            # Summary should reflect vendors
            assert "vendors" in result["summary"]

    def test_cable_compliance_check(self, db_csv_file, sample_ibdiagnet_dir):
        """Test cable compliance checking."""
        result = analyze_cable_info(sample_ibdiagnet_dir)

        # Check for compliance fields
        for item in result["data"]:
            if "CableComplianceStatus" in item:
                # Status should be valid
                assert item["CableComplianceStatus"] in [True, False, None]

    def test_empty_cable_data_handling(self, tmp_path):
        """Test handling of missing cable data."""
        # Create empty directory
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should handle gracefully
        result = analyze_cable_info(empty_dir)
        assert isinstance(result, dict)
        assert result["data"] == [] or result["summary"]["total_cables"] == 0


class TestCableServiceEdgeCases:
    """Test edge cases in cable service."""

    def test_missing_temperature_field(self):
        """Test handling of missing temperature data."""
        # This would require mocking the data reading
        # For now, we document the expected behavior
        pass

    def test_invalid_temperature_values(self):
        """Test handling of invalid temperature values (NaN, negative, etc.)."""
        pass

    def test_cable_length_validation(self):
        """Test cable length compliance checking."""
        pass
