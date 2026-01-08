"""Physical Layer Diagnostics service for signal integrity analysis.

Uses tables:
- PHY_DB1: Core physical layer diagnostics (30k+ rows)
- Provides signal quality metrics and eye diagram parameters
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
class PhyDiagnosticsResult:
    """Result from Physical Layer Diagnostics analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PhyDiagnosticsService:
    """Analyze physical layer diagnostics for signal integrity."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PhyDiagnosticsResult:
        """Run Physical Layer Diagnostics analysis."""
        phy_df = self._try_read_table("PHY_DB1")

        if phy_df.empty:
            return PhyDiagnosticsResult()

        topology = self._get_topology()
        records = []

        # Get column names for dynamic analysis
        columns = list(phy_df.columns)
        field_columns = [c for c in columns if c.startswith("field")]

        for _, row in phy_df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            port_guid = str(row.get("PortGuid", ""))
            port_num = self._safe_int(row.get("PortNum"))
            version = self._safe_int(row.get("Version", 0))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Extract key field values (first 20 fields are typically most important)
            field_values = {}
            for i, col in enumerate(field_columns[:20]):
                field_values[f"Field{i}"] = self._safe_int(row.get(col, 0))

            # Calculate a simple quality score based on field values
            # Higher values in certain fields may indicate issues
            non_zero_fields = sum(1 for v in field_values.values() if v != 0)

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "PortGUID": port_guid[-16:] if len(port_guid) > 16 else port_guid,
                "Version": version,
                "NonZeroFields": non_zero_fields,
                **field_values,
            }
            records.append(record)

        # Build summary
        summary = self._build_summary(records, phy_df, field_columns)

        return PhyDiagnosticsResult(data=records[:2000], anomalies=None, summary=summary)

    def _build_summary(
        self,
        records: List[Dict],
        raw_df: pd.DataFrame,
        field_columns: List[str],
    ) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {"total_ports": 0}

        non_zero_counts = [r.get("NonZeroFields", 0) for r in records]
        avg_non_zero = sum(non_zero_counts) / len(non_zero_counts) if non_zero_counts else 0
        max_non_zero = max(non_zero_counts) if non_zero_counts else 0

        return {
            "total_ports": len(raw_df),
            "total_diagnostic_fields": len(field_columns),
            "avg_non_zero_fields": round(avg_non_zero, 1),
            "max_non_zero_fields": max_non_zero,
            "ports_with_data": sum(1 for r in records if r.get("NonZeroFields", 0) > 0),
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
