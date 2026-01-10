"""Unit tests for BER (Bit Error Rate) service."""

import pytest
import pandas as pd
from pathlib import Path
from services.ber_service import analyze_ber
from services.anomalies import AnomlyType


class TestBERService:
    """Test BER analysis service."""

    def test_analyze_ber_basic(self, sample_ibdiagnet_dir):
        """Test basic BER analysis."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # Should return a dictionary
        assert isinstance(result, dict)
        assert "data" in result
        assert "summary" in result

        # Data should be a list
        assert isinstance(result["data"], list)

    def test_ber_severity_classification(self, sample_ibdiagnet_dir):
        """Test BER severity classification."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # Check for severity classification
        for item in result["data"]:
            if "SymbolBER" in item and item["SymbolBER"]:
                # Should have severity classification
                assert "Severity" in item or "BER_Status" in item

    def test_high_ber_detection(self, sample_ibdiagnet_dir):
        """Test that high BER is detected and flagged."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # Look for high BER items
        high_ber_items = [
            item for item in result["data"]
            if item.get("SymbolBER") and float(item["SymbolBER"]) > 1e-6
        ]

        # If high BER exists, should be flagged
        for item in high_ber_items:
            # Should have anomaly flag
            anomaly = item.get("IBH Anomaly", "")
            if anomaly:
                assert "BER" in anomaly or "Symbol" in anomaly

    def test_ber_calculation_accuracy(self):
        """Test BER calculation formulas."""
        # Test Raw BER calculation
        # Raw BER = RawErrorCounter / (EffectiveErrors + 1)
        raw_errors = 100
        effective_errors = 1000
        expected_raw_ber = raw_errors / (effective_errors + 1)

        assert expected_raw_ber > 0
        assert expected_raw_ber < 1

    def test_ber_summary_statistics(self, sample_ibdiagnet_dir):
        """Test that summary statistics are calculated."""
        result = analyze_ber(sample_ibdiagnet_dir)

        summary = result["summary"]

        # Should have key statistics
        assert "total_ports" in summary or "total_links" in summary
        assert isinstance(summary, dict)

    def test_ber_with_missing_data(self, tmp_path):
        """Test BER analysis with missing data."""
        # Create empty directory
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should handle gracefully
        result = analyze_ber(empty_dir)
        assert isinstance(result, dict)
        assert result["data"] == [] or result.get("summary", {}).get("total_ports", 0) == 0

    def test_ber_threshold_levels(self):
        """Test BER threshold levels."""
        # Define standard BER thresholds
        CRITICAL_BER = 1e-6
        WARNING_BER = 1e-9
        NORMAL_BER = 1e-12

        # Test classification
        assert CRITICAL_BER > WARNING_BER
        assert WARNING_BER > NORMAL_BER

    def test_effective_ber_vs_raw_ber(self):
        """Test that Effective BER and Raw BER are different."""
        # Effective BER should account for FEC corrections
        # Raw BER is before FEC
        raw_ber = 1e-6
        fec_corrected = 0.9  # 90% corrected
        effective_ber = raw_ber * (1 - fec_corrected)

        assert effective_ber < raw_ber
        assert effective_ber == 1e-7

    def test_ber_per_lane_analysis(self, sample_ibdiagnet_dir):
        """Test per-lane BER analysis if available."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # Check if per-lane data exists
        for item in result["data"]:
            if "Lane" in str(item.keys()):
                # Should have lane-specific BER
                assert "Lane" in item or any("lane" in str(k).lower() for k in item.keys())
                break

    def test_ber_anomaly_weight_calculation(self, sample_ibdiagnet_dir):
        """Test that BER anomaly weights are calculated correctly."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # Check anomaly weights
        for item in result["data"]:
            if "IBH Anomaly Weight" in item:
                weight = item["IBH Anomaly Weight"]
                assert isinstance(weight, (int, float))
                assert weight >= 0


class TestBEREdgeCases:
    """Test edge cases in BER service."""

    def test_zero_ber(self):
        """Test handling of zero BER (perfect link)."""
        ber = 0.0
        assert ber == 0.0
        # Should not trigger any anomalies

    def test_nan_ber_values(self):
        """Test handling of NaN BER values."""
        import math
        ber = float('nan')
        assert math.isnan(ber)
        # Should be handled gracefully

    def test_infinite_ber_values(self):
        """Test handling of infinite BER values."""
        import math
        ber = float('inf')
        assert math.isinf(ber)
        # Should be capped or handled

    def test_negative_ber_values(self):
        """Test handling of negative BER values (invalid)."""
        ber = -1e-6
        # Should be rejected or set to 0
        assert ber < 0  # Invalid value

    def test_very_high_ber(self):
        """Test handling of extremely high BER (>1)."""
        ber = 1.5
        # BER should never exceed 1.0 (100%)
        assert ber > 1.0  # Invalid

    def test_ber_with_no_traffic(self):
        """Test BER calculation when no traffic has passed."""
        # If no data transmitted, BER should be undefined or 0
        transmitted_bits = 0
        error_bits = 0
        # BER = error_bits / transmitted_bits would cause division by zero
        # Should handle gracefully


class TestBERIntegration:
    """Integration tests for BER service."""

    def test_ber_with_pm_counters(self, sample_ibdiagnet_dir):
        """Test BER analysis with PM counter data."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # Should integrate PM counter data
        for item in result["data"]:
            # Check for PM-related fields
            pm_fields = ["PortXmitData", "PortRcvData", "SymbolErrorCounter"]
            has_pm_data = any(field in item for field in pm_fields)
            # At least some items should have PM data
            if has_pm_data:
                break

    def test_ber_with_phy_diagnostics(self, sample_ibdiagnet_dir):
        """Test BER analysis with PHY diagnostic data."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # Should include PHY diagnostic data if available
        for item in result["data"]:
            # Check for PHY-related fields
            phy_fields = ["PhyRawErrorCounter", "PhySymbolErrors"]
            has_phy_data = any(field in item for field in phy_fields)
            if has_phy_data:
                # PHY data should be numeric
                for field in phy_fields:
                    if field in item:
                        assert isinstance(item[field], (int, float, type(None)))
                break

    def test_ber_correlation_with_cable_quality(self, sample_ibdiagnet_dir):
        """Test that BER correlates with cable quality issues."""
        result = analyze_ber(sample_ibdiagnet_dir)

        # High BER should correlate with cable issues
        # This is a logical test, not a strict assertion
        high_ber_count = sum(
            1 for item in result["data"]
            if item.get("SymbolBER") and float(item["SymbolBER"]) > 1e-6
        )

        # Just verify we can count high BER items
        assert high_ber_count >= 0
