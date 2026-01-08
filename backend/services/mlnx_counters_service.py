"""Mellanox-specific counters analysis service using MLNX_CNTRS_INFO table.

Provides:
- RNR (Receiver Not Ready) retry analysis
- Queue Pair errors
- DC (Dynamic Connection) transport statistics
- Timeout and retry counters
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_AGG_COL, IBH_ANOMALY_AGG_WEIGHT
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

# Error counter thresholds
RNR_WARNING_THRESHOLD = 1000
RNR_CRITICAL_THRESHOLD = 100000
TIMEOUT_WARNING_THRESHOLD = 100
TIMEOUT_CRITICAL_THRESHOLD = 10000
QP_ERROR_THRESHOLD = 10


@dataclass
class MlnxCountersResult:
    """Result from MLNX counters analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class MlnxCountersService:
    """Analyze Mellanox-specific counters from ibdiagnet data."""

    # Counter descriptions for better reporting
    COUNTER_DESCRIPTIONS = {
        "sq_num_rnr": "Send Queue RNR (Receiver Not Ready) retries",
        "sq_num_to": "Send Queue timeouts",
        "rq_num_wrfe": "Receive Queue Work Request Flush Errors",
        "sq_num_wrfe": "Send Queue Work Request Flush Errors",
        "sq_num_tree": "Send Queue transport retry exceeded",
        "sq_num_rae": "Send Queue remote access errors",
        "rq_num_roe": "Receive Queue remote operation errors",
        "sq_num_lpe": "Send Queue local protection errors",
        "rq_num_lqpoe": "Receive Queue local QP operation errors",
        "sq_num_lqpoe": "Send Queue local QP operation errors",
    }

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> MlnxCountersResult:
        """Run MLNX counters analysis."""
        mlnx_df = self._try_read_table("MLNX_CNTRS_INFO")

        if mlnx_df.empty:
            return MlnxCountersResult()

        topology = self._get_topology()
        records = []
        anomaly_rows = []

        # Key error counters to analyze
        error_counters = [
            "sq_num_rnr", "sq_num_to", "rq_num_wrfe", "sq_num_wrfe",
            "sq_num_tree", "sq_num_rae", "rq_num_roe", "sq_num_lpe",
            "rq_num_lqpoe", "sq_num_lqpoe", "rq_num_dc_cacks", "sq_num_dc_cacks"
        ]

        for _, row in mlnx_df.iterrows():
            node_guid = str(row.get("NodeGUID", ""))
            port_num = self._safe_int(row.get("PortNumber"))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Extract counter values
            rnr_count = self._safe_int(row.get("sq_num_rnr"))
            timeout_count = self._safe_int(row.get("sq_num_to"))
            rq_wrfe = self._safe_int(row.get("rq_num_wrfe"))
            sq_wrfe = self._safe_int(row.get("sq_num_wrfe"))
            transport_retry = self._safe_int(row.get("sq_num_tree"))
            remote_access_err = self._safe_int(row.get("sq_num_rae"))
            remote_op_err = self._safe_int(row.get("rq_num_roe"))
            local_prot_err = self._safe_int(row.get("sq_num_lpe"))
            dc_cacks = self._safe_int(row.get("rq_num_dc_cacks"))

            # Calculate total errors
            total_errors = (rq_wrfe + sq_wrfe + transport_retry +
                           remote_access_err + remote_op_err + local_prot_err)

            # Determine severity
            severity = "normal"
            issues = []

            if rnr_count >= RNR_CRITICAL_THRESHOLD:
                severity = "critical"
                issues.append(f"High RNR retries: {rnr_count:,}")
            elif rnr_count >= RNR_WARNING_THRESHOLD:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"RNR retries: {rnr_count:,}")

            if timeout_count >= TIMEOUT_CRITICAL_THRESHOLD:
                severity = "critical"
                issues.append(f"High timeouts: {timeout_count:,}")
            elif timeout_count >= TIMEOUT_WARNING_THRESHOLD:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"Timeouts: {timeout_count:,}")

            if total_errors >= QP_ERROR_THRESHOLD:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"QP errors: {total_errors}")

            # Only include records with some activity or issues
            if rnr_count > 0 or timeout_count > 0 or total_errors > 0 or dc_cacks > 0:
                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_num,
                    "RNRRetries": rnr_count,
                    "Timeouts": timeout_count,
                    "RQFlushErrors": rq_wrfe,
                    "SQFlushErrors": sq_wrfe,
                    "TransportRetryExceeded": transport_retry,
                    "RemoteAccessErrors": remote_access_err,
                    "RemoteOpErrors": remote_op_err,
                    "LocalProtectionErrors": local_prot_err,
                    "DCConnAcks": dc_cacks,
                    "TotalErrors": total_errors,
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)

                # Track anomalies
                if severity == "critical":
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_num,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_MLNX_COUNTER_CRITICAL),
                        IBH_ANOMALY_AGG_WEIGHT: 1.0,
                    })
                elif severity == "warning":
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_num,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_MLNX_COUNTER_WARNING),
                        IBH_ANOMALY_AGG_WEIGHT: 0.5,
                    })

        # Build anomaly DataFrame
        anomalies = pd.DataFrame(anomaly_rows) if anomaly_rows else None

        # Build summary
        summary = self._build_summary(records, mlnx_df)

        # Sort by severity and error count
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r["TotalErrors"]
        ))

        return MlnxCountersResult(data=records[:2000], anomalies=anomalies, summary=summary)

    def _build_summary(self, records: List[Dict], raw_df: pd.DataFrame) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {"total_ports_with_activity": 0}

        total_rnr = sum(r.get("RNRRetries", 0) for r in records)
        total_timeouts = sum(r.get("Timeouts", 0) for r in records)
        total_errors = sum(r.get("TotalErrors", 0) for r in records)

        critical_count = sum(1 for r in records if r.get("Severity") == "critical")
        warning_count = sum(1 for r in records if r.get("Severity") == "warning")

        return {
            "total_ports_analyzed": len(raw_df),
            "total_ports_with_activity": len(records),
            "total_rnr_retries": total_rnr,
            "total_timeouts": total_timeouts,
            "total_qp_errors": total_errors,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "ports_with_rnr": sum(1 for r in records if r.get("RNRRetries", 0) > 0),
            "ports_with_timeouts": sum(1 for r in records if r.get("Timeouts", 0) > 0),
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
