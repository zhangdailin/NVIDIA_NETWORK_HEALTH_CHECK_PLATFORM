"""Adaptive Routing and RN Counters analysis service.

Uses tables:
- RN_COUNTERS: Adaptive routing packet counters (port_rcv_rn_pkt, port_xmit_rn_pkt, port_ar_trials)
- HBF_PORT_COUNTERS: Hash-based forwarding statistics
- FAST_RECOVERY_COUNTERS: Fast recovery error/warning counts
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


@dataclass
class RoutingResult:
    """Result from routing analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class RoutingService:
    """Analyze adaptive routing, RN counters, and HBF statistics from ibdiagnet data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> RoutingResult:
        """Run routing analysis combining RN_COUNTERS, HBF_PORT_COUNTERS, FAST_RECOVERY_COUNTERS."""
        records = []
        anomaly_rows = []

        # Load RN counters (adaptive routing)
        rn_df = self._try_read_table("RN_COUNTERS")
        hbf_df = self._try_read_table("HBF_PORT_COUNTERS")
        fr_df = self._try_read_table("FAST_RECOVERY_COUNTERS")

        if rn_df.empty and hbf_df.empty:
            return RoutingResult()

        topology = self._get_topology()

        # Build lookup for HBF counters
        hbf_lookup = {}
        if not hbf_df.empty:
            for _, row in hbf_df.iterrows():
                key = (str(row.get("NodeGUID", "")), int(row.get("PortNumber", 0)))
                hbf_lookup[key] = {
                    "StaticForwarding": self._safe_int(row.get("rx_pkt_forwarding_static")),
                    "HBFForwarding": self._safe_int(row.get("rx_pkt_forwarding_hbf")),
                    "ARForwarding": self._safe_int(row.get("rx_pkt_forwarding_ar")),
                    "HBFFallbackLocal": self._safe_int(row.get("rx_pkt_hbf_fallback_local")),
                    "HBFFallbackRemote": self._safe_int(row.get("rx_pkt_hbf_fallback_remote")),
                }

        # Build lookup for Fast Recovery
        fr_lookup = {}
        if not fr_df.empty:
            for _, row in fr_df.iterrows():
                key = (str(row.get("NodeGUID", "")), int(row.get("PortNumber", 0)))
                if key not in fr_lookup:
                    fr_lookup[key] = {"errors": 0, "warnings": 0}
                fr_lookup[key]["errors"] += self._safe_int(row.get("num_errors"))
                fr_lookup[key]["warnings"] += self._safe_int(row.get("num_warnings"))

        # Process RN counters as primary source
        if not rn_df.empty:
            for _, row in rn_df.iterrows():
                node_guid = str(row.get("NodeGUID", ""))
                port_number = int(row.get("PortNumber", 0))
                key = (node_guid, port_number)

                node_name = topology.node_label(node_guid) if topology else node_guid

                # RN packet counters
                rcv_rn_pkt = self._safe_int(row.get("port_rcv_rn_pkt"))
                xmit_rn_pkt = self._safe_int(row.get("port_xmit_rn_pkt"))
                rcv_rn_error = self._safe_int(row.get("port_rcv_rn_error"))
                ar_trials = self._safe_int(row.get("port_ar_trials"))
                pfrn_error = self._safe_int(row.get("pfrn_received_error"))

                # Get HBF data
                hbf_data = hbf_lookup.get(key, {})
                fr_data = fr_lookup.get(key, {"errors": 0, "warnings": 0})

                # Calculate routing effectiveness
                total_forwarded = (
                    hbf_data.get("StaticForwarding", 0) +
                    hbf_data.get("HBFForwarding", 0) +
                    hbf_data.get("ARForwarding", 0)
                )
                ar_utilization = 0.0
                if total_forwarded > 0:
                    ar_utilization = (hbf_data.get("ARForwarding", 0) / total_forwarded) * 100

                # Determine severity
                severity = "normal"
                issues = []

                if rcv_rn_error > 0 or pfrn_error > 0:
                    severity = "warning"
                    issues.append(f"RN errors: {rcv_rn_error + pfrn_error}")

                if fr_data["errors"] > 0:
                    severity = "critical"
                    issues.append(f"Fast recovery errors: {fr_data['errors']}")

                if hbf_data.get("HBFFallbackLocal", 0) > 0 or hbf_data.get("HBFFallbackRemote", 0) > 0:
                    if severity != "critical":
                        severity = "warning"
                    issues.append("HBF fallback detected")

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_number,
                    # RN Counters
                    "RcvRNPackets": rcv_rn_pkt,
                    "XmitRNPackets": xmit_rn_pkt,
                    "RNErrors": rcv_rn_error + pfrn_error,
                    "ARTrials": ar_trials,
                    # HBF Counters
                    "StaticForwarding": hbf_data.get("StaticForwarding", 0),
                    "HBFForwarding": hbf_data.get("HBFForwarding", 0),
                    "ARForwarding": hbf_data.get("ARForwarding", 0),
                    "HBFFallbackLocal": hbf_data.get("HBFFallbackLocal", 0),
                    "HBFFallbackRemote": hbf_data.get("HBFFallbackRemote", 0),
                    "ARUtilizationPct": round(ar_utilization, 2),
                    # Fast Recovery
                    "FRErrors": fr_data["errors"],
                    "FRWarnings": fr_data["warnings"],
                    # Status
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)

                # Track anomalies with proper anomaly types
                if fr_data["errors"] > 0:
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_number,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_ROUTING_FR_ERROR),
                        IBH_ANOMALY_AGG_WEIGHT: 1.0,
                    })
                if rcv_rn_error > 0 or pfrn_error > 0:
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_number,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_ROUTING_RN_ERROR),
                        IBH_ANOMALY_AGG_WEIGHT: 0.5,
                    })
                if hbf_data.get("HBFFallbackLocal", 0) > 0 or hbf_data.get("HBFFallbackRemote", 0) > 0:
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_number,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_ROUTING_HBF_FALLBACK),
                        IBH_ANOMALY_AGG_WEIGHT: 0.5,
                    })

        # Build anomaly DataFrame
        anomalies = pd.DataFrame(anomaly_rows) if anomaly_rows else None

        # Build summary
        summary = self._build_summary(records)

        return RoutingResult(data=records, anomalies=anomalies, summary=summary)

    def _build_summary(self, records: List[Dict]) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        total_ar_pkts = sum(r.get("ARForwarding", 0) for r in records)
        total_hbf_pkts = sum(r.get("HBFForwarding", 0) for r in records)
        total_static_pkts = sum(r.get("StaticForwarding", 0) for r in records)
        total_rn_errors = sum(r.get("RNErrors", 0) for r in records)
        total_fr_errors = sum(r.get("FRErrors", 0) for r in records)
        ports_with_ar = sum(1 for r in records if r.get("ARForwarding", 0) > 0)
        ports_with_hbf = sum(1 for r in records if r.get("HBFForwarding", 0) > 0)

        return {
            "total_ports": len(records),
            "ports_with_ar_traffic": ports_with_ar,
            "ports_with_hbf_traffic": ports_with_hbf,
            "total_ar_packets": total_ar_pkts,
            "total_hbf_packets": total_hbf_pkts,
            "total_static_packets": total_static_pkts,
            "total_rn_errors": total_rn_errors,
            "total_fr_errors": total_fr_errors,
            "critical_count": sum(1 for r in records if r.get("Severity") == "critical"),
            "warning_count": sum(1 for r in records if r.get("Severity") == "warning"),
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
