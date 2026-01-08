"""Adaptive Routing Info service for AR/FR/HBF configuration analysis.

Uses tables:
- AR_INFO: Adaptive routing capabilities and configuration per switch
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
class ArInfoResult:
    """Result from AR Info analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class ArInfoService:
    """Analyze Adaptive Routing configuration and capabilities."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> ArInfoResult:
        """Run AR Info analysis."""
        ar_df = self._try_read_table("AR_INFO")

        if ar_df.empty:
            return ArInfoResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        ar_supported = 0
        fr_supported = 0
        fr_enabled = 0
        hbf_supported = 0
        hbf_enabled = 0
        pfrn_supported = 0
        pfrn_enabled = 0

        for _, row in ar_df.iterrows():
            node_guid = str(row.get("NodeGUID", ""))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # AR capabilities
            is_arn_sup = self._safe_bool(row.get("is_arn_sup"))
            is_frn_sup = self._safe_bool(row.get("is_frn_sup"))
            is_fr_sup = self._safe_bool(row.get("is_fr_sup"))
            fr_en = self._safe_bool(row.get("fr_enabled"))
            rn_xmit_en = self._safe_bool(row.get("rn_xmit_enabled"))

            # HBF capabilities
            is_hbf_sup = self._safe_bool(row.get("is_hbf_supported"))
            by_sl_hbf_en = self._safe_bool(row.get("by_sl_hbf_en"))
            is_whbf_sup = self._safe_bool(row.get("is_whbf_supported"))
            whbf_en = self._safe_bool(row.get("whbf_en"))

            # PFRN capabilities
            is_pfrn_sup = self._safe_bool(row.get("is_pfrn_supported"))
            pfrn_en = self._safe_bool(row.get("pfrn_enabled"))

            # Group configuration
            group_cap = self._safe_int(row.get("group_cap", 0))
            group_top = self._safe_int(row.get("group_top", 0))
            sub_grps_active = self._safe_int(row.get("sub_grps_active", 0))
            glb_groups = self._safe_int(row.get("glb_groups", 0))

            # AR version info
            ar_version = self._safe_int(row.get("ar_version_cap", 0))
            rn_version = self._safe_int(row.get("rn_version_cap", 0))

            # Track statistics
            if is_arn_sup or is_frn_sup:
                ar_supported += 1
            if is_fr_sup:
                fr_supported += 1
            if fr_en:
                fr_enabled += 1
            if is_hbf_sup:
                hbf_supported += 1
            if by_sl_hbf_en or whbf_en:
                hbf_enabled += 1
            if is_pfrn_sup:
                pfrn_supported += 1
            if pfrn_en:
                pfrn_enabled += 1

            # Determine issues
            issues = []
            severity = "normal"

            # Check for supported but not enabled features
            if is_fr_sup and not fr_en:
                issues.append("Fast Recovery supported but disabled")
                if severity == "normal":
                    severity = "info"

            if is_hbf_sup and not (by_sl_hbf_en or whbf_en):
                issues.append("HBF supported but disabled")
                if severity == "normal":
                    severity = "info"

            if is_pfrn_sup and not pfrn_en:
                issues.append("PFRN supported but disabled")
                if severity == "normal":
                    severity = "info"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "ARNSupported": is_arn_sup,
                "FRNSupported": is_frn_sup,
                "FRSupported": is_fr_sup,
                "FREnabled": fr_en,
                "RNXmitEnabled": rn_xmit_en,
                "HBFSupported": is_hbf_sup,
                "HBFEnabled": by_sl_hbf_en or whbf_en,
                "WHBFSupported": is_whbf_sup,
                "WHBFEnabled": whbf_en,
                "PFRNSupported": is_pfrn_sup,
                "PFRNEnabled": pfrn_en,
                "GroupCapacity": group_cap,
                "GroupTop": group_top,
                "SubGroupsActive": sub_grps_active,
                "GlobalGroups": glb_groups,
                "ARVersion": ar_version,
                "RNVersion": rn_version,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = {
            "total_switches": len(ar_df),
            "ar_supported": ar_supported,
            "fr_supported": fr_supported,
            "fr_enabled": fr_enabled,
            "hbf_supported": hbf_supported,
            "hbf_enabled": hbf_enabled,
            "pfrn_supported": pfrn_supported,
            "pfrn_enabled": pfrn_enabled,
            "fr_coverage_pct": round(fr_enabled / max(fr_supported, 1) * 100, 1),
            "hbf_coverage_pct": round(hbf_enabled / max(hbf_supported, 1) * 100, 1),
        }

        return ArInfoResult(data=records[:2000], anomalies=None, summary=summary)

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
            s = str(value).strip().lower()
            return s in ("1", "true", "yes", "enabled")
        except (TypeError, ValueError):
            return False
