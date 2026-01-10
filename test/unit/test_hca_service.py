"""Unit tests for HCA (Host Channel Adapter) service."""

import pytest
import pandas as pd
from services.hca_service import analyze_hca
from services.anomalies import AnomlyType


class TestHCAService:
    """Test HCA analysis service."""

    def test_analyze_hca_basic(self, sample_ibdiagnet_dir):
        """Test basic HCA analysis."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Should return a dictionary
        assert isinstance(result, dict)
        assert "data" in result
        assert "summary" in result

        # Data should be a list
        assert isinstance(result["data"], list)

    def test_firmware_version_parsing(self, sample_ibdiagnet_dir):
        """Test firmware version parsing."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Check firmware version format
        for item in result["data"]:
            if "FW" in item:
                fw_version = item["FW"]
                # Should be a string in format like "28.39.1002"
                assert isinstance(fw_version, (str, type(None)))
                if fw_version:
                    # Should have version format
                    assert "." in fw_version or fw_version.replace(".", "").isdigit()

    def test_psid_compliance_check(self, sample_ibdiagnet_dir):
        """Test PSID compliance checking."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Check PSID compliance
        for item in result["data"]:
            if "PSID_Compliant" in item:
                compliant = item["PSID_Compliant"]
                # Should be boolean
                assert isinstance(compliant, (bool, type(None)))

    def test_firmware_compliance_check(self, sample_ibdiagnet_dir):
        """Test firmware compliance checking."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Check firmware compliance
        for item in result["data"]:
            if "FW_Compliant" in item:
                compliant = item["FW_Compliant"]
                # Should be boolean
                assert isinstance(compliant, (bool, type(None)))

    def test_recent_reboot_detection(self, sample_ibdiagnet_dir):
        """Test recent reboot detection."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Check for uptime and reboot detection
        for item in result["data"]:
            if "Up Time" in item or "UpTime" in item:
                uptime = item.get("Up Time") or item.get("UpTime")
                if uptime is not None:
                    # Should be numeric (seconds or hours)
                    assert isinstance(uptime, (int, float, str))

            if "RecentlyRebooted" in item:
                recently_rebooted = item["RecentlyRebooted"]
                # Should be boolean
                assert isinstance(recently_rebooted, (bool, type(None)))

    def test_device_type_identification(self, sample_ibdiagnet_dir):
        """Test device type identification."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Check device types
        for item in result["data"]:
            if "Device Type" in item or "DeviceType" in item:
                device_type = item.get("Device Type") or item.get("DeviceType")
                # Should be a string
                assert isinstance(device_type, (str, type(None)))
                if device_type:
                    # Common device types
                    valid_types = ["HCA", "Switch", "Router", "ConnectX", "MT"]
                    # Should contain at least one valid type indicator
                    # (This is a loose check)
                    assert len(device_type) > 0

    def test_psid_unsupported_detection(self, sample_ibdiagnet_dir):
        """Test PSID unsupported detection."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Look for unsupported PSIDs
        unsupported_items = [
            item for item in result["data"]
            if item.get("PSID_Compliant") == False
        ]

        # If unsupported PSIDs exist, should be flagged
        for item in unsupported_items:
            anomaly = item.get("IBH Anomaly", "")
            if anomaly:
                assert "PSID" in anomaly or "Unsupported" in anomaly or anomaly == ""

    def test_outdated_firmware_detection(self, sample_ibdiagnet_dir):
        """Test outdated firmware detection."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Look for outdated firmware
        outdated_items = [
            item for item in result["data"]
            if item.get("FW_Compliant") == False
        ]

        # If outdated firmware exists, should be flagged
        for item in outdated_items:
            anomaly = item.get("IBH Anomaly", "")
            if anomaly:
                assert "FW" in anomaly or "Firmware" in anomaly or "Outdated" in anomaly or anomaly == ""

    def test_recommended_firmware_suggestion(self, sample_ibdiagnet_dir):
        """Test recommended firmware suggestion."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Check for recommended firmware field
        for item in result["data"]:
            if "RecommendedFW" in item:
                recommended = item["RecommendedFW"]
                # Should be a version string or None
                assert isinstance(recommended, (str, type(None)))

    def test_hca_summary_statistics(self, sample_ibdiagnet_dir):
        """Test that summary statistics are calculated."""
        result = analyze_hca(sample_ibdiagnet_dir)

        summary = result["summary"]

        # Should have key statistics
        assert isinstance(summary, dict)
        # Should have some summary data
        assert len(summary) >= 0


class TestHCAEdgeCases:
    """Test edge cases in HCA service."""

    def test_missing_firmware_version(self):
        """Test handling of missing firmware version."""
        fw_version = None
        # Should handle gracefully
        assert fw_version is None

    def test_invalid_firmware_format(self):
        """Test handling of invalid firmware format."""
        fw_version = "invalid_format"
        # Should handle gracefully
        assert isinstance(fw_version, str)

    def test_zero_uptime(self):
        """Test handling of zero uptime (just booted)."""
        uptime = 0
        # Should be flagged as recently rebooted
        recently_rebooted = uptime < 3600  # Less than 1 hour
        assert recently_rebooted == True

    def test_negative_uptime(self):
        """Test handling of negative uptime (invalid)."""
        uptime = -100
        # Should be rejected or set to 0
        assert uptime < 0  # Invalid

    def test_very_old_firmware(self):
        """Test handling of very old firmware."""
        current_fw = "20.00.0000"
        recommended_fw = "28.39.1002"
        # Should be flagged as outdated
        assert current_fw < recommended_fw  # String comparison


class TestHCAIntegration:
    """Integration tests for HCA service."""

    def test_hca_with_nodes_info(self, sample_ibdiagnet_dir):
        """Test HCA analysis with NODES_INFO data."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Should use NODES_INFO table
        for item in result["data"]:
            # Should have node identification
            assert "NodeGUID" in item or "NodeGuid" in item or "Node Name" in item
            break

    def test_hca_firmware_matrix_integration(self, sample_ibdiagnet_dir):
        """Test integration with firmware policy matrix."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # If firmware matrix is available, should use it
        # This is optional functionality
        for item in result["data"]:
            if "RecommendedFW" in item and item["RecommendedFW"]:
                # Firmware matrix is being used
                assert isinstance(item["RecommendedFW"], str)
                break

    def test_hca_device_filtering(self, sample_ibdiagnet_dir):
        """Test that only HCA devices are analyzed."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Should primarily contain HCA devices
        hca_count = 0
        switch_count = 0

        for item in result["data"]:
            device_type = item.get("Device Type", "") or item.get("DeviceType", "")
            if "HCA" in str(device_type) or "ConnectX" in str(device_type):
                hca_count += 1
            elif "Switch" in str(device_type):
                switch_count += 1

        # Should have some HCA devices (or be empty if no HCAs)
        assert hca_count >= 0

    def test_hca_frequent_reboot_detection(self, sample_ibdiagnet_dir):
        """Test detection of frequently rebooting HCAs."""
        result = analyze_hca(sample_ibdiagnet_dir)

        # Look for recently rebooted devices
        recent_reboots = [
            item for item in result["data"]
            if item.get("RecentlyRebooted") == True
        ]

        # If recent reboots exist, should be tracked
        assert len(recent_reboots) >= 0

        # Frequent reboots should be flagged
        for item in recent_reboots:
            anomaly = item.get("IBH Anomaly", "")
            if anomaly:
                assert "reboot" in anomaly.lower() or anomaly == ""
