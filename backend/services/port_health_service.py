"""Port health analysis service using PORT_GENERAL_COUNTERS, EXTENDED_PORT_INFO, FEC_MODE.

Provides detailed per-port health metrics including:
- ICRC errors, parity errors
- FEC mode configuration
- Port unhealthy reasons
- Retransmission mode status
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
class PortHealthResult:
    """Result from port health analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PortHealthService:
    """Analyze detailed port health from ibdiagnet data."""

    # FEC mode mappings based on ibdiagnet documentation
    FEC_MODE_NAMES = {
        0: "No FEC",
        1: "FireCode FEC",
        2: "RS-FEC (528,514)",
        4: "RS-FEC (544,514)",
        8: "Placeholder RS-FEC",
        16: "Zero Latency FEC",
    }

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PortHealthResult:
        """Run port health analysis."""
        records = []
        anomaly_rows = []

        # Load tables
        counters_df = self._try_read_table("PORT_GENERAL_COUNTERS")
        ext_info_df = self._try_read_table("EXTENDED_PORT_INFO")
        fec_df = self._try_read_table("FEC_MODE")

        if counters_df.empty and ext_info_df.empty:
            return PortHealthResult()

        topology = self._get_topology()

        # Build lookup dictionaries
        ext_info_lookup = {}
        if not ext_info_df.empty:
            for _, row in ext_info_df.iterrows():
                key = (str(row.get("NodeGuid", "")), int(row.get("PortNum", 0)))
                unhealthy_reason = self._safe_int(row.get("UnhealthyReason"))
                ext_info_lookup[key] = {
                    "UnhealthyReason": unhealthy_reason,
                    "UnhealthyReasonText": self._decode_unhealthy_reason(unhealthy_reason),
                    "FECModeActive": self._safe_int(row.get("FECModeActive")),
                    "RetransMode": self._safe_int(row.get("RetransMode")),
                    "LinkSpeedActive": str(row.get("LinkSpeedActive", "")),
                    "BwUtilization": self._safe_float(row.get("BwUtilization")),
                    "IsSpecialPort": bool(row.get("IsSpecialPort", 0)),
                }

        fec_lookup = {}
        if not fec_df.empty:
            for _, row in fec_df.iterrows():
                key = (str(row.get("NodeGuid", "")), int(row.get("PortNum", 0)))
                fec_active = self._safe_int(row.get("FECActv"))
                fec_lookup[key] = {
                    "FECActive": fec_active,
                    "FECActiveName": self.FEC_MODE_NAMES.get(fec_active, f"Unknown ({fec_active})"),
                    "HDRFECSupported": self._hex_to_bool(row.get("HDRFECSup")),
                    "HDRFECEnabled": self._hex_to_bool(row.get("HDRFECEn")),
                    "NDRFECSupported": self._hex_to_bool(row.get("NDRFECSup")),
                    "NDRFECEnabled": self._hex_to_bool(row.get("NDRFECEn")),
                }

        # Process PORT_GENERAL_COUNTERS as primary source
        if not counters_df.empty:
            for _, row in counters_df.iterrows():
                node_guid = str(row.get("NodeGUID", ""))
                port_number = int(row.get("PortNumber", 0))
                key = (node_guid, port_number)

                node_name = topology.node_label(node_guid) if topology else node_guid

                # Error counters
                rx_icrc_error = self._safe_int(row.get("rx_icrc_error"))
                tx_parity_error = self._safe_int(row.get("tx_parity_error"))
                xmit_discards = self._safe_int(row.get("contain_n_drain_xmit_discards"))
                rcv_discards = self._safe_int(row.get("contain_n_drain_rcv_discards"))

                # Get extended info
                ext_info = ext_info_lookup.get(key, {})
                fec_info = fec_lookup.get(key, {})

                # Determine severity
                severity = "normal"
                issues = []

                unhealthy_reason = ext_info.get("UnhealthyReason", 0)
                if unhealthy_reason > 0:
                    severity = "critical"
                    issues.append(f"Unhealthy: {ext_info.get('UnhealthyReasonText', 'Unknown')}")

                if rx_icrc_error > 0:
                    if severity != "critical":
                        severity = "warning"
                    issues.append(f"ICRC errors: {rx_icrc_error}")

                if tx_parity_error > 0:
                    severity = "critical"
                    issues.append(f"Parity errors: {tx_parity_error}")

                if xmit_discards > 0 or rcv_discards > 0:
                    if severity != "critical":
                        severity = "warning"
                    issues.append(f"Discards: TX={xmit_discards}, RX={rcv_discards}")

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_number,
                    # Error counters
                    "RxICRCErrors": rx_icrc_error,
                    "TxParityErrors": tx_parity_error,
                    "XmitDiscards": xmit_discards,
                    "RcvDiscards": rcv_discards,
                    # Extended info
                    "UnhealthyReason": unhealthy_reason,
                    "UnhealthyReasonText": ext_info.get("UnhealthyReasonText", ""),
                    "RetransMode": ext_info.get("RetransMode", 0),
                    "BwUtilization": ext_info.get("BwUtilization", 0),
                    # FEC info
                    "FECMode": fec_info.get("FECActiveName", "Unknown"),
                    "HDRFECEnabled": fec_info.get("HDRFECEnabled", False),
                    "NDRFECEnabled": fec_info.get("NDRFECEnabled", False),
                    # Status
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)

                # Track anomalies with proper anomaly types
                if unhealthy_reason > 0:
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_number,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_PORT_UNHEALTHY),
                        IBH_ANOMALY_AGG_WEIGHT: 1.0,
                    })
                if tx_parity_error > 0:
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_number,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_PORT_PARITY_ERROR),
                        IBH_ANOMALY_AGG_WEIGHT: 1.0,
                    })
                if rx_icrc_error > 0:
                    anomaly_rows.append({
                        "NodeGUID": node_guid,
                        "PortNumber": port_number,
                        IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_PORT_ICRC_ERROR),
                        IBH_ANOMALY_AGG_WEIGHT: 0.5,
                    })

        # Build anomaly DataFrame
        anomalies = pd.DataFrame(anomaly_rows) if anomaly_rows else None

        # Build summary
        summary = self._build_summary(records)

        return PortHealthResult(data=records, anomalies=anomalies, summary=summary)

    def _decode_unhealthy_reason(self, reason: int) -> str:
        """Decode unhealthy reason bitmask."""
        if reason == 0:
            return ""

        # Based on ibdiagnet documentation
        reasons = []
        if reason & 0x1:
            reasons.append("DLID routed")
        if reason & 0x2:
            reasons.append("SLID routed")
        if reason & 0x4:
            reasons.append("Raw traffic not allowed")
        if reason & 0x8:
            reasons.append("VL stalled")
        if reason & 0x10:
            reasons.append("Loopback")
        if reason & 0x20:
            reasons.append("High BER")
        if reason & 0x40:
            reasons.append("Credits stall")
        if reason & 0x80:
            reasons.append("Link down")

        return ", ".join(reasons) if reasons else f"Code {reason}"

    def _build_summary(self, records: List[Dict]) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        icrc_errors = sum(r.get("RxICRCErrors", 0) for r in records)
        parity_errors = sum(r.get("TxParityErrors", 0) for r in records)
        unhealthy_count = sum(1 for r in records if r.get("UnhealthyReason", 0) > 0)

        # FEC mode distribution
        fec_modes = {}
        for r in records:
            mode = r.get("FECMode", "Unknown")
            fec_modes[mode] = fec_modes.get(mode, 0) + 1

        return {
            "total_ports": len(records),
            "total_icrc_errors": icrc_errors,
            "total_parity_errors": parity_errors,
            "unhealthy_ports": unhealthy_count,
            "ports_with_errors": sum(1 for r in records if r.get("RxICRCErrors", 0) > 0 or r.get("TxParityErrors", 0) > 0),
            "fec_mode_distribution": fec_modes,
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
            # Handle hex strings like "0x0008"
            if isinstance(value, str) and value.startswith("0x"):
                return int(value, 16)
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: object) -> float:
        """Safely convert to float."""
        try:
            if pd.isna(value):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _hex_to_bool(value: object) -> bool:
        """Convert hex value to boolean (non-zero = True)."""
        try:
            if pd.isna(value):
                return False
            if isinstance(value, str) and value.startswith("0x"):
                return int(value, 16) != 0
            return int(float(value)) != 0
        except (TypeError, ValueError):
            return False
