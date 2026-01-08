"""Partition Key (PKEY) analysis service for network isolation and security.

Uses tables:
- PKEY: Partition key assignments per port
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class PkeyResult:
    """Result from PKEY analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PkeyService:
    """Analyze partition key configuration for network isolation."""

    # Common PKEY values
    DEFAULT_PKEY = 0x7fff  # Default partition (full membership)
    LIMITED_PKEY = 0xffff   # Limited membership variant

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PkeyResult:
        """Run PKEY analysis."""
        pkey_df = self._try_read_table("PKEY")

        if pkey_df.empty:
            return PkeyResult()

        topology = self._get_topology()
        records = []

        # Track partition usage
        pkey_usage: Dict[str, Set[str]] = defaultdict(set)  # pkey -> set of node GUIDs
        node_pkeys: Dict[str, Set[str]] = defaultdict(set)  # node GUID -> set of pkeys
        membership_counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

        for _, row in pkey_df.iterrows():
            node_guid = str(row.get("NodeGUID", ""))
            port_num = self._safe_int(row.get("LocalPortNum"))
            pkey_raw = row.get("PKey", "0x0")
            membership = self._safe_int(row.get("Membership"))

            # Parse PKEY value
            pkey_value = self._parse_pkey(pkey_raw)
            pkey_str = f"0x{pkey_value:04x}"

            # Skip invalid/empty pkeys
            if pkey_value == 0:
                continue

            # Track usage
            pkey_usage[pkey_str].add(node_guid)
            node_pkeys[node_guid].add(pkey_str)
            membership_counts[pkey_str][membership] += 1

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Determine membership type
            membership_type = "Full" if membership == 1 else "Limited" if membership == 0 else f"Unknown({membership})"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "PKey": pkey_str,
                "PKeyValue": pkey_value,
                "Membership": membership,
                "MembershipType": membership_type,
                "IsDefaultPartition": pkey_value == self.DEFAULT_PKEY,
            }
            records.append(record)

        # Build summary
        summary = self._build_summary(records, pkey_usage, node_pkeys, membership_counts)

        # Sort by PKEY then node
        records.sort(key=lambda r: (r.get("PKeyValue", 0), r.get("NodeName", "")))

        # Return sampled data (PKEY table can be very large)
        return PkeyResult(data=records[:2000], anomalies=None, summary=summary)

    def _parse_pkey(self, value: object) -> int:
        """Parse PKEY value from various formats."""
        try:
            if pd.isna(value):
                return 0
            if isinstance(value, (int, float)):
                return int(value)
            s = str(value).strip()
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(float(s))
        except (TypeError, ValueError):
            return 0

    def _build_summary(
        self,
        records: List[Dict],
        pkey_usage: Dict[str, Set[str]],
        node_pkeys: Dict[str, Set[str]],
        membership_counts: Dict[str, Dict[int, int]],
    ) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        # Unique partitions
        unique_pkeys = list(pkey_usage.keys())

        # Partition sizes
        partition_sizes = {pk: len(nodes) for pk, nodes in pkey_usage.items()}

        # Nodes with multiple partitions
        multi_partition_nodes = sum(1 for pkeys in node_pkeys.values() if len(pkeys) > 1)

        # Find largest partitions
        largest_partitions = sorted(partition_sizes.items(), key=lambda x: -x[1])[:5]

        # Default partition coverage
        default_pkey_str = f"0x{self.DEFAULT_PKEY:04x}"
        default_partition_size = len(pkey_usage.get(default_pkey_str, set()))

        return {
            "total_pkey_entries": len(records),
            "unique_partitions": len(unique_pkeys),
            "unique_nodes": len(node_pkeys),
            "nodes_with_multiple_partitions": multi_partition_nodes,
            "default_partition_nodes": default_partition_size,
            "largest_partitions": dict(largest_partitions),
            "partition_list": unique_pkeys[:20],  # First 20 partitions
            "isolation_enabled": len(unique_pkeys) > 1,
        }

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
