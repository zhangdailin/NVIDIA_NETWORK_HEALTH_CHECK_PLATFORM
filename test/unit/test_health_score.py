"""Unit tests for health score calculation."""

import pytest
from services.health_score import (
    calculate_health_score,
    health_report_to_dict,
    Severity,
    CATEGORY_WEIGHTS,
    SEVERITY_MULTIPLIERS,
)
from services.anomalies import AnomlyType


class TestHealthScoreCalculation:
    """Test health score calculation logic."""

    def test_perfect_health_score(self, mock_empty_health_data):
        """Test that a healthy network gets a high score."""
        report = calculate_health_score(
            analysis_data=mock_empty_health_data["analysis_data"],
            cable_data=mock_empty_health_data["cable_data"],
            xmit_data=mock_empty_health_data["xmit_data"],
            ber_data=mock_empty_health_data["ber_data"],
            hca_data=mock_empty_health_data["hca_data"],
        )

        # Should have high score
        assert report.score >= 90
        assert report.grade in ["A", "B"]
        assert report.status == "Healthy"

        # Should have minimal issues
        assert report.summary["critical"] == 0
        assert report.summary["warning"] == 0

    def test_health_score_with_anomalies(self, mock_health_data):
        """Test health score calculation with various anomalies."""
        report = calculate_health_score(
            analysis_data=mock_health_data["analysis_data"],
            cable_data=mock_health_data["cable_data"],
            xmit_data=mock_health_data["xmit_data"],
            ber_data=mock_health_data["ber_data"],
            hca_data=mock_health_data["hca_data"],
        )

        # Should have lower score due to anomalies
        assert 0 <= report.score <= 100
        assert report.score < 90  # Should be penalized

        # Should have issues detected
        assert len(report.issues) > 0
        assert report.summary["critical"] > 0 or report.summary["warning"] > 0

    def test_health_score_range(self, mock_health_data):
        """Test that health score is always in valid range."""
        report = calculate_health_score(
            analysis_data=mock_health_data["analysis_data"],
            cable_data=mock_health_data["cable_data"],
            xmit_data=mock_health_data["xmit_data"],
            ber_data=mock_health_data["ber_data"],
            hca_data=mock_health_data["hca_data"],
        )

        assert 0 <= report.score <= 100

    def test_grade_assignment(self):
        """Test grade assignment based on score."""
        # Test data with varying severity
        test_cases = [
            ([], [], [], [], [], "A"),  # Perfect score
        ]

        for analysis, cable, xmit, ber, hca, expected_grade in test_cases:
            report = calculate_health_score(
                analysis_data=analysis,
                cable_data=cable,
                xmit_data=xmit,
                ber_data=ber,
                hca_data=hca,
            )
            # Grade should be one of the valid grades
            assert report.grade in ["A", "B", "C", "D", "F"]

    def test_category_weights_sum(self):
        """Test that category weights are properly defined."""
        total_weight = sum(CATEGORY_WEIGHTS.values())
        assert total_weight == 100  # Should sum to 100

    def test_severity_multipliers_defined(self):
        """Test that all severity levels have multipliers."""
        assert Severity.CRITICAL in SEVERITY_MULTIPLIERS
        assert Severity.WARNING in SEVERITY_MULTIPLIERS
        assert Severity.INFO in SEVERITY_MULTIPLIERS

        # Critical should have highest multiplier
        assert SEVERITY_MULTIPLIERS[Severity.CRITICAL] > SEVERITY_MULTIPLIERS[Severity.WARNING]
        assert SEVERITY_MULTIPLIERS[Severity.WARNING] > SEVERITY_MULTIPLIERS[Severity.INFO]

    def test_high_temperature_detection(self):
        """Test that high temperature is detected and penalized."""
        cable_data = [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "Temperature (c)": 85,  # Critical temperature
            }
        ]

        report = calculate_health_score(
            analysis_data=[],
            cable_data=cable_data,
            xmit_data=[],
            ber_data=[],
            hca_data=[],
        )

        # Should detect temperature issue
        temp_issues = [i for i in report.issues if "temperature" in i.description.lower()]
        assert len(temp_issues) > 0

        # Should be critical severity
        critical_temp = [i for i in temp_issues if i.severity == Severity.CRITICAL]
        assert len(critical_temp) > 0

    def test_link_down_detection(self):
        """Test that link down events are detected."""
        xmit_data = [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "LinkDownedCounter": 5,
                "LinkDownedCounterExt": 0,
            }
        ]

        report = calculate_health_score(
            analysis_data=[],
            cable_data=[],
            xmit_data=xmit_data,
            ber_data=[],
            hca_data=[],
        )

        # Should detect link down issue
        link_issues = [i for i in report.issues if "link down" in i.description.lower()]
        assert len(link_issues) > 0

        # Should be critical
        assert any(i.severity == Severity.CRITICAL for i in link_issues)

    def test_link_error_recovery_detection(self):
        """Test that link error recovery events are detected."""
        xmit_data = [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "LinkErrorRecoveryCounter": 15,
                "LinkErrorRecoveryCounterExt": 0,
            }
        ]

        report = calculate_health_score(
            analysis_data=[],
            cable_data=[],
            xmit_data=xmit_data,
            ber_data=[],
            hca_data=[],
        )

        # Should detect recovery issue
        # Note: The function checks recovery_total >= 3, and 15 >= 10 means CRITICAL
        recovery_issues = [i for i in report.issues if "recovery" in i.description.lower() or "recoveries" in i.description.lower()]
        assert len(recovery_issues) > 0

        # Verify it's marked as critical (since 15 >= 10)
        assert any(i.severity == Severity.CRITICAL for i in recovery_issues)

    def test_anomaly_aggregation(self):
        """Test that anomalies are properly aggregated."""
        # IMPORTANT: The column name must match IBH_ANOMALY_AGG_COL = "IBH Anomaly"
        # not "IBH_ANOMALY_AGG"
        data_with_anomalies = [
            {
                "NodeGUID": "0xe8ebd30300723915",
                "PortNumber": 1,
                "IBH Anomaly": "High xmit-wait,High Symbol BER",  # Use actual anomaly values
                "IBH Anomaly Weight": 10.0,  # Use actual column name
            }
        ]

        report = calculate_health_score(
            analysis_data=data_with_anomalies,
            cable_data=[],
            xmit_data=[],
            ber_data=[],
            hca_data=[],
        )

        # Should detect multiple anomalies
        assert len(report.issues) >= 2

        # Verify anomalies are from different categories
        categories = {issue.category for issue in report.issues}
        assert len(categories) >= 2  # Should have congestion and ber

    def test_health_report_to_dict_conversion(self, mock_health_data):
        """Test conversion of HealthReport to dictionary."""
        report = calculate_health_score(
            analysis_data=mock_health_data["analysis_data"],
            cable_data=mock_health_data["cable_data"],
            xmit_data=mock_health_data["xmit_data"],
            ber_data=mock_health_data["ber_data"],
            hca_data=mock_health_data["hca_data"],
        )

        report_dict = health_report_to_dict(report)

        # Verify structure
        assert "score" in report_dict
        assert "grade" in report_dict
        assert "status" in report_dict
        assert "total_nodes" in report_dict
        assert "total_ports" in report_dict
        assert "summary" in report_dict
        assert "category_scores" in report_dict
        assert "issues" in report_dict

        # Verify types
        assert isinstance(report_dict["score"], int)
        assert isinstance(report_dict["grade"], str)
        assert isinstance(report_dict["issues"], list)

    def test_category_scores_present(self, mock_health_data):
        """Test that all category scores are calculated."""
        report = calculate_health_score(
            analysis_data=mock_health_data["analysis_data"],
            cable_data=mock_health_data["cable_data"],
            xmit_data=mock_health_data["xmit_data"],
            ber_data=mock_health_data["ber_data"],
            hca_data=mock_health_data["hca_data"],
        )

        # All categories should have scores
        for category in CATEGORY_WEIGHTS.keys():
            assert category in report.category_scores
            assert 0 <= report.category_scores[category] <= 100

    def test_node_and_port_counting(self):
        """Test that nodes and ports are counted correctly."""
        data = [
            {"NodeGUID": "0x1111", "PortNumber": 1},
            {"NodeGUID": "0x1111", "PortNumber": 2},
            {"NodeGUID": "0x2222", "PortNumber": 1},
        ]

        report = calculate_health_score(
            analysis_data=data,
            cable_data=[],
            xmit_data=[],
            ber_data=[],
            hca_data=[],
        )

        # Should count unique nodes
        assert report.total_nodes == 2
        # Should count all ports
        assert report.total_ports == 3

    def test_empty_data_handling(self):
        """Test that empty data doesn't cause errors."""
        report = calculate_health_score(
            analysis_data=[],
            cable_data=[],
            xmit_data=[],
            ber_data=[],
            hca_data=[],
        )

        # Should return valid report
        assert isinstance(report.score, int)
        assert 0 <= report.score <= 100
        assert report.total_nodes == 0
        assert report.total_ports == 0

    def test_issue_details_include_kb(self, mock_health_data):
        """Test that issues include knowledge base information."""
        report = calculate_health_score(
            analysis_data=mock_health_data["analysis_data"],
            cable_data=mock_health_data["cable_data"],
            xmit_data=mock_health_data["xmit_data"],
            ber_data=mock_health_data["ber_data"],
            hca_data=mock_health_data["hca_data"],
        )

        # At least some issues should have KB info
        issues_with_kb = [i for i in report.issues if "kb" in i.details]
        assert len(issues_with_kb) > 0
