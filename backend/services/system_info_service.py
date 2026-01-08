"""System Information service for hardware inventory and run metadata.

Uses tables:
- SYSTEM_GENERAL_INFORMATION: Hardware serial/part numbers
- RUN_INFO: ibdiagnet run metadata
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
class SystemInfoResult:
    """Result from System Info analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class SystemInfoService:
    """Analyze system hardware inventory and diagnostic run information."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> SystemInfoResult:
        """Run System Info analysis."""
        sys_df = self._try_read_table("SYSTEM_GENERAL_INFORMATION")
        run_df = self._try_read_table("RUN_INFO")

        records = []
        run_info = {}

        # Process RUN_INFO
        if not run_df.empty and len(run_df) > 0:
            row = run_df.iloc[0]
            run_info = {
                "ibdiagnet_version": self._clean_string(row.get("IBDIAGNET_Version", "")),
                "ibdiag_version": self._clean_string(row.get("IBDIAG_Version", "")),
                "ibdm_version": self._clean_string(row.get("IBDM_Version", "")),
                "ibis_version": self._clean_string(row.get("IBIS_Version", "")),
                "run_date": self._clean_string(row.get("Date", "")),
                "run_args": self._clean_string(row.get("Args", "")),
            }

        # Process SYSTEM_GENERAL_INFORMATION
        if not sys_df.empty:
            topology = self._get_topology()

            # Track product distribution
            product_counts: Dict[str, int] = defaultdict(int)
            serial_set = set()

            for _, row in sys_df.iterrows():
                node_guid = str(row.get("NodeGuid", ""))
                serial_number = self._clean_string(row.get("SerialNumber", ""))
                part_number = self._clean_string(row.get("PartNumber", ""))
                revision = self._clean_string(row.get("Revision", ""))
                product_name = self._clean_string(row.get("ProductName", ""))

                # Get node name
                node_name = topology.node_label(node_guid) if topology else node_guid

                # Track statistics
                if product_name:
                    product_counts[product_name] += 1
                if serial_number:
                    serial_set.add(serial_number)

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "SerialNumber": serial_number,
                    "PartNumber": part_number,
                    "Revision": revision,
                    "ProductName": product_name,
                }
                records.append(record)

        # Build summary
        summary = self._build_summary(records, run_info, sys_df)

        return SystemInfoResult(data=records[:2000], anomalies=None, summary=summary)

    def _clean_string(self, value: object) -> str:
        """Clean string value, removing quotes and handling NaN."""
        if pd.isna(value):
            return ""
        s = str(value).strip()
        # Remove surrounding quotes
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        if s.lower() == "nan":
            return ""
        return s

    def _build_summary(
        self,
        records: List[Dict],
        run_info: Dict[str, str],
        sys_df: pd.DataFrame,
    ) -> Dict[str, object]:
        """Build summary statistics."""
        # Product distribution
        product_counts: Dict[str, int] = defaultdict(int)
        revision_counts: Dict[str, int] = defaultdict(int)
        unique_serials = set()

        for r in records:
            product = r.get("ProductName", "")
            if product:
                product_counts[product] += 1
            revision = r.get("Revision", "")
            if revision:
                revision_counts[revision] += 1
            serial = r.get("SerialNumber", "")
            if serial:
                unique_serials.add(serial)

        # Sort products by count
        top_products = sorted(product_counts.items(), key=lambda x: -x[1])[:10]

        return {
            "total_devices": len(records),
            "unique_serials": len(unique_serials),
            "product_types": len(product_counts),
            "revision_types": len(revision_counts),
            "product_distribution": dict(top_products),
            "revisions": dict(sorted(revision_counts.items())),
            **run_info,
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
