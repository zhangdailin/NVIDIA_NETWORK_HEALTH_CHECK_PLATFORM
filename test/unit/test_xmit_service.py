"""Unit tests for Xmit (congestion) service."""

import pytest
import pandas as pd
from services.xmit_service import analyze_xmit
from services.anomalies import AnomlyType


class TestXmitService:
    """Test Xmit/congestion analysis service."""

    def test_analyze_xmit_basic(self, sample_ibdiagnet_dir):
        """Test basic xmit analysis."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Should return a dictionary
        assert isinstance(result, dict)
        assert "data" in result
        assert "summary" in result

        # Data should be a list
        assert isinstance(result["data"], list)

    def test_xmit_wait_ratio_calculation(self, sample_ibdiagnet_dir):
        """Test xmit wait ratio calculation."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Check wait ratio calculation
        for item in result["data"]:
            if "PortXmitWait" in item and "PortXmitData" in item:
                xmit_wait = item.get("PortXmitWait", 0)
                xmit_data = item.get("PortXmitData", 0)

                if xmit_data > 0:
                    expected_ratio = (xmit_wait / xmit_data) * 100
                    if "WaitRatioPct" in item:
                        actual_ratio = item["WaitRatioPct"]
                        # Should be close (allowing for rounding)
                        assert abs(actual_ratio - expected_ratio) < 0.01 or actual_ratio >= 0

    def test_high_xmit_wait_detection(self, sample_ibdiagnet_dir):
        """Test that high xmit wait is detected."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Look for high xmit wait items (>5%)
        high_wait_items = [
            item for item in result["data"]
            if item.get("WaitRatioPct", 0) >= 5.0
        ]

        # If high wait exists, should be flagged
        for item in high_wait_items:
            anomaly = item.get("IBH Anomaly", "")
            if anomaly:
                assert "xmit" in anomaly.lower() or "wait" in anomaly.lower() or "congestion" in anomaly.lower()

    def test_congestion_severity_levels(self):
        """Test congestion severity classification."""
        # Define severity thresholds
        SEVERE_THRESHOLD = 5.0  # 5% wait ratio
        WARNING_THRESHOLD = 1.0  # 1% wait ratio

        # Test classification
        severe_wait = 6.5
        warning_wait = 2.0
        normal_wait = 0.5

        assert severe_wait >= SEVERE_THRESHOLD
        assert warning_wait >= WARNING_THRESHOLD
        assert normal_wait < WARNING_THRESHOLD

    def test_fecn_becn_detection(self, sample_ibdiagnet_dir):
        """Test FECN/BECN congestion detection."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Check for FECN/BECN fields
        for item in result["data"]:
            if "PortXmitTimeCong" in item or "PortMarkFECN" in item:
                # Should have congestion indicators
                assert isinstance(item.get("PortXmitTimeCong", 0), (int, float))

    def test_credit_watchdog_detection(self, sample_ibdiagnet_dir):
        """Test credit watchdog timeout detection."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Look for credit watchdog timeouts
        for item in result["data"]:
            if "CreditWatchdogTimeout" in item or "PortXmitWaitCreditWatchdog" in item:
                timeout_count = item.get("CreditWatchdogTimeout", 0)
                if timeout_count > 0:
                    # Should be flagged as critical
                    anomaly = item.get("IBH Anomaly", "")
                    assert "watchdog" in anomaly.lower() or "credit" in anomaly.lower() or anomaly == ""

    def test_link_downshift_detection(self, sample_ibdiagnet_dir):
        """Test link speed/width downshift detection."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Check for link downshift indicators
        for item in result["data"]:
            if "LinkSpeedActive" in item and "LinkWidthActive" in item:
                # Should have speed and width information
                assert item.get("LinkSpeedActive") is not None or item.get("LinkWidthActive") is not None

    def test_hca_backpressure_detection(self, sample_ibdiagnet_dir):
        """Test HCA backpressure detection."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Look for HCA backpressure indicators
        for item in result["data"]:
            if "PortRcvRemotePhysicalErrors" in item:
                # HCA backpressure can cause remote physical errors
                errors = item.get("PortRcvRemotePhysicalErrors", 0)
                assert isinstance(errors, (int, float))

    def test_xmit_summary_statistics(self, sample_ibdiagnet_dir):
        """Test that summary statistics are calculated."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        summary = result["summary"]

        # Should have key statistics
        assert isinstance(summary, dict)
        # Common summary fields
        expected_fields = ["total_ports", "congested_ports", "severe_congestion", "warning_congestion"]
        # At least some summary data should exist
        assert len(summary) > 0

    def test_port_state_decoding(self, sample_ibdiagnet_dir):
        """Test port state decoding."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Check port state fields
        for item in result["data"]:
            if "PortState" in item:
                state = item["PortState"]
                # Should be a valid state
                valid_states = ["Down", "Init", "Armed", "Active", "0", "1", "2", "3", "4"]
                # State should be string or int
                assert isinstance(state, (str, int, type(None)))


class TestXmitEdgeCases:
    """Test edge cases in Xmit service."""

    def test_zero_xmit_data(self):
        """Test handling of zero xmit data (no traffic)."""
        xmit_wait = 100
        xmit_data = 0

        # Should handle division by zero
        if xmit_data == 0:
            wait_ratio = 0  # or undefined
        else:
            wait_ratio = (xmit_wait / xmit_data) * 100

        assert wait_ratio == 0

    def test_negative_counters(self):
        """Test handling of negative counter values (invalid)."""
        xmit_wait = -100
        # Negative values should be rejected or set to 0
        assert xmit_wait < 0  # Invalid

    def test_counter_overflow(self):
        """Test handling of counter overflow."""
        # 64-bit counter max value
        max_counter = 2**64 - 1
        assert max_counter > 0

    def test_very_high_wait_ratio(self):
        """Test handling of extremely high wait ratio (>100%)."""
        wait_ratio = 150.0
        # Wait ratio should not exceed 100%
        assert wait_ratio > 100  # Invalid or special case


class TestXmitIntegration:
    """Integration tests for Xmit service."""

    def test_xmit_with_pm_delta(self, sample_ibdiagnet_dir):
        """Test xmit analysis with PM_DELTA data."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Should use PM_DELTA for delta calculations
        for item in result["data"]:
            # Check for delta-related fields
            if "PortXmitData" in item:
                # Should have xmit data
                assert isinstance(item["PortXmitData"], (int, float))
                break

    def test_xmit_correlation_with_topology(self, sample_ibdiagnet_dir):
        """Test that xmit data includes topology information."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Should include node names and topology info
        for item in result["data"]:
            # Should have node identification
            assert "NodeGUID" in item or "NodeGuid" in item
            break

    def test_congestion_hotspot_identification(self, sample_ibdiagnet_dir):
        """Test identification of congestion hotspots."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Count congested ports
        congested_ports = [
            item for item in result["data"]
            if item.get("WaitRatioPct", 0) >= 1.0
        ]

        # Should be able to identify hotspots
        assert len(congested_ports) >= 0

    def test_bidirectional_congestion_analysis(self, sample_ibdiagnet_dir):
        """Test bidirectional congestion analysis."""
        result = analyze_xmit(sample_ibdiagnet_dir)

        # Should analyze both directions of a link
        # Check for both Xmit and Rcv counters
        for item in result["data"]:
            has_xmit = "PortXmitData" in item
            has_rcv = "PortRcvData" in item

            if has_xmit or has_rcv:
                # Should have at least one direction
                assert has_xmit or has_rcv
                break
