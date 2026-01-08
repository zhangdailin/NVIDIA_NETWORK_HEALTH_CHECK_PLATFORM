"""Virtual Ports (VPorts) analysis service for SR-IOV and virtualization.

Uses tables:
- VNODES: Virtual node information
- VPORTS: Virtual port details
- VPORTS_GUID_INFO: Virtual port GUID mappings
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
class VPortsResult:
    """Result from VPorts analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class VPortsService:
    """Analyze virtual ports for SR-IOV and virtualization deployments."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> VPortsResult:
        """Run VPorts analysis."""
        vnodes_df = self._try_read_table("VNODES")
        vports_df = self._try_read_table("VPORTS")

        if vnodes_df.empty and vports_df.empty:
            return VPortsResult()

        topology = self._get_topology()
        records = []

        # Track VNodes per physical node
        vnode_counts: Dict[str, int] = defaultdict(int)
        vport_counts: Dict[str, int] = defaultdict(int)

        # Process VNODES
        if not vnodes_df.empty:
            for _, row in vnodes_df.iterrows():
                phys_node_guid = str(row.get("NodeGuid", ""))
                vnode_guid = str(row.get("VNodeGuid", ""))
                vnode_desc = str(row.get("VNodeDesc", ""))
                vport_index = self._safe_int(row.get("VPortIndex"))
                v_num_ports = self._safe_int(row.get("VNumberOfPorts"))

                # Get physical node name
                phys_node_name = topology.node_label(phys_node_guid) if topology else phys_node_guid

                vnode_counts[phys_node_guid] += 1

                record = {
                    "PhysicalNodeGUID": phys_node_guid,
                    "PhysicalNodeName": phys_node_name,
                    "VNodeGUID": vnode_guid,
                    "VNodeDescription": vnode_desc if vnode_desc != "nan" else "",
                    "VPortIndex": vport_index,
                    "VirtualPorts": v_num_ports,
                    "Type": "VNode",
                }
                records.append(record)

        # Process VPORTS for additional details
        if not vports_df.empty:
            for _, row in vports_df.iterrows():
                phys_node_guid = str(row.get("NodeGuid", ""))
                vport_counts[phys_node_guid] += 1

        # Build summary
        summary = self._build_summary(records, vnodes_df, vports_df, vnode_counts, vport_counts)

        return VPortsResult(data=records[:2000], anomalies=None, summary=summary)

    def _build_summary(
        self,
        records: List[Dict],
        vnodes_df: pd.DataFrame,
        vports_df: pd.DataFrame,
        vnode_counts: Dict[str, int],
        vport_counts: Dict[str, int],
    ) -> Dict[str, object]:
        """Build summary statistics."""
        total_vnodes = len(vnodes_df) if not vnodes_df.empty else 0
        total_vports = len(vports_df) if not vports_df.empty else 0

        # Physical nodes with virtualization
        phys_nodes_with_vnodes = len(vnode_counts)
        phys_nodes_with_vports = len(vport_counts)

        # Calculate distribution
        vnodes_per_node = list(vnode_counts.values()) if vnode_counts else []
        avg_vnodes = sum(vnodes_per_node) / len(vnodes_per_node) if vnodes_per_node else 0
        max_vnodes = max(vnodes_per_node) if vnodes_per_node else 0

        return {
            "total_vnodes": total_vnodes,
            "total_vports": total_vports,
            "physical_nodes_with_vnodes": phys_nodes_with_vnodes,
            "physical_nodes_with_vports": phys_nodes_with_vports,
            "avg_vnodes_per_physical": round(avg_vnodes, 1),
            "max_vnodes_per_physical": max_vnodes,
            "virtualization_enabled": total_vnodes > 0 or total_vports > 0,
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
