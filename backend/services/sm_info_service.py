"""Subnet Manager (SM) analysis service using SM_INFO table.

Provides:
- SM state and priority information
- Master SM identification
- SM configuration analysis
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
class SMInfoResult:
    """Result from SM analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class SMInfoService:
    """Analyze Subnet Manager configuration from ibdiagnet data."""

    # SM State codes from IB spec
    SM_STATE_NAMES = {
        0: "Not Active",
        1: "Discovering",
        2: "Standby",
        3: "Master",
        4: "Unknown",
    }

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> SMInfoResult:
        """Run SM analysis."""
        sm_df = self._try_read_table("SM_INFO")

        if sm_df.empty:
            return SMInfoResult()

        topology = self._get_topology()
        records = []

        for _, row in sm_df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            port_num = self._safe_int(row.get("PortNum"))
            sm_state = self._safe_int(row.get("SMState"))
            priority = self._safe_int(row.get("Priority"))
            act_count = self._safe_int(row.get("ActCount"))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Decode SM state
            state_name = self.SM_STATE_NAMES.get(sm_state, f"Unknown ({sm_state})")
            is_master = sm_state == 3

            # Determine status
            status = "master" if is_master else "standby" if sm_state == 2 else "inactive"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "SMState": sm_state,
                "SMStateName": state_name,
                "Priority": priority,
                "ActCount": act_count,
                "IsMaster": is_master,
                "Status": status,
            }
            records.append(record)

        # Build summary
        summary = self._build_summary(records)

        return SMInfoResult(data=records, anomalies=None, summary=summary)

    def _build_summary(self, records: List[Dict]) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        master_sms = [r for r in records if r.get("IsMaster")]
        standby_sms = [r for r in records if r.get("SMState") == 2]

        master_info = None
        if master_sms:
            master = master_sms[0]
            master_info = {
                "node_name": master.get("NodeName"),
                "node_guid": master.get("NodeGUID"),
                "priority": master.get("Priority"),
            }

        return {
            "total_sms": len(records),
            "master_count": len(master_sms),
            "standby_count": len(standby_sms),
            "inactive_count": len(records) - len(master_sms) - len(standby_sms),
            "master_sm": master_info,
            "has_redundancy": len(standby_sms) > 0,
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
