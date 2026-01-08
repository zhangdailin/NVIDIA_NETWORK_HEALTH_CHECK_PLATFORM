"""QoS and VL Arbitration analysis service.

Uses tables:
- VL_ARBITRATION_TABLE: Virtual Lane arbitration configuration
- Analyzes weight distribution and VL usage patterns
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_AGG_COL, IBH_ANOMALY_AGG_WEIGHT
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class QosResult:
    """Result from QoS analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class QosService:
    """Analyze QoS and VL arbitration configuration from ibdiagnet data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> QosResult:
        """Run QoS analysis."""
        vl_df = self._try_read_table("VL_ARBITRATION_TABLE")

        if vl_df.empty:
            return QosResult()

        topology = self._get_topology()

        # Aggregate by port to create per-port QoS summary
        port_qos: Dict[tuple, Dict] = defaultdict(lambda: {
            "vl_count": 0,
            "total_weight": 0,
            "high_priority_weight": 0,
            "low_priority_weight": 0,
            "vls_used": set(),
            "weights": [],
        })

        for _, row in vl_df.iterrows():
            node_guid = str(row.get("NodeGUID", ""))
            port_num = self._safe_int(row.get("PortNum"))
            priority = str(row.get("Priority", "")).lower()
            vl = self._safe_int(row.get("VL"))
            weight = self._safe_int(row.get("Weight"))

            key = (node_guid, port_num)
            port_qos[key]["vl_count"] += 1
            port_qos[key]["total_weight"] += weight
            port_qos[key]["vls_used"].add(vl)
            port_qos[key]["weights"].append(weight)

            if priority == "high":
                port_qos[key]["high_priority_weight"] += weight
            else:
                port_qos[key]["low_priority_weight"] += weight

        records = []
        anomaly_rows = []

        for (node_guid, port_num), qos_data in port_qos.items():
            node_name = topology.node_label(node_guid) if topology else node_guid

            vls_used = len(qos_data["vls_used"])
            total_weight = qos_data["total_weight"]
            high_prio_pct = (qos_data["high_priority_weight"] / total_weight * 100) if total_weight > 0 else 0

            # Calculate weight variance (imbalance detection)
            weights = qos_data["weights"]
            avg_weight = sum(weights) / len(weights) if weights else 0
            weight_variance = sum((w - avg_weight) ** 2 for w in weights) / len(weights) if weights else 0

            # Determine severity
            severity = "normal"
            issues = []

            # Check for potential QoS issues
            if vls_used < 2:
                severity = "info"
                issues.append("Single VL in use")

            if high_prio_pct > 80:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"High priority dominates ({high_prio_pct:.1f}%)")

            if weight_variance > 10000:  # High variance indicates imbalance
                if severity == "normal":
                    severity = "warning"
                issues.append("VL weight imbalance detected")

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "VLsUsed": vls_used,
                "TotalWeight": total_weight,
                "HighPriorityWeight": qos_data["high_priority_weight"],
                "LowPriorityWeight": qos_data["low_priority_weight"],
                "HighPriorityPct": round(high_prio_pct, 1),
                "AvgWeight": round(avg_weight, 1),
                "WeightVariance": round(weight_variance, 1),
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = self._build_summary(records)

        # Sample down for display (VL table is very large)
        display_records = records[:2000] if len(records) > 2000 else records

        return QosResult(data=display_records, anomalies=None, summary=summary)

    def _build_summary(self, records: List[Dict]) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        total_ports = len(records)
        avg_vls = sum(r.get("VLsUsed", 0) for r in records) / total_ports if total_ports else 0

        # VL distribution
        vl_distribution = defaultdict(int)
        for r in records:
            vl_distribution[r.get("VLsUsed", 0)] += 1

        return {
            "total_ports_analyzed": total_ports,
            "avg_vls_per_port": round(avg_vls, 1),
            "ports_with_single_vl": sum(1 for r in records if r.get("VLsUsed", 0) == 1),
            "ports_with_high_prio_dominant": sum(1 for r in records if r.get("HighPriorityPct", 0) > 80),
            "vl_distribution": dict(vl_distribution),
        }

    def _try_read_table(self, table_name: str) -> pd.DataFrame:
        """Try to read a table, return empty DataFrame on failure."""
        try:
            index_table = self._get_index_table()
            if table_name not in index_table.index:
                return pd.DataFrame()
            return self._read_table(table_name)
        except Exception as e:
            logger.debug(f"Could not read {table_name}: {e}")
            return pd.DataFrame()

    def _get_index_table(self) -> pd.DataFrame:
        if self._index_cache is None:
            db_csv = self._find_db_csv()
            self._index_cache = read_index_table(db_csv)
        return self._index_cache

    def _read_table(self, table_name: str) -> pd.DataFrame:
        db_csv = self._find_db_csv()
        return read_table(db_csv, table_name, self._get_index_table())

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    def _get_topology(self) -> Optional[TopologyLookup]:
        if self._topology is None:
            try:
                self._topology = TopologyLookup(self.dataset_root)
            except Exception as e:
                logger.debug(f"Could not load topology: {e}")
        return self._topology

    @staticmethod
    def _safe_int(value: object) -> int:
        try:
            if pd.isna(value):
                return 0
            return int(float(value))
        except (TypeError, ValueError):
            return 0
