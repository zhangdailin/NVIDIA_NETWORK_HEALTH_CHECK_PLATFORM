"""SHARP (Scalable Hierarchical Aggregation and Reduction Protocol) analysis service.

Uses tables:
- SHARP_AN_INFO: SHARP Aggregation Node configuration for AI/ML clusters
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class SharpResult:
    """Result from SHARP analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class SharpService:
    """Analyze SHARP configuration for AI/ML collective operations."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> SharpResult:
        """Run SHARP analysis."""
        sharp_df = self._try_read_table("SHARP_AN_INFO")

        if sharp_df.empty:
            return SharpResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        total_tree_capacity = 0
        total_jobs_capacity = 0
        max_qps = 0
        sharp_versions = set()

        for _, row in sharp_df.iterrows():
            node_guid = str(row.get("GUID", row.get("NodeGUID", "")))
            lid = self._safe_int(row.get("LID", 0))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # SHARP capabilities
            tree_table_size = self._safe_int(row.get("tree_table_size", 0))
            tree_radix = self._safe_int(row.get("tree_radix", 0))
            group_table_size = self._safe_int(row.get("group_table_size", 0))
            max_group_num = self._safe_int(row.get("max_group_num", 0))
            num_jobs = self._safe_int(row.get("num_of_jobs", 0))
            max_num_qps = self._safe_int(row.get("max_num_qps", 0))
            max_agg_payload = self._safe_int(row.get("max_aggregation_payload", 0))
            num_semaphores = self._safe_int(row.get("num_semaphores", 0))
            line_size = self._safe_int(row.get("line_size", 0))

            # Version and capabilities
            sharp_version = self._safe_int(row.get("sharp_version_supported_bit_mask", 0))
            active_class_version = self._safe_int(row.get("active_class_version", 0))
            data_types_supported = self._safe_int(row.get("data_types_supported", 0))
            mtu_support = self._safe_int(row.get("mtu_support", 0))

            # Configuration options
            endianness = self._safe_int(row.get("endianness", 0))
            reproducibility_disable = self._safe_bool(row.get("reproducibility_disable"))
            an_sat_qp_supported = self._safe_bool(row.get("an_sat_qp_info_supported"))

            # Track statistics
            total_tree_capacity += tree_table_size
            total_jobs_capacity += num_jobs
            max_qps = max(max_qps, max_num_qps)
            if sharp_version:
                sharp_versions.add(sharp_version)

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "LID": lid,
                "TreeTableSize": tree_table_size,
                "TreeRadix": tree_radix,
                "GroupTableSize": group_table_size,
                "MaxGroupNum": max_group_num,
                "NumJobs": num_jobs,
                "MaxQPs": max_num_qps,
                "MaxAggPayload": max_agg_payload,
                "NumSemaphores": num_semaphores,
                "LineSize": line_size,
                "SharpVersion": sharp_version,
                "ActiveClassVersion": active_class_version,
                "DataTypesSupported": data_types_supported,
                "MTUSupport": mtu_support,
                "Endianness": "Big" if endianness else "Little",
                "ReproducibilityDisabled": reproducibility_disable,
                "ANSatQPSupported": an_sat_qp_supported,
            }
            records.append(record)

        # Calculate data types from bitmask
        data_type_names = self._decode_data_types(data_types_supported)

        # Build summary
        summary = {
            "total_sharp_nodes": len(sharp_df),
            "sharp_enabled": len(sharp_df) > 0,
            "total_tree_capacity": total_tree_capacity,
            "total_jobs_capacity": total_jobs_capacity,
            "max_qps_per_node": max_qps,
            "avg_tree_size": round(total_tree_capacity / max(len(sharp_df), 1), 1),
            "avg_jobs_per_node": round(total_jobs_capacity / max(len(sharp_df), 1), 1),
            "sharp_versions": list(sharp_versions),
            "data_types_supported": data_type_names,
        }

        return SharpResult(data=records[:2000], anomalies=None, summary=summary)

    def _decode_data_types(self, bitmask: int) -> List[str]:
        """Decode SHARP data types bitmask."""
        types = []
        type_names = [
            "INT8", "INT16", "INT32", "INT64",
            "UINT8", "UINT16", "UINT32", "UINT64",
            "FLOAT16", "FLOAT32", "FLOAT64",
            "BFLOAT16",
        ]
        for i, name in enumerate(type_names):
            if bitmask & (1 << i):
                types.append(name)
        return types if types else ["Unknown"]

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
            return str(value).strip().lower() in ("1", "true", "yes")
        except (TypeError, ValueError):
            return False
