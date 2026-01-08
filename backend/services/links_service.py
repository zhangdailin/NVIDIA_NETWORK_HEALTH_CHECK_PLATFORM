"""Links analysis service using LINKS table for network topology connectivity.

Provides:
- Node-to-node connectivity mapping
- Link symmetry validation
- Port utilization analysis
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_AGG_COL, IBH_ANOMALY_AGG_WEIGHT
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class LinksResult:
    """Result from links analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class LinksService:
    """Analyze network link connectivity from ibdiagnet data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> LinksResult:
        """Run links analysis."""
        links_df = self._try_read_table("LINKS")

        if links_df.empty:
            return LinksResult()

        topology = self._get_topology()
        records = []
        anomaly_rows = []

        # Track connections for symmetry check
        connections: Dict[Tuple[str, int], Tuple[str, int]] = {}
        node_port_count: Dict[str, Set[int]] = defaultdict(set)

        for _, row in links_df.iterrows():
            node1 = str(row.get("NodeGuid1", ""))
            port1 = self._safe_int(row.get("PortNum1"))
            node2 = str(row.get("NodeGuid2", ""))
            port2 = self._safe_int(row.get("PortNum2"))

            # Track connections
            connections[(node1, port1)] = (node2, port2)
            node_port_count[node1].add(port1)
            node_port_count[node2].add(port2)

            # Get node names
            node1_name = topology.node_label(node1) if topology else node1
            node2_name = topology.node_label(node2) if topology else node2

            record = {
                "NodeGUID1": node1,
                "NodeName1": node1_name,
                "PortNumber1": port1,
                "NodeGUID2": node2,
                "NodeName2": node2_name,
                "PortNumber2": port2,
                "LinkDescription": f"{node1_name}:{port1} <-> {node2_name}:{port2}",
            }
            records.append(record)

        # Check for asymmetric links (one-way connections)
        asymmetric_links = []
        for (node1, port1), (node2, port2) in connections.items():
            reverse_key = (node2, port2)
            if reverse_key in connections:
                reverse_target = connections[reverse_key]
                if reverse_target != (node1, port1):
                    asymmetric_links.append({
                        "node1": node1,
                        "port1": port1,
                        "node2": node2,
                        "port2": port2,
                    })

        # Add asymmetry info to records
        if asymmetric_links:
            for link in asymmetric_links:
                anomaly_rows.append({
                    "NodeGUID": link["node1"],
                    "PortNumber": link["port1"],
                    IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_LINK_ASYMMETRIC),
                    IBH_ANOMALY_AGG_WEIGHT: 0.5,
                })

        # Build anomaly DataFrame
        anomalies = pd.DataFrame(anomaly_rows) if anomaly_rows else None

        # Build summary
        summary = self._build_summary(records, node_port_count, asymmetric_links)

        return LinksResult(data=records, anomalies=anomalies, summary=summary)

    def _build_summary(
        self,
        records: List[Dict],
        node_port_count: Dict[str, Set[int]],
        asymmetric_links: List[Dict],
    ) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        # Count unique nodes
        unique_nodes = set()
        for r in records:
            unique_nodes.add(r.get("NodeGUID1", ""))
            unique_nodes.add(r.get("NodeGUID2", ""))

        # Port count distribution
        port_counts = [len(ports) for ports in node_port_count.values()]
        avg_ports = sum(port_counts) / len(port_counts) if port_counts else 0

        return {
            "total_links": len(records),
            "unique_nodes": len(unique_nodes),
            "avg_ports_per_node": round(avg_ports, 1),
            "max_ports_per_node": max(port_counts) if port_counts else 0,
            "min_ports_per_node": min(port_counts) if port_counts else 0,
            "asymmetric_links": len(asymmetric_links),
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
