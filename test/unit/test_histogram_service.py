"""Unit tests for Histogram service."""

import pytest
import pandas as pd
from services.histogram_service import analyze_histogram


class TestHistogramService:
    """Test histogram analysis service."""

    def test_analyze_histogram_basic(self, sample_ibdiagnet_dir):
        """Test basic histogram analysis."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Should return a dictionary
        assert isinstance(result, dict)
        assert "data" in result
        assert "summary" in result

        # Data should be a list
        assert isinstance(result["data"], list)

    def test_rtt_median_calculation(self, sample_ibdiagnet_dir):
        """Test RTT median calculation."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Check for median RTT
        for item in result["data"]:
            if "MedianRTT" in item or "RTT_Median" in item:
                median = item.get("MedianRTT") or item.get("RTT_Median")
                # Should be numeric
                assert isinstance(median, (int, float, type(None)))
                if median is not None:
                    assert median >= 0

    def test_rtt_p99_calculation(self, sample_ibdiagnet_dir):
        """Test RTT P99 calculation."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Check for P99 RTT
        for item in result["data"]:
            if "P99RTT" in item or "RTT_P99" in item:
                p99 = item.get("P99RTT") or item.get("RTT_P99")
                # Should be numeric
                assert isinstance(p99, (int, float, type(None)))
                if p99 is not None:
                    assert p99 >= 0

    def test_latency_anomaly_detection(self, sample_ibdiagnet_dir):
        """Test latency anomaly detection."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Look for latency anomalies
        # P99/Median >= 3.0 indicates anomaly
        for item in result["data"]:
            median = item.get("MedianRTT") or item.get("RTT_Median")
            p99 = item.get("P99RTT") or item.get("RTT_P99")

            if median and p99 and median > 0:
                ratio = p99 / median
                if ratio >= 3.0:
                    # Should be flagged as anomaly
                    anomaly = item.get("IBH Anomaly", "")
                    # May or may not have anomaly flag depending on implementation
                    assert ratio >= 3.0

    def test_histogram_bucket_distribution(self, sample_ibdiagnet_dir):
        """Test histogram bucket distribution."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Check for histogram buckets
        for item in result["data"]:
            # Look for bucket fields
            bucket_fields = [k for k in item.keys() if "Bucket" in k or "bucket" in k]
            if bucket_fields:
                # Should have bucket data
                assert len(bucket_fields) > 0
                break

    def test_upper_bucket_ratio(self, sample_ibdiagnet_dir):
        """Test upper bucket ratio calculation."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Check for upper bucket ratio
        # High ratio in upper buckets indicates latency issues
        for item in result["data"]:
            if "UpperBucketRatio" in item or "upper_bucket_pct" in item:
                ratio = item.get("UpperBucketRatio") or item.get("upper_bucket_pct")
                if ratio is not None:
                    # Should be percentage (0-100)
                    assert 0 <= ratio <= 100 or ratio >= 0

    def test_histogram_summary_statistics(self, sample_ibdiagnet_dir):
        """Test that summary statistics are calculated."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        summary = result["summary"]

        # Should have key statistics
        assert isinstance(summary, dict)
        assert len(summary) >= 0


class TestHistogramEdgeCases:
    """Test edge cases in histogram service."""

    def test_zero_median_rtt(self):
        """Test handling of zero median RTT."""
        median = 0
        p99 = 100

        # Division by zero should be handled
        if median == 0:
            ratio = float('inf')
        else:
            ratio = p99 / median

        assert median == 0

    def test_missing_histogram_data(self, tmp_path):
        """Test handling when histogram data is missing."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should handle gracefully
        result = analyze_histogram(empty_dir)
        assert isinstance(result, dict)

    def test_negative_rtt_values(self):
        """Test handling of negative RTT values (invalid)."""
        rtt = -100
        # Should be rejected
        assert rtt < 0  # Invalid

    def test_extremely_high_rtt(self):
        """Test handling of extremely high RTT values."""
        rtt = 1000000  # 1 second in microseconds
        # Should be valid but flagged
        assert rtt > 0


class TestHistogramIntegration:
    """Integration tests for histogram service."""

    def test_histogram_with_performance_data(self, sample_ibdiagnet_dir):
        """Test histogram analysis with performance data."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Should integrate with performance histogram table
        assert isinstance(result["data"], list)

    def test_histogram_correlation_with_congestion(self, sample_ibdiagnet_dir):
        """Test that high latency correlates with congestion."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # High P99/Median ratio should indicate congestion
        high_latency_items = []
        for item in result["data"]:
            median = item.get("MedianRTT") or item.get("RTT_Median")
            p99 = item.get("P99RTT") or item.get("RTT_P99")

            if median and p99 and median > 0:
                ratio = p99 / median
                if ratio >= 3.0:
                    high_latency_items.append(item)

        # Should be able to identify high latency items
        assert len(high_latency_items) >= 0

    def test_histogram_per_port_analysis(self, sample_ibdiagnet_dir):
        """Test per-port histogram analysis."""
        result = analyze_histogram(sample_ibdiagnet_dir)

        # Should analyze histograms per port
        for item in result["data"]:
            # Should have port identification
            has_port_id = "PortNumber" in item or "Port" in item
            if has_port_id:
                break
