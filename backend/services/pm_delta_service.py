"""Performance Monitor Delta analysis using PM_DELTA table.

Provides:
- Real-time counter changes during ibdiagnet run
- FEC correction activity analysis
- Traffic statistics during diagnostic window
- Active error detection
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

# Thresholds for detecting active issues
FEC_UNCORRECTABLE_THRESHOLD = 10
FEC_CORRECTABLE_WARNING = 100000
RELAY_ERROR_THRESHOLD = 1


@dataclass
class PmDeltaResult:
    """Result from PM Delta analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PmDeltaService:
    """Analyze performance counter deltas from ibdiagnet run."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PmDeltaResult:
        """Run PM Delta analysis."""
        pm_df = self._try_read_table("PM_DELTA")

        if pm_df.empty:
            return PmDeltaResult()

        topology = self._get_topology()
        records = []
        anomaly_rows = []

        for _, row in pm_df.iterrows():
            node_guid = str(row.get("NodeGUID", ""))
            port_num = self._safe_int(row.get("PortNumber"))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Extract key counters
            xmit_data = self._safe_int(row.get("PortXmitDataExtended", 0))
            rcv_data = self._safe_int(row.get("PortRcvDataExtended", 0))
            xmit_pkts = self._safe_int(row.get("PortXmitPktsExtended", 0))
            rcv_pkts = self._safe_int(row.get("PortRcvPktsExtended", 0))
            xmit_wait = self._safe_int(row.get("PortXmitWaitExt", 0))

            # FEC counters
            fec_corrected = self._safe_int(row.get("PortFECCorrectedSymbolCounter", 0))
            fec_correctable_blocks = self._safe_int(row.get("PortFECCorrectableBlockCounter", 0))
            fec_uncorrectable = self._safe_int(row.get("PortFECUncorrectableBlockCounter", 0))

            # Per-lane FEC
            fec_lane0 = self._safe_int(row.get("FECCorrectedSymbolCounterLane[0]", 0))
            fec_lane1 = self._safe_int(row.get("FECCorrectedSymbolCounterLane[1]", 0))
            fec_lane2 = self._safe_int(row.get("FECCorrectedSymbolCounterLane[2]", 0))
            fec_lane3 = self._safe_int(row.get("FECCorrectedSymbolCounterLane[3]", 0))

            # Error counters
            relay_errors = self._safe_int(row.get("PortRcvSwitchRelayErrorsExt", 0))
            dlid_errors = self._safe_int(row.get("PortDLIDMappingErrors", 0))

            # Skip ports with no activity
            total_activity = xmit_data + rcv_data + fec_corrected + fec_uncorrectable
            if total_activity == 0:
                continue

            # Determine severity
            severity = "normal"
            issues = []

            if fec_uncorrectable >= FEC_UNCORRECTABLE_THRESHOLD:
                severity = "critical"
                issues.append(f"FEC uncorrectable blocks: {fec_uncorrectable}")

            if fec_corrected >= FEC_CORRECTABLE_WARNING:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"High FEC corrections: {fec_corrected:,}")

            if relay_errors > 0:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"Switch relay errors: {relay_errors}")

            if dlid_errors > 0:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"DLID mapping errors: {dlid_errors}")

            # Calculate data rates (approximate, assuming 1 second sample)
            xmit_gb = xmit_data / (1024 ** 3) if xmit_data > 0 else 0
            rcv_gb = rcv_data / (1024 ** 3) if rcv_data > 0 else 0

            # Calculate FEC lane imbalance
            lane_values = [fec_lane0, fec_lane1, fec_lane2, fec_lane3]
            lane_max = max(lane_values) if lane_values else 0
            lane_min = min(lane_values) if lane_values else 0
            lane_imbalance = (lane_max - lane_min) / max(lane_max, 1) * 100 if lane_max > 0 else 0

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "XmitDataGB": round(xmit_gb, 3),
                "RcvDataGB": round(rcv_gb, 3),
                "XmitPkts": xmit_pkts,
                "RcvPkts": rcv_pkts,
                "XmitWait": xmit_wait,
                "FECCorrected": fec_corrected,
                "FECCorrectableBlocks": fec_correctable_blocks,
                "FECUncorrectable": fec_uncorrectable,
                "FECLane0": fec_lane0,
                "FECLane1": fec_lane1,
                "FECLane2": fec_lane2,
                "FECLane3": fec_lane3,
                "FECLaneImbalancePct": round(lane_imbalance, 1),
                "RelayErrors": relay_errors,
                "DLIDErrors": dlid_errors,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

            # Track anomalies
            if fec_uncorrectable >= FEC_UNCORRECTABLE_THRESHOLD:
                anomaly_rows.append({
                    "NodeGUID": node_guid,
                    "PortNumber": port_num,
                    IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_FEC_UNCORRECTABLE),
                    IBH_ANOMALY_AGG_WEIGHT: 1.0,
                })
            if relay_errors > 0:
                anomaly_rows.append({
                    "NodeGUID": node_guid,
                    "PortNumber": port_num,
                    IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_RELAY_ERROR),
                    IBH_ANOMALY_AGG_WEIGHT: 0.5,
                })

        # Build anomaly DataFrame
        anomalies = pd.DataFrame(anomaly_rows) if anomaly_rows else None

        # Build summary
        summary = self._build_summary(records, pm_df)

        # Sort by severity and FEC uncorrectable
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("FECUncorrectable", 0),
            -r.get("FECCorrected", 0)
        ))

        return PmDeltaResult(data=records[:2000], anomalies=anomalies, summary=summary)

    def _build_summary(self, records: List[Dict], raw_df: pd.DataFrame) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {"total_ports_with_activity": 0}

        total_xmit = sum(r.get("XmitDataGB", 0) for r in records)
        total_rcv = sum(r.get("RcvDataGB", 0) for r in records)
        total_fec_corrected = sum(r.get("FECCorrected", 0) for r in records)
        total_fec_uncorrectable = sum(r.get("FECUncorrectable", 0) for r in records)

        critical_count = sum(1 for r in records if r.get("Severity") == "critical")
        warning_count = sum(1 for r in records if r.get("Severity") == "warning")

        return {
            "total_ports_sampled": len(raw_df),
            "ports_with_activity": len(records),
            "total_xmit_gb": round(total_xmit, 2),
            "total_rcv_gb": round(total_rcv, 2),
            "total_fec_corrected": total_fec_corrected,
            "total_fec_uncorrectable": total_fec_uncorrectable,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "ports_with_fec_activity": sum(1 for r in records if r.get("FECCorrected", 0) > 0),
            "ports_with_errors": sum(1 for r in records if r.get("RelayErrors", 0) > 0 or r.get("DLIDErrors", 0) > 0),
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
