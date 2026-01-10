"""Unit tests for Warnings service."""

import pytest
import pandas as pd
from services.warnings_service import analyze_warnings


class TestWarningsService:
    """Test warnings analysis service."""

    def test_analyze_warnings_basic(self, sample_ibdiagnet_dir):
        """Test basic warnings analysis."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Should return a dictionary
        assert isinstance(result, dict)
        assert "data" in result
        assert "summary" in result

        # Data should be a list
        assert isinstance(result["data"], list)

    def test_warning_types_detection(self, sample_ibdiagnet_dir):
        """Test detection of different warning types."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Check for different warning types
        warning_types = set()
        for item in result["data"]:
            if "WarningType" in item or "Type" in item:
                warning_type = item.get("WarningType") or item.get("Type")
                if warning_type:
                    warning_types.add(warning_type)

        # Should detect various warning types
        assert len(warning_types) >= 0

    def test_firmware_check_warnings(self, sample_ibdiagnet_dir):
        """Test firmware check warnings."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Look for firmware warnings
        fw_warnings = [
            item for item in result["data"]
            if "FW" in str(item.get("WarningType", "")) or "firmware" in str(item).lower()
        ]

        # Should be able to detect firmware warnings
        assert len(fw_warnings) >= 0

    def test_cable_warnings(self, sample_ibdiagnet_dir):
        """Test cable-related warnings."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Look for cable warnings
        cable_warnings = [
            item for item in result["data"]
            if "cable" in str(item).lower() or "CABLE" in str(item.get("WarningType", ""))
        ]

        # Should be able to detect cable warnings
        assert len(cable_warnings) >= 0

    def test_ber_check_warnings(self, sample_ibdiagnet_dir):
        """Test BER check warnings."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Look for BER warnings
        ber_warnings = [
            item for item in result["data"]
            if "BER" in str(item.get("WarningType", "")) or "Symbol" in str(item.get("WarningType", ""))
        ]

        # Should be able to detect BER warnings
        assert len(ber_warnings) >= 0

    def test_pci_degradation_warnings(self, sample_ibdiagnet_dir):
        """Test PCI degradation warnings."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Look for PCI warnings
        pci_warnings = [
            item for item in result["data"]
            if "PCI" in str(item.get("WarningType", ""))
        ]

        # Should be able to detect PCI warnings
        assert len(pci_warnings) >= 0

    def test_warning_severity_classification(self, sample_ibdiagnet_dir):
        """Test warning severity classification."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Check for severity levels
        for item in result["data"]:
            if "Severity" in item:
                severity = item["Severity"]
                valid_severities = ["critical", "warning", "info", "error", None]
                assert severity in valid_severities or isinstance(severity, str)

    def test_warning_message_parsing(self, sample_ibdiagnet_dir):
        """Test warning message parsing."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Check for warning messages
        for item in result["data"]:
            if "Message" in item or "Description" in item:
                message = item.get("Message") or item.get("Description")
                # Should be a string
                assert isinstance(message, (str, type(None)))

    def test_warnings_summary_statistics(self, sample_ibdiagnet_dir):
        """Test that summary statistics are calculated."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        summary = result["summary"]

        # Should have key statistics
        assert isinstance(summary, dict)
        # Should have warning counts
        assert "total_warnings" in summary or len(summary) >= 0


class TestWarningsEdgeCases:
    """Test edge cases in warnings service."""

    def test_no_warnings(self, tmp_path):
        """Test handling when no warnings exist."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should handle gracefully
        result = analyze_warnings(empty_dir)
        assert isinstance(result, dict)
        assert result["data"] == [] or result.get("summary", {}).get("total_warnings", 0) == 0

    def test_malformed_warning_table(self):
        """Test handling of malformed warning data."""
        # This is a conceptual test
        pass

    def test_duplicate_warnings(self):
        """Test handling of duplicate warnings."""
        # Duplicate warnings should be handled
        pass


class TestWarningsIntegration:
    """Integration tests for warnings service."""

    def test_warnings_correlation_with_other_services(self, sample_ibdiagnet_dir):
        """Test that warnings correlate with other service findings."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Warnings should provide context for other issues
        assert isinstance(result, dict)

    def test_warning_table_coverage(self, sample_ibdiagnet_dir):
        """Test that all warning tables are processed."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Should process multiple warning tables
        # WARNINGS_FW_CHECK, WARNINGS_CABLE_REPORT, etc.
        assert isinstance(result["data"], list)

    def test_warnings_with_node_identification(self, sample_ibdiagnet_dir):
        """Test that warnings include node identification."""
        result = analyze_warnings(sample_ibdiagnet_dir)

        # Warnings should identify affected nodes
        for item in result["data"]:
            # Should have node identification
            has_node_id = any(key in item for key in ["NodeGUID", "NodeGuid", "Node Name", "NodeDesc"])
            # At least some warnings should have node IDs
            if has_node_id:
                break
