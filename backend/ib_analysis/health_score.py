"""Health Score calculation for InfiniBand network analysis."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import pandas as pd

from .anomaly import (
    AnomlyType,
    IBH_ANOMALY_AGG_COL,
    IBH_ANOMALY_AGG_WEIGHT
)
from .core.explanations import get_issue_guide, ExplanationKey


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    """Represents a single network issue."""
    severity: Severity
    category: str
    description: str
    node_guid: str
    port_number: int
    weight: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    """Complete health report for a network analysis."""
    score: int  # 0-100
    grade: str  # A, B, C, D, F
    status: str  # Healthy, Warning, Critical
    total_nodes: int
    total_ports: int
    issues: List[Issue] = field(default_factory=list)
    category_scores: Dict[str, int] = field(default_factory=dict)
    summary: Dict[str, int] = field(default_factory=dict)


# Anomaly type to category mapping
ANOMALY_CATEGORIES = {
    AnomlyType.IBH_HIGH_XMIT_WAIT: ("congestion", Severity.WARNING),
    AnomlyType.IBH_HCA_BP: ("congestion", Severity.WARNING),
    AnomlyType.IBH_PLAIN_UNB: ("balance", Severity.INFO),
    AnomlyType.IBH_AR_UNB: ("balance", Severity.INFO),
    AnomlyType.IBH_DRIB_OUTLIER_SW: ("anomaly", Severity.WARNING),
    AnomlyType.IBH_HIGH_SYMBOL_BER: ("ber", Severity.CRITICAL),
    AnomlyType.IBH_UNUSUAL_BER: ("ber", Severity.WARNING),
    AnomlyType.IBH_OUTLIER: ("config", Severity.INFO),
    AnomlyType.IBH_RED_FLAG: ("errors", Severity.CRITICAL),
    AnomlyType.IBH_UNUSUAL_RTT_NUM: ("congestion", Severity.INFO),
    AnomlyType.IBH_HIGH_MIN_RTT: ("latency", Severity.WARNING),
    AnomlyType.IBH_ASYM_TOPO: ("topology", Severity.WARNING),
}

# Category weights for overall score (must sum to 100)
CATEGORY_WEIGHTS = {
    "ber": 25,
    "errors": 25,
    "congestion": 20,
    "topology": 10,
    "latency": 10,
    "balance": 5,
    "config": 3,
    "anomaly": 2,
}

# Severity multipliers for score deduction
SEVERITY_MULTIPLIERS = {
    Severity.CRITICAL: 3.0,
    Severity.WARNING: 1.5,
    Severity.INFO: 0.5,
}


def calculate_health_score(
    analysis_data: List[Dict],
    cable_data: List[Dict],
    xmit_data: List[Dict],
    ber_data: List[Dict],
    hca_data: List[Dict],
) -> HealthReport:
    """
    Calculate overall network health score from analysis results.

    Returns a HealthReport with score 0-100 and categorized issues.
    """
    issues: List[Issue] = []
    category_deductions: Dict[str, float] = {cat: 0.0 for cat in CATEGORY_WEIGHTS}

    # Process each data source
    all_data = [
        ("brief", analysis_data),
        ("cable", cable_data),
        ("xmit", xmit_data),
        ("ber", ber_data),
        ("hca", hca_data),
    ]

    total_ports = 0
    node_guids = set()

    for source, data in all_data:
        if not data:
            continue

        for row in data:
            node_guid = row.get("NodeGUID", "")
            port_number = row.get("PortNumber", 0)

            if node_guid:
                node_guids.add(node_guid)
            total_ports += 1

            # Check for anomaly columns
            anomaly_str = row.get(IBH_ANOMALY_AGG_COL, "")
            anomaly_weight = row.get(IBH_ANOMALY_AGG_WEIGHT, 0)

            if anomaly_str and anomaly_weight > 0:
                # Parse anomaly types from the aggregated string
                anomaly_types = [a.strip() for a in anomaly_str.split(",") if a.strip()]

                for anomaly_name in anomaly_types:
                    # Find matching anomaly type
                    matched_type = None
                    for atype in AnomlyType:
                        if atype.value in anomaly_name or anomaly_name in atype.value:
                            matched_type = atype
                            break

                    if matched_type and matched_type in ANOMALY_CATEGORIES:
                        category, severity = ANOMALY_CATEGORIES[matched_type]

                        issue = Issue(
                            severity=severity,
                            category=category,
                            description=anomaly_name,
                            node_guid=node_guid,
                            port_number=port_number,
                            weight=anomaly_weight,
                            details={"source": source}
                        )
                        issues.append(issue)
                        _attach_issue_guide(issue, anomaly_type=matched_type)

                        # Calculate deduction
                        deduction = anomaly_weight * SEVERITY_MULTIPLIERS[severity]
                        category_deductions[category] += deduction

            # Check for specific high-value indicators
            _check_specific_issues(row, source, issues, category_deductions)

    # Calculate category scores (0-100 each)
    category_scores = {}
    for category, weight in CATEGORY_WEIGHTS.items():
        # Normalize deduction to category weight
        max_deduction = weight * 2  # Allow up to 2x weight in deductions
        deduction = min(category_deductions[category], max_deduction)
        category_scores[category] = max(0, int(100 - (deduction / max_deduction) * 100))

    # Calculate overall score
    total_score = 0
    for category, weight in CATEGORY_WEIGHTS.items():
        total_score += (category_scores[category] * weight) / 100

    score = max(0, min(100, int(total_score)))

    # Determine grade and status
    grade, status = _get_grade_and_status(score)

    # Count issues by severity
    summary = {
        "critical": len([i for i in issues if i.severity == Severity.CRITICAL]),
        "warning": len([i for i in issues if i.severity == Severity.WARNING]),
        "info": len([i for i in issues if i.severity == Severity.INFO]),
    }

    return HealthReport(
        score=score,
        grade=grade,
        status=status,
        total_nodes=len(node_guids),
        total_ports=total_ports,
        issues=issues,
        category_scores=category_scores,
        summary=summary,
    )


def _check_specific_issues(
    row: Dict,
    source: str,
    issues: List[Issue],
    category_deductions: Dict[str, float]
):
    """Check for specific high-value indicators not in anomaly columns."""
    node_guid = row.get("NodeGUID", "")
    port_number = row.get("PortNumber", 0)

    # High temperature check
    temp = row.get("Temperature (c)", row.get("Temperature", 0))
    if temp and isinstance(temp, (int, float)) and temp >= 70:
        severity = Severity.CRITICAL if temp >= 80 else Severity.WARNING
        issue = Issue(
            severity=severity,
            category="errors",
            description=f"High temperature: {temp}C",
            node_guid=node_guid,
            port_number=port_number,
            weight=temp - 60,
            details={"temperature": temp, "source": source}
        )
        issues.append(issue)
        kb_key = (
            ExplanationKey.HIGH_TEMPERATURE
            if severity == Severity.CRITICAL else ExplanationKey.MODERATE_TEMPERATURE
        )
        _attach_issue_guide(issue, custom_key=kb_key)
        category_deductions["errors"] += (temp - 60) * SEVERITY_MULTIPLIERS[severity]

    # Link down check
    link_down = row.get("LinkDownedCounter", row.get("LinkDownedCounterExt", 0))
    if link_down and int(link_down) > 0:
        issue = Issue(
            severity=Severity.CRITICAL,
            category="errors",
            description=f"Link down events: {link_down}",
            node_guid=node_guid,
            port_number=port_number,
            weight=float(link_down),
            details={"link_down_count": link_down, "source": source}
        )
        issues.append(issue)
        _attach_issue_guide(issue, custom_key=ExplanationKey.LINK_DOWN)
        category_deductions["errors"] += float(link_down) * SEVERITY_MULTIPLIERS[Severity.CRITICAL]

    # Port state check
    port_state = row.get("PortState", "")
    if port_state and "Active" not in str(port_state) and "4" not in str(port_state):
        issue = Issue(
            severity=Severity.WARNING,
            category="topology",
            description=f"Port not active: {port_state}",
            node_guid=node_guid,
            port_number=port_number,
            weight=1.0,
            details={"port_state": port_state, "source": source}
        )
        issues.append(issue)
        _attach_issue_guide(issue, custom_key=ExplanationKey.PORT_INACTIVE)
        category_deductions["topology"] += SEVERITY_MULTIPLIERS[Severity.WARNING]


def _get_grade_and_status(score: int) -> tuple:
    """Get letter grade and status from score."""
    if score >= 90:
        return "A", "Healthy"
    elif score >= 80:
        return "B", "Healthy"
    elif score >= 70:
        return "C", "Warning"
    elif score >= 60:
        return "D", "Warning"
    else:
        return "F", "Critical"


def health_report_to_dict(report: HealthReport) -> Dict[str, Any]:
    """Convert HealthReport to dictionary for JSON serialization."""
    return {
        "score": report.score,
        "grade": report.grade,
        "status": report.status,
        "total_nodes": report.total_nodes,
        "total_ports": report.total_ports,
        "summary": report.summary,
        "category_scores": report.category_scores,
        "issues": [
            {
                "severity": issue.severity.value,
                "category": issue.category,
                "description": issue.description,
                "node_guid": issue.node_guid,
                "port_number": issue.port_number,
                "weight": issue.weight,
                "details": issue.details,
            }
            for issue in report.issues
        ],
    }


def _attach_issue_guide(
    issue: Issue,
    *,
    anomaly_type: Optional[AnomlyType] = None,
    custom_key: Optional[str] = None,
) -> None:
    """Attach NVIDIA guide metadata to the issue when available."""
    guide = get_issue_guide(anomaly_type=anomaly_type, custom_key=custom_key)
    if guide:
        issue.details = issue.details or {}
        issue.details.setdefault("kb", guide)
