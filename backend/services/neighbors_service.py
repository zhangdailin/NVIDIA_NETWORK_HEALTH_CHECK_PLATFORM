"""Neighbors Info service for enhanced topology relationship analysis.

Uses tables:
- NEIGHBORS_INFO: Detailed neighbor relationships (20,480 rows typical)
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
class NeighborsResult:
    """Result from Neighbors analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class NeighborsService:
    """Analyze neighbor relationships for topology insights."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> NeighborsResult:
        """Run Neighbors analysis."""
        neighbors_df = self._try_read_table("NEIGHBORS_INFO")

        if neighbors_df.empty:
            return NeighborsResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        node_connections: Dict[str, int] = defaultdict(int)
        port_type_counts: Dict[str, int] = defaultdict(int)
        speed_distribution: Dict[str, int] = defaultdict(int)
        width_distribution: Dict[str, int] = defaultdict(int)
        mtu_distribution: Dict[int, int] = defaultdict(int)
        mismatched_speeds = 0
        mismatched_widths = 0

        for _, row in neighbors_df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            port_num = self._safe_int(row.get("PortNum"))

            # Neighbor info
            neighbor_guid = str(row.get("NeighborNodeGuid", ""))
            neighbor_port = self._safe_int(row.get("NeighborPortNum"))

            # Get node names
            node_name = topology.node_label(node_guid) if topology else node_guid
            neighbor_name = topology.node_label(neighbor_guid) if topology else neighbor_guid

            # Link properties
            local_speed = str(row.get("LinkSpeedActive", ""))
            remote_speed = str(row.get("NeighborLinkSpeedActive", ""))
            local_width = str(row.get("LinkWidthActive", ""))
            remote_width = str(row.get("NeighborLinkWidthActive", ""))
            mtu = self._safe_int(row.get("MTU", 0))

            # Port type
            port_type = str(row.get("PortType", ""))
            port_type_counts[port_type or "Unknown"] += 1

            # Track connections per node
            node_connections[node_guid] += 1

            # Track distributions
            if local_speed:
                speed_distribution[local_speed] += 1
            if local_width:
                width_distribution[local_width] += 1
            if mtu > 0:
                mtu_distribution[mtu] += 1

            # Detect mismatches
            issues = []
            severity = "normal"

            if local_speed and remote_speed and local_speed != remote_speed:
                issues.append(f"Speed mismatch: {local_speed} vs {remote_speed}")
                severity = "warning"
                mismatched_speeds += 1

            if local_width and remote_width and local_width != remote_width:
                issues.append(f"Width mismatch: {local_width} vs {remote_width}")
                severity = "warning"
                mismatched_widths += 1

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "NeighborGUID": neighbor_guid,
                "NeighborName": neighbor_name,
                "NeighborPort": neighbor_port,
                "LinkSpeed": local_speed,
                "LinkWidth": local_width,
                "MTU": mtu,
                "PortType": port_type,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Calculate statistics
        total_nodes = len(node_connections)
        avg_connections = sum(node_connections.values()) / max(total_nodes, 1)
        max_connections = max(node_connections.values()) if node_connections else 0

        # Build summary
        summary = {
            "total_neighbor_entries": len(neighbors_df),
            "unique_nodes": total_nodes,
            "avg_connections_per_node": round(avg_connections, 1),
            "max_connections_per_node": max_connections,
            "mismatched_speeds": mismatched_speeds,
            "mismatched_widths": mismatched_widths,
            "speed_distribution": dict(sorted(speed_distribution.items(), key=lambda x: -x[1])),
            "width_distribution": dict(sorted(width_distribution.items(), key=lambda x: -x[1])),
            "port_type_distribution": dict(sorted(port_type_counts.items(), key=lambda x: -x[1])),
            "mtu_distribution": dict(sorted(mtu_distribution.items(), key=lambda x: -x[1])),
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            r.get("NodeName", "")
        ))

        return NeighborsResult(data=records[:2000], anomalies=None, summary=summary)

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
