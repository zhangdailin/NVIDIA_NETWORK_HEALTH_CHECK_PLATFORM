"""Switch-level analysis service using SWITCHES, SYSTEM_GENERAL_INFORMATION, AR_INFO tables."""

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
class SwitchResult:
    """Result from switch analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class SwitchService:
    """Analyze switch-level information from ibdiagnet data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> SwitchResult:
        """Run switch analysis."""
        index_table = self._get_index_table()
        records = []

        # Load all switch-related tables
        switches_df = self._try_read_table("SWITCHES")
        sys_info_df = self._try_read_table("SYSTEM_GENERAL_INFORMATION")
        ar_info_df = self._try_read_table("AR_INFO")

        if switches_df.empty and sys_info_df.empty:
            return SwitchResult()

        topology = self._get_topology()

        # Build lookup dictionaries
        sys_info_lookup = {}
        if not sys_info_df.empty:
            for _, row in sys_info_df.iterrows():
                guid = str(row.get("NodeGuid", ""))
                sys_info_lookup[guid] = {
                    "SerialNumber": str(row.get("SerialNumber", "")),
                    "PartNumber": str(row.get("PartNumber", "")),
                    "Revision": str(row.get("Revision", "")),
                    "ProductName": str(row.get("ProductName", "")).strip('"'),
                }

        ar_info_lookup = {}
        if not ar_info_df.empty:
            for _, row in ar_info_df.iterrows():
                guid = str(row.get("NodeGUID", ""))
                ar_info_lookup[guid] = {
                    "AREnabled": bool(row.get("e", 0)),
                    "ARNSupported": bool(row.get("is_arn_sup", 0)),
                    "FREnabled": bool(row.get("fr_enabled", 0)),
                    "RNXmitEnabled": bool(row.get("rn_xmit_enabled", 0)),
                    "HBFSupported": bool(row.get("is_hbf_supported", 0)),
                    "HBFEnabled": bool(row.get("by_sl_hbf_en", 0)),
                    "PFRNSupported": bool(row.get("is_pfrn_supported", 0)),
                    "PFRNEnabled": bool(row.get("pfrn_enabled", 0)),
                    "GroupCap": int(row.get("group_cap", 0)) if pd.notna(row.get("group_cap")) else 0,
                    "GroupTop": int(row.get("group_top", 0)) if pd.notna(row.get("group_top")) else 0,
                }

        # Process switches
        if not switches_df.empty:
            for _, row in switches_df.iterrows():
                guid = str(row.get("NodeGUID", ""))
                node_name = topology.node_label(guid) if topology else guid

                # Get system info
                sys_info = sys_info_lookup.get(guid, {})
                ar_info = ar_info_lookup.get(guid, {})

                record = {
                    "NodeGUID": guid,
                    "NodeName": node_name,
                    "ProductName": sys_info.get("ProductName", ""),
                    "PartNumber": sys_info.get("PartNumber", ""),
                    "SerialNumber": sys_info.get("SerialNumber", ""),
                    "Revision": sys_info.get("Revision", ""),
                    "LinearFDBCap": int(row.get("LinearFDBCap", 0)) if pd.notna(row.get("LinearFDBCap")) else 0,
                    "LinearFDBTop": int(row.get("LinearFDBTop", 0)) if pd.notna(row.get("LinearFDBTop")) else 0,
                    "MCastFDBCap": int(row.get("MCastFDBCap", 0)) if pd.notna(row.get("MCastFDBCap")) else 0,
                    "LifeTimeValue": int(row.get("LifeTimeValue", 0)) if pd.notna(row.get("LifeTimeValue")) else 0,
                    # Adaptive Routing info
                    "AREnabled": ar_info.get("AREnabled", False),
                    "FREnabled": ar_info.get("FREnabled", False),
                    "HBFSupported": ar_info.get("HBFSupported", False),
                    "HBFEnabled": ar_info.get("HBFEnabled", False),
                    "ARGroupCap": ar_info.get("GroupCap", 0),
                    "ARGroupTop": ar_info.get("GroupTop", 0),
                }
                records.append(record)

        # Build summary
        summary = self._build_summary(records)

        return SwitchResult(data=records, anomalies=None, summary=summary)

    def _build_summary(self, records: List[Dict]) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        ar_enabled_count = sum(1 for r in records if r.get("AREnabled"))
        fr_enabled_count = sum(1 for r in records if r.get("FREnabled"))
        hbf_enabled_count = sum(1 for r in records if r.get("HBFEnabled"))

        # Count product types
        products = {}
        for r in records:
            pn = r.get("ProductName", "Unknown")
            products[pn] = products.get(pn, 0) + 1

        return {
            "total_switches": len(records),
            "ar_enabled_count": ar_enabled_count,
            "fr_enabled_count": fr_enabled_count,
            "hbf_enabled_count": hbf_enabled_count,
            "product_types": products,
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
