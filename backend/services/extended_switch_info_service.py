"""Extended Switch Info service for switch-specific attributes.

Uses tables:
- EXTENDED_SWITCH_INFO: Extended switch-specific information (608 rows typical)
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
class ExtendedSwitchInfoResult:
    """Result from Extended Switch Info analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class ExtendedSwitchInfoService:
    """Analyze extended switch information for advanced switch features."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> ExtendedSwitchInfoResult:
        """Run Extended Switch Info analysis."""
        ext_switch_df = self._try_read_table("EXTENDED_SWITCH_INFO")

        if ext_switch_df.empty:
            return ExtendedSwitchInfoResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        enhanced_port0_count = 0
        multicast_enabled_count = 0
        filter_raw_enabled_count = 0
        total_multicast_pkeys = 0
        total_multicast_cap = 0
        ar_capable_count = 0

        for _, row in ext_switch_df.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("GUID", "")))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Enhanced port 0
            enhanced_port0 = self._safe_bool(row.get("EnhancedPort0", row.get("EnhPort0", False)))
            if enhanced_port0:
                enhanced_port0_count += 1

            # Multicast capabilities
            multicast_fdb_cap = self._safe_int(row.get("MulticastFDBCap", 0))
            multicast_fdb_top = self._safe_int(row.get("MulticastFDBTop", 0))
            multicast_pkey_table_cap = self._safe_int(row.get("MulticastPKeyTableCap", 0))
            total_multicast_cap += multicast_fdb_cap
            total_multicast_pkeys += multicast_pkey_table_cap

            if multicast_fdb_cap > 0:
                multicast_enabled_count += 1

            # LFT capabilities
            lft_cap = self._safe_int(row.get("LinearFDBCap", row.get("LFTCap", 0)))
            lft_top = self._safe_int(row.get("LinearFDBTop", row.get("LFTTop", 0)))
            random_fdb_cap = self._safe_int(row.get("RandomFDBCap", 0))

            # Filter raw packets
            filter_raw_inbound = self._safe_bool(row.get("FilterRawInbound", False))
            filter_raw_outbound = self._safe_bool(row.get("FilterRawOutbound", False))
            if filter_raw_inbound or filter_raw_outbound:
                filter_raw_enabled_count += 1

            # Optimized SL to VL mapping
            opt_sl2vl = self._safe_bool(row.get("OptimizedSLtoVLMappingProgramming", False))

            # AR capabilities
            ar_cap = self._safe_int(row.get("AdaptiveRoutingCapability", row.get("ARCap", 0)))
            if ar_cap > 0:
                ar_capable_count += 1

            # Multipath support
            multipath_support = self._safe_bool(row.get("MultipathSupport", False))

            # Port state change
            port_state_change = self._safe_int(row.get("PortStateChange", 0))

            # Detect potential issues
            issues = []
            severity = "normal"

            lft_utilization = (lft_top / lft_cap * 100) if lft_cap > 0 else 0
            if lft_utilization >= 90:
                issues.append(f"LFT near capacity: {lft_utilization:.1f}%")
                severity = "warning"
            if lft_utilization >= 98:
                severity = "critical"

            mcast_utilization = (multicast_fdb_top / multicast_fdb_cap * 100) if multicast_fdb_cap > 0 else 0
            if mcast_utilization >= 90:
                issues.append(f"Multicast FDB near capacity: {mcast_utilization:.1f}%")
                if severity == "normal":
                    severity = "warning"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "EnhancedPort0": enhanced_port0,
                "LinearFDBCap": lft_cap,
                "LinearFDBTop": lft_top,
                "LFTUtilization": round(lft_utilization, 1),
                "RandomFDBCap": random_fdb_cap,
                "MulticastFDBCap": multicast_fdb_cap,
                "MulticastFDBTop": multicast_fdb_top,
                "MulticastPKeyCap": multicast_pkey_table_cap,
                "FilterRawInbound": filter_raw_inbound,
                "FilterRawOutbound": filter_raw_outbound,
                "OptimizedSL2VL": opt_sl2vl,
                "ARCapability": ar_cap,
                "MultipathSupport": multipath_support,
                "PortStateChange": port_state_change,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = {
            "total_switches": len(ext_switch_df),
            "enhanced_port0_count": enhanced_port0_count,
            "multicast_enabled_count": multicast_enabled_count,
            "filter_raw_enabled_count": filter_raw_enabled_count,
            "ar_capable_count": ar_capable_count,
            "total_multicast_capacity": total_multicast_cap,
            "total_multicast_pkey_capacity": total_multicast_pkeys,
            "avg_multicast_cap_per_switch": round(total_multicast_cap / max(len(ext_switch_df), 1), 1),
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            r.get("NodeName", "")
        ))

        return ExtendedSwitchInfoResult(data=records[:2000], anomalies=None, summary=summary)

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
