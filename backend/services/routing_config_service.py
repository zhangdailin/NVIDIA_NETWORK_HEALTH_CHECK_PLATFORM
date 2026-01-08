"""HBF and PFRN Config service for routing configuration analysis.

Uses tables:
- HBF_CONFIG: Hash-Based Forwarding configuration (608 rows typical)
- PFRN_CONFIG: Precise Forwarding Routing Notification config (608 rows typical)
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
class RoutingConfigResult:
    """Result from Routing Config analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class RoutingConfigService:
    """Analyze HBF and PFRN routing configuration."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> RoutingConfigResult:
        """Run Routing Config analysis."""
        hbf_df = self._try_read_table("HBF_CONFIG")
        pfrn_df = self._try_read_table("PFRN_CONFIG")

        if hbf_df.empty and pfrn_df.empty:
            return RoutingConfigResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        hbf_enabled_count = 0
        pfrn_enabled_count = 0
        hash_function_distribution: Dict[str, int] = defaultdict(int)
        seed_distribution: Dict[int, int] = defaultdict(int)

        # Build PFRN lookup
        pfrn_lookup = {}
        if not pfrn_df.empty:
            for _, row in pfrn_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                pfrn_lookup[guid] = {
                    "enabled": self._safe_bool(row.get("Enabled", row.get("PFRNEnabled", False))),
                    "timeout": self._safe_int(row.get("Timeout", row.get("PFRNTimeout", 0))),
                    "max_retries": self._safe_int(row.get("MaxRetries", 0)),
                    "mode": str(row.get("Mode", row.get("PFRNMode", ""))),
                }
                if pfrn_lookup[guid]["enabled"]:
                    pfrn_enabled_count += 1

        # Process HBF config (primary source)
        if not hbf_df.empty:
            for _, row in hbf_df.iterrows():
                node_guid = str(row.get("NodeGuid", row.get("GUID", "")))

                # Get node name
                node_name = topology.node_label(node_guid) if topology else node_guid

                # HBF settings
                hbf_enabled = self._safe_bool(row.get("Enabled", row.get("HBFEnabled", False)))
                if hbf_enabled:
                    hbf_enabled_count += 1

                # Hash function
                hash_function = str(row.get("HashFunction", row.get("HashType", "Unknown")))
                hash_function_distribution[hash_function] += 1

                # Seed
                seed = self._safe_int(row.get("Seed", row.get("HashSeed", 0)))
                seed_distribution[seed] += 1

                # Hash fields
                hash_fields = str(row.get("HashFields", row.get("Fields", "")))

                # Load balancing mode
                lb_mode = str(row.get("LoadBalancingMode", row.get("LBMode", "")))

                # Weight distribution
                weight_cap = self._safe_int(row.get("WeightCap", 0))
                weight_top = self._safe_int(row.get("WeightTop", 0))

                # Get PFRN info
                pfrn_info = pfrn_lookup.get(node_guid, {})

                # Detect issues
                issues = []
                severity = "normal"

                # Check for inconsistent configuration
                if hbf_enabled and not pfrn_info.get("enabled", False):
                    issues.append("HBF enabled but PFRN disabled - may affect fast recovery")
                    severity = "info"

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "HBFEnabled": hbf_enabled,
                    "HashFunction": hash_function,
                    "HashSeed": seed,
                    "HashFields": hash_fields,
                    "LoadBalancingMode": lb_mode,
                    "WeightCap": weight_cap,
                    "WeightTop": weight_top,
                    "PFRNEnabled": pfrn_info.get("enabled", False),
                    "PFRNTimeout": pfrn_info.get("timeout", 0),
                    "PFRNMaxRetries": pfrn_info.get("max_retries", 0),
                    "PFRNMode": pfrn_info.get("mode", ""),
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)
        else:
            # Process PFRN only if no HBF data
            for _, row in pfrn_df.iterrows():
                node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
                node_name = topology.node_label(node_guid) if topology else node_guid

                pfrn_info = pfrn_lookup.get(node_guid, {})

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "HBFEnabled": False,
                    "HashFunction": "",
                    "HashSeed": 0,
                    "HashFields": "",
                    "LoadBalancingMode": "",
                    "WeightCap": 0,
                    "WeightTop": 0,
                    "PFRNEnabled": pfrn_info.get("enabled", False),
                    "PFRNTimeout": pfrn_info.get("timeout", 0),
                    "PFRNMaxRetries": pfrn_info.get("max_retries", 0),
                    "PFRNMode": pfrn_info.get("mode", ""),
                    "Severity": "normal",
                    "Issues": "",
                }
                records.append(record)

        # Build summary
        total_switches = max(len(hbf_df), len(pfrn_df))
        summary = {
            "total_switches": total_switches,
            "hbf_enabled_count": hbf_enabled_count,
            "pfrn_enabled_count": pfrn_enabled_count,
            "hbf_coverage_pct": round(hbf_enabled_count / max(total_switches, 1) * 100, 1),
            "pfrn_coverage_pct": round(pfrn_enabled_count / max(total_switches, 1) * 100, 1),
            "hash_function_distribution": dict(sorted(hash_function_distribution.items(), key=lambda x: -x[1])),
            "unique_seeds": len(seed_distribution),
            "most_common_seed": max(seed_distribution.items(), key=lambda x: x[1])[0] if seed_distribution else 0,
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            r.get("NodeName", "")
        ))

        return RoutingConfigResult(data=records[:2000], anomalies=None, summary=summary)

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
