"""Credit Watchdog Timeout service for flow control issues.

Uses tables:
- CREDIT_WATCHDOG_TIMEOUT_COUNTERS: Credit watchdog timeouts indicating flow control issues
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class CreditWatchdogResult:
    """Result from Credit Watchdog analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class CreditWatchdogService:
    """Analyze credit watchdog timeout counters for flow control issues."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> CreditWatchdogResult:
        """Run Credit Watchdog analysis."""
        cwd_df = self._try_read_table("CREDIT_WATCHDOG_TIMEOUT_COUNTERS")

        if cwd_df.empty:
            return CreditWatchdogResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        total_timeouts = 0
        ports_with_timeouts = 0
        vl_distribution: Dict[int, int] = defaultdict(int)
        max_timeout_count = 0

        for _, row in cwd_df.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
            port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Timeout counters per VL
            vl_timeouts = {}
            total_port_timeouts = 0

            # Check for VL-specific counters
            for vl in range(16):  # VL0-VL15
                col_names = [f"VL{vl}TimeoutCount", f"VL{vl}_Timeout", f"VL{vl}"]
                for col in col_names:
                    if col in row.index:
                        count = self._safe_int(row.get(col, 0))
                        if count > 0:
                            vl_timeouts[vl] = count
                            total_port_timeouts += count
                            vl_distribution[vl] += count
                        break

            # Also check generic timeout counter
            generic_timeout = self._safe_int(row.get("TimeoutCount", row.get("Timeouts", 0)))
            if generic_timeout > 0 and total_port_timeouts == 0:
                total_port_timeouts = generic_timeout

            total_timeouts += total_port_timeouts
            if total_port_timeouts > 0:
                ports_with_timeouts += 1
            max_timeout_count = max(max_timeout_count, total_port_timeouts)

            # Watchdog state
            watchdog_enabled = self._safe_bool(row.get("WatchdogEnabled", row.get("Enabled", True)))
            watchdog_limit = self._safe_int(row.get("WatchdogLimit", row.get("Limit", 0)))

            # Determine severity
            issues = []
            severity = "normal"

            if total_port_timeouts > 1000:
                issues.append(f"High timeout count: {total_port_timeouts}")
                severity = "critical"
            elif total_port_timeouts > 100:
                issues.append(f"Elevated timeout count: {total_port_timeouts}")
                severity = "warning"
            elif total_port_timeouts > 0:
                issues.append(f"Timeouts detected: {total_port_timeouts}")
                severity = "info"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "TotalTimeouts": total_port_timeouts,
                "WatchdogEnabled": watchdog_enabled,
                "WatchdogLimit": watchdog_limit,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }

            # Add VL-specific counters
            for vl, count in vl_timeouts.items():
                record[f"VL{vl}Timeouts"] = count

            records.append(record)

        # Build summary
        summary = {
            "total_entries": len(cwd_df),
            "ports_with_timeouts": ports_with_timeouts,
            "total_timeout_events": total_timeouts,
            "max_timeout_count": max_timeout_count,
            "vl_timeout_distribution": dict(sorted(vl_distribution.items())),
            "affected_vls": len(vl_distribution),
        }

        # Sort by severity and timeout count
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("TotalTimeouts", 0)
        ))

        return CreditWatchdogResult(data=records[:2000], anomalies=None, summary=summary)

    def _try_read_table(self, table_name: str) -> pd.DataFrame:
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

    @staticmethod
    def _safe_bool(value: object) -> bool:
        try:
            if pd.isna(value):
                return False
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return int(value) != 0
            return str(value).strip().lower() in ("1", "true", "yes", "enabled")
        except (TypeError, ValueError):
            return False
