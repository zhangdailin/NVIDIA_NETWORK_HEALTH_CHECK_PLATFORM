"""Port Hierarchy analysis service using PORT_HIERARCHY_INFO table.

Provides:
- Hierarchical port relationships in the fabric
- Plane/tier information for multi-plane networks
- Port role identification (spine/leaf/etc.)
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
class PortHierarchyResult:
    """Result from port hierarchy analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PortHierarchyService:
    """Analyze port hierarchy information from ibdiagnet data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PortHierarchyResult:
        """Run port hierarchy analysis."""
        hierarchy_df = self._try_read_table("PORT_HIERARCHY_INFO")

        if hierarchy_df.empty:
            return PortHierarchyResult()

        topology = self._get_topology()
        records = []

        # Track hierarchy statistics
        plane_nodes: Dict[int, set] = defaultdict(set)
        tier_counts: Dict[int, int] = defaultdict(int)
        role_counts: Dict[str, int] = defaultdict(int)

        for _, row in hierarchy_df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            port_num = self._safe_int(row.get("PortNum"))
            plane_num = self._safe_int(row.get("PlaneNum"))
            tier = self._safe_int(row.get("Tier"))
            is_smp = bool(row.get("IsSMP", 0))
            is_enhanced = bool(row.get("IsEnhanced", 0))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Determine role based on tier (common mapping)
            role = self._tier_to_role(tier)

            # Track statistics
            plane_nodes[plane_num].add(node_guid)
            tier_counts[tier] += 1
            role_counts[role] += 1

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "PlaneNumber": plane_num,
                "Tier": tier,
                "Role": role,
                "IsSMP": is_smp,
                "IsEnhanced": is_enhanced,
            }
            records.append(record)

        # Build summary
        summary = self._build_summary(records, plane_nodes, tier_counts, role_counts)

        # Sample for display (PORT_HIERARCHY_INFO can be large)
        display_records = records[:2000] if len(records) > 2000 else records

        return PortHierarchyResult(data=display_records, anomalies=None, summary=summary)

    def _tier_to_role(self, tier: int) -> str:
        """Map tier number to common role name."""
        tier_roles = {
            0: "Edge",
            1: "Leaf",
            2: "Spine",
            3: "Super-Spine",
            4: "Core",
        }
        return tier_roles.get(tier, f"Tier-{tier}")

    def _build_summary(
        self,
        records: List[Dict],
        plane_nodes: Dict[int, set],
        tier_counts: Dict[int, int],
        role_counts: Dict[str, int],
    ) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        # Count unique nodes
        unique_nodes = set(r.get("NodeGUID") for r in records)

        # Plane distribution
        planes = {plane: len(nodes) for plane, nodes in plane_nodes.items()}

        return {
            "total_ports": len(records),
            "unique_nodes": len(unique_nodes),
            "plane_count": len(plane_nodes),
            "planes": planes,
            "tier_distribution": dict(tier_counts),
            "role_distribution": dict(role_counts),
            "is_multi_plane": len(plane_nodes) > 1,
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
        """Get the index table, cached."""
        if self._index_cache is None:
            db_csv = self._find_db_csv()
            self._index_cache = read_index_table(db_csv)
        return self._index_cache

    def _read_table(self, table_name: str) -> pd.DataFrame:
        """Read a table from db_csv."""
        db_csv = self._find_db_csv()
        return read_table(db_csv, table_name, self._get_index_table())

    def _find_db_csv(self) -> Path:
        """Find the db_csv file."""
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    def _get_topology(self) -> Optional[TopologyLookup]:
        """Get topology lookup, cached."""
        if self._topology is None:
            try:
                self._topology = TopologyLookup(self.dataset_root)
            except Exception as e:
                logger.debug(f"Could not load topology: {e}")
        return self._topology

    @staticmethod
    def _safe_int(value: object) -> int:
        """Safely convert to int."""
        try:
            if pd.isna(value):
                return 0
            return int(float(value))
        except (TypeError, ValueError):
            return 0
