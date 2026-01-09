"""Health score calculation ported from ib_analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .anomalies import (
    AnomlyType,
    IBH_ANOMALY_AGG_COL,
    IBH_ANOMALY_AGG_WEIGHT,
)
from .explanations import ExplanationKey, get_issue_guide


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Issue:
    severity: Severity
    category: str
    description: str
    node_guid: str
    port_number: int
    weight: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthReport:
    score: int
    grade: str
    status: str
    total_nodes: int
    total_ports: int
    issues: List[Issue] = field(default_factory=list)
    category_scores: Dict[str, int] = field(default_factory=dict)
    summary: Dict[str, int] = field(default_factory=dict)


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
    AnomlyType.IBH_ASYM_TOPO: ("config", Severity.WARNING),
    AnomlyType.IBH_DUPLICATE_GUID: ("config", Severity.WARNING),
    AnomlyType.IBH_DUPLICATE_DESC: ("config", Severity.INFO),
    AnomlyType.IBH_OPTICAL_TEMP_HIGH: ("errors", Severity.WARNING),
    AnomlyType.IBH_OPTICAL_TX_BIAS: ("errors", Severity.WARNING),
    AnomlyType.IBH_OPTICAL_TX_POWER: ("errors", Severity.WARNING),
    AnomlyType.IBH_OPTICAL_RX_POWER: ("errors", Severity.WARNING),
    AnomlyType.IBH_OPTICAL_VOLTAGE: ("errors", Severity.WARNING),
    AnomlyType.IBH_FECN_ALERT: ("congestion", Severity.WARNING),
    AnomlyType.IBH_BECN_ALERT: ("congestion", Severity.WARNING),
    AnomlyType.IBH_XMIT_TIME_CONG: ("congestion", Severity.CRITICAL),
    AnomlyType.IBH_PSID_UNSUPPORTED: ("config", Severity.CRITICAL),
    AnomlyType.IBH_FW_OUTDATED: ("config", Severity.WARNING),
    AnomlyType.IBH_CABLE_MISMATCH: ("config", Severity.WARNING),
    AnomlyType.IBH_LINK_DOWNSHIFT: ("errors", Severity.WARNING),
    AnomlyType.IBH_CREDIT_WATCHDOG: ("congestion", Severity.CRITICAL),
    AnomlyType.IBH_FAN_FAILURE: ("errors", Severity.WARNING),
    # New anomaly types for routing, port health, links, temperature, power
    AnomlyType.IBH_ROUTING_RN_ERROR: ("congestion", Severity.WARNING),
    AnomlyType.IBH_ROUTING_FR_ERROR: ("errors", Severity.CRITICAL),
    AnomlyType.IBH_ROUTING_HBF_FALLBACK: ("congestion", Severity.WARNING),
    AnomlyType.IBH_PORT_ICRC_ERROR: ("errors", Severity.WARNING),
    AnomlyType.IBH_PORT_PARITY_ERROR: ("errors", Severity.CRITICAL),
    AnomlyType.IBH_PORT_UNHEALTHY: ("errors", Severity.CRITICAL),
    AnomlyType.IBH_LINK_ASYMMETRIC: ("errors", Severity.WARNING),
    AnomlyType.IBH_TEMP_CRITICAL: ("errors", Severity.CRITICAL),
    AnomlyType.IBH_TEMP_WARNING: ("errors", Severity.WARNING),
    AnomlyType.IBH_PSU_CRITICAL: ("errors", Severity.CRITICAL),
    AnomlyType.IBH_PSU_WARNING: ("errors", Severity.WARNING),
    # MLNX counters / performance
    AnomlyType.IBH_MLNX_COUNTER_CRITICAL: ("errors", Severity.CRITICAL),
    AnomlyType.IBH_MLNX_COUNTER_WARNING: ("errors", Severity.WARNING),
    AnomlyType.IBH_FEC_UNCORRECTABLE: ("ber", Severity.CRITICAL),
    AnomlyType.IBH_RELAY_ERROR: ("errors", Severity.WARNING),
}

CATEGORY_WEIGHTS = {
    "ber": 25,
    "errors": 25,
    "congestion": 20,
    "latency": 10,
    "balance": 5,
    "config": 13,
    "anomaly": 2,
}

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
    fan_data: Optional[List[Dict]] = None,
    histogram_data: Optional[List[Dict]] = None,
    extra_sources: Optional[List[Tuple[str, List[Dict[str, Any]]]]] = None,
) -> HealthReport:
    fan_data = fan_data or []
    histogram_data = histogram_data or []
    issues: List[Issue] = []
    deductions: Dict[str, float] = {cat: 0.0 for cat in CATEGORY_WEIGHTS}

    all_sources = [
        ("brief", analysis_data),
        ("cable", cable_data),
        ("xmit", xmit_data),
        ("ber", ber_data),
        ("hca", hca_data),
        ("fan", fan_data),
        ("histogram", histogram_data),
    ]
    if extra_sources:
        all_sources.extend(extra_sources)

    total_ports = 0
    node_guids = set()

    for source, data in all_sources:
        if not data:
            continue
        for row in data:
            node_guid = row.get("NodeGUID", "")
            port_number = row.get("PortNumber", 0)
            if node_guid:
                node_guids.add(node_guid)
            total_ports += 1

            anomaly_str = row.get(IBH_ANOMALY_AGG_COL, "")
            anomaly_weight = row.get(IBH_ANOMALY_AGG_WEIGHT, 0)
            if anomaly_str and anomaly_weight > 0:
                anomaly_types = [a.strip() for a in anomaly_str.split(",") if a.strip()]
                for anomaly_name in anomaly_types:
                    matched = _match_anomaly(anomaly_name)
                    if matched and matched in ANOMALY_CATEGORIES:
                        category, severity = ANOMALY_CATEGORIES[matched]
                        issue = Issue(
                            severity=severity,
                            category=category,
                            description=anomaly_name,
                            node_guid=node_guid,
                            port_number=port_number,
                            weight=anomaly_weight,
                            details={"source": source},
                        )
                        _attach_issue_guide(issue, anomaly_type=matched)
                        issues.append(issue)
                        deductions[category] += anomaly_weight * SEVERITY_MULTIPLIERS[severity]

            _check_specific_issues(row, source, issues, deductions)

    category_scores = {}
    for category, weight in CATEGORY_WEIGHTS.items():
        max_deduction = weight * 2
        deduction = min(deductions[category], max_deduction)
        score_value = max(0, int(100 - (deduction / max_deduction) * 100))
        category_scores[category] = score_value

    total_score = sum((category_scores[cat] * wt) / 100 for cat, wt in CATEGORY_WEIGHTS.items())
    score = max(0, min(100, int(total_score)))
    grade, status = _get_grade_and_status(score)
    summary = {
        "critical": sum(1 for issue in issues if issue.severity == Severity.CRITICAL),
        "warning": sum(1 for issue in issues if issue.severity == Severity.WARNING),
        "info": sum(1 for issue in issues if issue.severity == Severity.INFO),
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


def health_report_to_dict(report: HealthReport) -> Dict[str, Any]:
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


def _match_anomaly(name: str) -> Optional[AnomlyType]:
    for atype in AnomlyType:
        if atype.value in name or name in atype.value:
            return atype
    return None


def _check_specific_issues(row: Dict, source: str, issues: List[Issue], deductions: Dict[str, float]):
    node_guid = row.get("NodeGUID", "")
    port_number = row.get("PortNumber", 0)

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
            details={"temperature": temp, "source": source},
        )
        kb_key = ExplanationKey.HIGH_TEMPERATURE if severity == Severity.CRITICAL else ExplanationKey.MODERATE_TEMPERATURE
        _attach_issue_guide(issue, custom_key=kb_key)
        issues.append(issue)
        deductions["errors"] += (temp - 60) * SEVERITY_MULTIPLIERS[severity]

    link_down = _to_float(row.get("LinkDownedCounter")) + _to_float(row.get("LinkDownedCounterExt"))
    if link_down > 0:
        link_down_count = int(link_down)
        issue = Issue(
            severity=Severity.CRITICAL,
            category="errors",
            description=f"Link down events: {link_down_count}",
            node_guid=node_guid,
            port_number=port_number,
            weight=link_down,
            details={"link_down_count": link_down_count, "source": source},
        )
        _attach_issue_guide(issue, custom_key=ExplanationKey.LINK_DOWN)
        issues.append(issue)
        deductions["errors"] += link_down * SEVERITY_MULTIPLIERS[Severity.CRITICAL]

    recovery_total = _to_float(row.get("LinkErrorRecoveryCounter")) + _to_float(row.get("LinkErrorRecoveryCounterExt"))
    if recovery_total >= 3:
        severity = Severity.CRITICAL if recovery_total >= 10 else Severity.WARNING
        issue = Issue(
            severity=severity,
            category="errors",
            description=f"Link error recoveries: {int(recovery_total)}",
            node_guid=node_guid,
            port_number=port_number,
            weight=recovery_total,
            details={"link_recovery_count": recovery_total, "source": source},
        )
        _attach_issue_guide(issue, custom_key=ExplanationKey.LINK_RECOVERY)
        issues.append(issue)
        deductions["errors"] += recovery_total * SEVERITY_MULTIPLIERS[severity]

    neighbor_active = row.get("NeighborIsActive")
    port_state = str(row.get("PortState", "") or "")
    port_phy = str(row.get("PortPhyState", "") or "")
    neighbor_state = row.get("NeighborPortState")
    neighbor_phy = row.get("NeighborPortPhyState")
    if neighbor_active:
        state_issue = port_state and "Active" not in port_state and "4" not in port_state
        phy_issue = port_phy and "LinkUp" not in port_phy
        if state_issue or phy_issue:
            description = "Port inactive while neighbor active"
            if state_issue and phy_issue:
                description = f"Port state {port_state} / {port_phy}"
            elif state_issue:
                description = f"Port state {port_state}"
            elif phy_issue:
                description = f"Port phy state {port_phy}"
            issue = Issue(
                severity=Severity.WARNING,
                category="errors",
                description=description,
                node_guid=node_guid,
                port_number=port_number,
                weight=1.0,
                details={
                    "port_state": port_state,
                    "port_phy_state": port_phy,
                    "neighbor_state": neighbor_state,
                    "neighbor_phy_state": neighbor_phy,
                    "source": source,
                },
            )
            _attach_issue_guide(issue, custom_key=ExplanationKey.PORT_INACTIVE)
            issues.append(issue)
        deductions["errors"] += SEVERITY_MULTIPLIERS[Severity.WARNING]


def _to_float(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(numeric) or math.isinf(numeric):
        return 0.0
    return numeric


def _attach_issue_guide(
    issue: Issue,
    *,
    anomaly_type: Optional[AnomlyType] = None,
    custom_key: Optional[str] = None,
) -> None:
    guide = get_issue_guide(anomaly_type=anomaly_type, custom_key=custom_key)
    if guide:
        issue.details = issue.details or {}
        issue.details.setdefault("kb", guide)


def _get_grade_and_status(score: int) -> tuple[str, str]:
    if score >= 90:
        return "A", "Healthy"
    if score >= 80:
        return "B", "Healthy"
    if score >= 70:
        return "C", "Warning"
    if score >= 60:
        return "D", "Warning"
    return "F", "Critical"
