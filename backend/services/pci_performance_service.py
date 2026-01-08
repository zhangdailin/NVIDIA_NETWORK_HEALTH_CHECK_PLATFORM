"""PCI Express Performance service for PCIe link monitoring.

Uses tables:
- P_DB1: PCI Express link capabilities and status (node-level, ~6K rows)
- P_DB2: PCI Express extended capabilities (~6K rows)
- P_DB8: PCI Express AER (Advanced Error Reporting) counters (~6K rows)
- WARNINGS_PCI_DEGRADATION_CHECK: PCI speed/width degradation warnings

This service monitors PCIe link health which directly impacts InfiniBand performance.
PCIe degradation (e.g., Gen4 -> Gen3) can bottleneck HCA throughput.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

# PCIe Generation speed mappings (GT/s)
PCIE_GEN_SPEEDS = {
    1: 2.5,   # Gen1
    2: 5.0,   # Gen2
    3: 8.0,   # Gen3
    4: 16.0,  # Gen4
    5: 32.0,  # Gen5
    6: 64.0,  # Gen6
}

# PCIe width to lanes mapping
PCIE_WIDTH_LANES = {
    1: 1, 2: 2, 4: 4, 8: 8, 12: 12, 16: 16, 32: 32,
}


@dataclass
class PciPerformanceResult:
    """Result from PCI Performance analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PciPerformanceService:
    """Analyze PCIe link performance and degradation."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PciPerformanceResult:
        """Run PCI Performance analysis."""
        p_db1_df = self._try_read_table("P_DB1")
        p_db2_df = self._try_read_table("P_DB2")
        p_db8_df = self._try_read_table("P_DB8")
        pci_warnings_df = self._try_read_table("WARNINGS_PCI_DEGRADATION_CHECK")

        if p_db1_df.empty and p_db2_df.empty and p_db8_df.empty:
            return PciPerformanceResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        gen_distribution: Dict[int, int] = defaultdict(int)
        width_distribution: Dict[int, int] = defaultdict(int)
        degraded_count = 0
        aer_error_count = 0
        total_nodes = 0
        max_gen = 0
        total_bandwidth_gbps = 0.0

        # Build P_DB2 lookup (extended capabilities)
        p_db2_lookup = {}
        if not p_db2_df.empty:
            for _, row in p_db2_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                key = f"{guid}:{port}"
                p_db2_lookup[key] = {
                    "max_link_speed": self._safe_int(row.get("MaxLinkSpeed", 0)),
                    "max_link_width": self._safe_int(row.get("MaxLinkWidth", 0)),
                    "aspm_support": str(row.get("ASPMSupport", "")),
                    "l0s_exit_latency": self._safe_int(row.get("L0sExitLatency", 0)),
                    "l1_exit_latency": self._safe_int(row.get("L1ExitLatency", 0)),
                }

        # Build P_DB8 lookup (AER counters)
        p_db8_lookup = {}
        if not p_db8_df.empty:
            for _, row in p_db8_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                key = f"{guid}:{port}"
                p_db8_lookup[key] = {
                    "correctable_errors": self._safe_int(row.get("CorrectableErrors", row.get("CorrErrors", 0))),
                    "uncorrectable_errors": self._safe_int(row.get("UncorrectableErrors", row.get("UncorrErrors", 0))),
                    "fatal_errors": self._safe_int(row.get("FatalErrors", 0)),
                    "receiver_errors": self._safe_int(row.get("ReceiverErrors", row.get("RxErrors", 0))),
                    "bad_tlp": self._safe_int(row.get("BadTLP", 0)),
                    "bad_dllp": self._safe_int(row.get("BadDLLP", 0)),
                    "replay_num_rollover": self._safe_int(row.get("ReplayNumRollover", 0)),
                    "replay_timer_timeout": self._safe_int(row.get("ReplayTimerTimeout", 0)),
                }

        # Build degradation lookup from warnings
        degradation_lookup = {}
        if not pci_warnings_df.empty:
            for _, row in pci_warnings_df.iterrows():
                guid = str(row.get("NodeGUID", row.get("GUID", "")))
                port = self._safe_int(row.get("PortNumber", 0))
                key = f"{guid}:{port}"
                summary_text = str(row.get("Summary", ""))
                degradation_lookup[key] = {
                    "is_degraded": True,
                    "summary": summary_text,
                }

        # Process P_DB1 (primary source)
        if not p_db1_df.empty:
            for _, row in p_db1_df.iterrows():
                node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                key = f"{node_guid}:{port_num}"

                # Get node name
                node_name = topology.node_label(node_guid) if topology else node_guid
                total_nodes += 1

                # Link capabilities
                link_cap_speed = self._safe_int(row.get("LinkCapSpeed", row.get("MaxSpeed", 0)))
                link_cap_width = self._safe_int(row.get("LinkCapWidth", row.get("MaxWidth", 0)))

                # Current link status
                link_sta_speed = self._safe_int(row.get("LinkStaSpeed", row.get("CurrentSpeed", 0)))
                link_sta_width = self._safe_int(row.get("LinkStaWidth", row.get("CurrentWidth", 0)))

                # Track generation distribution
                gen_distribution[link_sta_speed] += 1
                width_distribution[link_sta_width] += 1
                max_gen = max(max_gen, link_sta_speed)

                # Calculate bandwidth
                speed_gtps = PCIE_GEN_SPEEDS.get(link_sta_speed, 0)
                lanes = link_sta_width if link_sta_width > 0 else 1
                # PCIe bandwidth: speed * lanes * encoding_efficiency (128b/130b for Gen3+)
                encoding_eff = 0.9846 if link_sta_speed >= 3 else 0.8  # 8b/10b for Gen1/2
                bandwidth_gbps = speed_gtps * lanes * encoding_eff
                total_bandwidth_gbps += bandwidth_gbps

                # Check for degradation
                is_speed_degraded = link_cap_speed > 0 and link_sta_speed < link_cap_speed
                is_width_degraded = link_cap_width > 0 and link_sta_width < link_cap_width
                degradation_info = degradation_lookup.get(key, {})
                is_degraded = is_speed_degraded or is_width_degraded or degradation_info.get("is_degraded", False)
                if is_degraded:
                    degraded_count += 1

                # Get extended info
                ext_info = p_db2_lookup.get(key, {})

                # Get AER counters
                aer_info = p_db8_lookup.get(key, {})
                total_aer_errors = (
                    aer_info.get("correctable_errors", 0) +
                    aer_info.get("uncorrectable_errors", 0) +
                    aer_info.get("fatal_errors", 0)
                )
                if total_aer_errors > 0:
                    aer_error_count += 1

                # Device and slot info
                device_id = str(row.get("DeviceID", row.get("DevID", "")))
                vendor_id = str(row.get("VendorID", row.get("VenID", "")))
                slot_cap = str(row.get("SlotCap", ""))

                # Determine severity
                issues = []
                severity = "normal"

                if aer_info.get("fatal_errors", 0) > 0:
                    issues.append(f"Fatal PCIe errors: {aer_info['fatal_errors']}")
                    severity = "critical"
                elif aer_info.get("uncorrectable_errors", 0) > 0:
                    issues.append(f"Uncorrectable errors: {aer_info['uncorrectable_errors']}")
                    severity = "critical"
                elif is_speed_degraded:
                    issues.append(f"Speed degraded: Gen{link_sta_speed} < Gen{link_cap_speed}")
                    severity = "critical"
                elif is_width_degraded:
                    issues.append(f"Width degraded: x{link_sta_width} < x{link_cap_width}")
                    severity = "warning"
                elif aer_info.get("correctable_errors", 0) > 100:
                    issues.append(f"High correctable errors: {aer_info['correctable_errors']}")
                    severity = "warning"
                elif aer_info.get("replay_timer_timeout", 0) > 0:
                    issues.append(f"Replay timeouts: {aer_info['replay_timer_timeout']}")
                    severity = "warning"

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_num,
                    "LinkCapSpeed": link_cap_speed,
                    "LinkCapWidth": link_cap_width,
                    "LinkStaSpeed": link_sta_speed,
                    "LinkStaWidth": link_sta_width,
                    "LinkCapSpeedGen": f"Gen{link_cap_speed}" if link_cap_speed > 0 else "N/A",
                    "LinkStaSpeedGen": f"Gen{link_sta_speed}" if link_sta_speed > 0 else "N/A",
                    "BandwidthGbps": round(bandwidth_gbps, 2),
                    "IsSpeedDegraded": is_speed_degraded,
                    "IsWidthDegraded": is_width_degraded,
                    "IsDegraded": is_degraded,
                    "DeviceID": device_id,
                    "VendorID": vendor_id,
                    "MaxLinkSpeed": ext_info.get("max_link_speed", 0),
                    "MaxLinkWidth": ext_info.get("max_link_width", 0),
                    "ASPMSupport": ext_info.get("aspm_support", ""),
                    "CorrectableErrors": aer_info.get("correctable_errors", 0),
                    "UncorrectableErrors": aer_info.get("uncorrectable_errors", 0),
                    "FatalErrors": aer_info.get("fatal_errors", 0),
                    "ReceiverErrors": aer_info.get("receiver_errors", 0),
                    "BadTLP": aer_info.get("bad_tlp", 0),
                    "BadDLLP": aer_info.get("bad_dllp", 0),
                    "ReplayRollover": aer_info.get("replay_num_rollover", 0),
                    "ReplayTimeout": aer_info.get("replay_timer_timeout", 0),
                    "TotalAERErrors": total_aer_errors,
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)

        # Build summary
        summary = {
            "total_nodes": total_nodes,
            "degraded_count": degraded_count,
            "aer_error_nodes": aer_error_count,
            "max_pcie_gen": max_gen,
            "gen_distribution": {f"Gen{k}": v for k, v in sorted(gen_distribution.items()) if k > 0},
            "width_distribution": {f"x{k}": v for k, v in sorted(width_distribution.items()) if k > 0},
            "total_bandwidth_tbps": round(total_bandwidth_gbps / 1000, 2),
            "avg_bandwidth_gbps": round(total_bandwidth_gbps / max(total_nodes, 1), 2),
            "degradation_pct": round(degraded_count / max(total_nodes, 1) * 100, 1),
            "p_db1_rows": len(p_db1_df),
            "p_db2_rows": len(p_db2_df),
            "p_db8_rows": len(p_db8_df),
        }

        # Sort by severity and errors
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("TotalAERErrors", 0),
            -1 if r.get("IsDegraded") else 0
        ))

        # Build anomalies DataFrame
        anomaly_records = []
        for r in records:
            if r["Severity"] in ("critical", "warning"):
                anomaly_records.append({
                    "NodeGUID": r["NodeGUID"],
                    "PortNumber": r["PortNumber"],
                    "PCI_DEGRADATION": 1.0 if r["IsDegraded"] else 0.0,
                    "PCI_AER_ERROR": min(r["TotalAERErrors"] / 100, 1.0) if r["TotalAERErrors"] > 0 else 0.0,
                })

        anomalies = pd.DataFrame(anomaly_records) if anomaly_records else None

        return PciPerformanceResult(data=records[:2000], anomalies=anomalies, summary=summary)

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
