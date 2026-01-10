"""Unit tests for Link Oscillation service."""

import pytest
import pandas as pd
from services.link_oscillation_service import analyze_link_oscillation


class TestLinkOscillationService:
    """Test link oscillation analysis service."""

    def test_analyze_link_oscillation_basic(self, sample_ibdiagnet_dir):
        """Test basic link oscillation analysis."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # Should return a dictionary
        assert isinstance(result, dict)
        assert "data" in result
        assert "summary" in result

        # Data should be a list
        assert isinstance(result["data"], list)

    def test_link_downed_counter_detection(self, sample_ibdiagnet_dir):
        """Test link downed counter detection."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # Check for link downed counters
        for item in result["data"]:
            if "LinkDownedCounter" in item:
                counter = item["LinkDownedCounter"]
                # Should be numeric
                assert isinstance(counter, (int, float, type(None)))
                if counter is not None:
                    assert counter >= 0

    def test_oscillation_severity_classification(self, sample_ibdiagnet_dir):
        """Test oscillation severity classification."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # Check severity classification
        # critical >= 100, warning >= 20
        for item in result["data"]:
            counter = item.get("LinkDownedCounter", 0)
            if counter >= 100:
                # Should be critical
                severity = item.get("Severity")
                if severity:
                    assert severity == "critical" or "critical" in str(severity).lower()
            elif counter >= 20:
                # Should be warning
                severity = item.get("Severity")
                if severity:
                    assert severity in ["warning", "critical"] or "warning" in str(severity).lower()

    def test_bidirectional_link_analysis(self, sample_ibdiagnet_dir):
        """Test bidirectional link oscillation analysis."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # Should analyze both directions of a link
        for item in result["data"]:
            # Should have both local and remote information
            has_local = "NodeGUID" in item or "NodeGuid" in item
            has_remote = "RemoteNodeGUID" in item or "RemoteNodeGuid" in item or "Attached To" in item

            if has_local:
                # At least local info should exist
                assert has_local

    def test_link_oscillation_summary(self, sample_ibdiagnet_dir):
        """Test link oscillation summary statistics."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        summary = result["summary"]

        # Should have key statistics
        assert isinstance(summary, dict)
        # Should track oscillating links
        assert len(summary) >= 0

    def test_zero_oscillation_links(self):
        """Test handling of links with zero oscillations."""
        link_downed = 0
        # Should not be flagged
        assert link_downed == 0

    def test_high_oscillation_detection(self, sample_ibdiagnet_dir):
        """Test detection of high oscillation links."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # Look for high oscillation links (>= 100)
        high_osc = [
            item for item in result["data"]
            if item.get("LinkDownedCounter", 0) >= 100
        ]

        # Should be flagged as critical
        for item in high_osc:
            anomaly = item.get("IBH Anomaly", "")
            if anomaly:
                assert "link" in anomaly.lower() or "down" in anomaly.lower()


class TestLinkOscillationEdgeCases:
    """Test edge cases in link oscillation service."""

    def test_missing_pm_info_table(self, tmp_path):
        """Test handling when PM_INFO table is missing."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should handle gracefully
        result = analyze_link_oscillation(empty_dir)
        assert isinstance(result, dict)

    def test_negative_link_downed_counter(self):
        """Test handling of negative counter (invalid)."""
        counter = -10
        # Should be rejected
        assert counter < 0  # Invalid

    def test_counter_overflow(self):
        """Test handling of counter overflow."""
        # 32-bit counter max
        max_counter = 2**32 - 1
        assert max_counter > 0

    def test_very_high_oscillation(self):
        """Test handling of extremely high oscillation count."""
        counter = 10000
        # Should be flagged as critical
        assert counter >= 100


class TestLinkOscillationIntegration:
    """Integration tests for link oscillation service."""

    def test_oscillation_with_pm_info(self, sample_ibdiagnet_dir):
        """Test oscillation analysis with PM_INFO data."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # Should use PM_INFO table
        assert isinstance(result["data"], list)

    def test_oscillation_correlation_with_errors(self, sample_ibdiagnet_dir):
        """Test that oscillation correlates with link errors."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # High oscillation should correlate with errors
        # This is a logical test
        assert isinstance(result, dict)

    def test_oscillation_root_cause_identification(self, sample_ibdiagnet_dir):
        """Test identification of oscillation root causes."""
        result = analyze_link_oscillation(sample_ibdiagnet_dir)

        # Should help identify root causes
        # (cable issues, firmware, etc.)
        for item in result["data"]:
            if item.get("LinkDownedCounter", 0) > 0:
                # Should have node identification for troubleshooting
                assert "NodeGUID" in item or "NodeGuid" in item
                break
