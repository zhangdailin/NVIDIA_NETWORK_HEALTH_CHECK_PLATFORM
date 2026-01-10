"""Per-Lane Performance service for lane-level PCI/Physical diagnostics.

Uses tables:
- P_DB4: Per-lane PCI Express performance data (~100K rows, 165 columns for equalizer taps)
- P_DB5: Per-lane extended performance data
- PHY_DB4: Physical layer per-lane diagnostics

This service provides lane-level analysis which is 8x more granular than port-level.
Lane-level analysis can identify specific lanes with issues (e.g., one bad lane in x16 link).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class PerLanePerformanceResult:
    """Result from Per-Lane Performance analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PerLanePerformanceService:
    """Analyze per-lane PCI and physical layer performance."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PerLanePerformanceResult:
        """Run Per-Lane Performance analysis."""
        p_db4_df = self._try_read_table("P_DB4")
        p_db5_df = self._try_read_table("P_DB5")
        phy_db4_df = self._try_read_table("PHY_DB4")

        if p_db4_df.empty and p_db5_df.empty and phy_db4_df.empty:
            return PerLanePerformanceResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        total_lanes = 0
        lanes_with_issues = 0
        lanes_with_eq_issues = 0
        ports_analyzed: set = set()

        # Error distribution by lane
        lane_error_distribution: Dict[int, int] = defaultdict(int)
        eq_tap_warnings: Dict[str, int] = defaultdict(int)

        # Process P_DB4 (primary per-lane source)
        if not p_db4_df.empty:
            # Group by port for aggregation
            port_lane_data: Dict[str, List[Dict]] = defaultdict(list)

            for _, row in p_db4_df.iterrows():
                node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                lane_num = self._safe_int(row.get("LaneNum", row.get("Lane", 0)))
                port_key = f"{node_guid}:{port_num}"
                ports_analyzed.add(port_key)
                total_lanes += 1

                # Equalizer taps (165 columns in P_DB4)
                eq_taps = {}
                eq_issues = []

                # Common equalizer tap columns
                tap_columns = [
                    "PreCursor", "MainCursor", "PostCursor",
                    "PreCursor1", "PreCursor2", "PreCursor3",
                    "PostCursor1", "PostCursor2", "PostCursor3",
                    "DFE_Tap1", "DFE_Tap2", "DFE_Tap3", "DFE_Tap4",
                    "DFE_Tap5", "DFE_Tap6", "DFE_Tap7", "DFE_Tap8",
                    "CTLE_Gain", "CTLE_Pole", "CTLE_Zero",
                    "VGA_Gain", "AGC_Gain",
                ]

                for col in tap_columns:
                    if col in row.index:
                        val = self._safe_float(row.get(col, 0))
                        eq_taps[col] = val
                        # Check for out-of-range equalizer values
                        if abs(val) > 100:  # Arbitrary threshold
                            eq_issues.append(f"{col}={val}")
                            eq_tap_warnings[col] += 1

                if eq_issues:
                    lanes_with_eq_issues += 1

                # Eye diagram metrics (if available)
                eye_height = self._safe_float(row.get("EyeHeight", row.get("EyeHeightMV", 0)))
                eye_width = self._safe_float(row.get("EyeWidth", row.get("EyeWidthPS", 0)))
                eye_grade = str(row.get("EyeGrade", ""))

                # Error counters
                lane_errors = self._safe_int(row.get("Errors", row.get("LaneErrors", 0)))
                bit_errors = self._safe_int(row.get("BitErrors", 0))
                symbol_errors = self._safe_int(row.get("SymbolErrors", 0))

                if lane_errors > 0 or bit_errors > 0 or symbol_errors > 0:
                    lane_error_distribution[lane_num] += 1
                    lanes_with_issues += 1

                # Signal quality
                snr_db = self._safe_float(row.get("SNR_dB", row.get("SNR", 0)))
                jitter_ps = self._safe_float(row.get("Jitter_ps", row.get("Jitter", 0)))

                # Link training
                link_training_status = str(row.get("LinkTrainingStatus", row.get("LTStatus", "")))
                eq_done = self._safe_bool(row.get("EQDone", row.get("EqualizationDone", False)))

                lane_data = {
                    "lane_num": lane_num,
                    "eye_height": eye_height,
                    "eye_width": eye_width,
                    "eye_grade": eye_grade,
                    "lane_errors": lane_errors,
                    "bit_errors": bit_errors,
                    "symbol_errors": symbol_errors,
                    "snr_db": snr_db,
                    "jitter_ps": jitter_ps,
                    "eq_done": eq_done,
                    "eq_issues": eq_issues,
                    "eq_taps": eq_taps,
                }

                port_lane_data[port_key].append(lane_data)

            # Aggregate per-port records with lane details
            for port_key, lanes in port_lane_data.items():
                parts = port_key.split(":")
                node_guid = parts[0]
                port_num = int(parts[1]) if len(parts) > 1 else 0

                node_name = topology.node_label(node_guid) if topology else node_guid
                num_lanes = len(lanes)

                # Find worst lane
                worst_lane = max(lanes, key=lambda l: l["lane_errors"] + l["bit_errors"])
                avg_eye_height = sum(l["eye_height"] for l in lanes) / num_lanes if num_lanes > 0 else 0
                min_eye_height = min(l["eye_height"] for l in lanes) if lanes else 0
                avg_snr = sum(l["snr_db"] for l in lanes) / num_lanes if num_lanes > 0 else 0
                min_snr = min(l["snr_db"] for l in lanes) if lanes else 0

                # Total errors across lanes
                total_lane_errors = sum(l["lane_errors"] for l in lanes)
                total_bit_errors = sum(l["bit_errors"] for l in lanes)
                total_symbol_errors = sum(l["symbol_errors"] for l in lanes)

                # Lanes with issues
                bad_lanes = [l for l in lanes if l["lane_errors"] > 0 or l["eq_issues"]]
                eq_issues_lanes = [l for l in lanes if l["eq_issues"]]

                # Determine severity
                issues = []
                severity = "normal"

                if total_bit_errors > 0:
                    issues.append(f"Bit errors: {total_bit_errors} across {len(bad_lanes)} lanes")
                    severity = "critical"
                elif total_lane_errors > 0:
                    issues.append(f"Lane errors: {total_lane_errors}")
                    severity = "warning"
                elif eq_issues_lanes:
                    issues.append(f"Equalizer issues on {len(eq_issues_lanes)} lanes")
                    severity = "warning"
                elif min_eye_height > 0 and min_eye_height < 20:
                    issues.append(f"Low min eye height: {min_eye_height}mV (Lane {worst_lane['lane_num']})")
                    severity = "warning"
                elif min_snr > 0 and min_snr < 12:
                    issues.append(f"Low min SNR: {min_snr:.1f}dB")
                    severity = "info"

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_num,
                    "NumLanes": num_lanes,
                    "TotalLaneErrors": total_lane_errors,
                    "TotalBitErrors": total_bit_errors,
                    "TotalSymbolErrors": total_symbol_errors,
                    "LanesWithIssues": len(bad_lanes),
                    "LanesWithEQIssues": len(eq_issues_lanes),
                    "AvgEyeHeightMV": round(avg_eye_height, 1),
                    "MinEyeHeightMV": round(min_eye_height, 1),
                    "AvgSNR_dB": round(avg_snr, 2),
                    "MinSNR_dB": round(min_snr, 2),
                    "WorstLane": worst_lane["lane_num"],
                    "WorstLaneErrors": worst_lane["lane_errors"],
                    "AllLanesEQDone": all(l["eq_done"] for l in lanes),
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }

                # Add details for worst 3 lanes
                sorted_lanes = sorted(lanes, key=lambda l: -(l["lane_errors"] + l["bit_errors"]))[:3]
                for i, lane in enumerate(sorted_lanes):
                    record[f"Lane{i}_Num"] = lane["lane_num"]
                    record[f"Lane{i}_Errors"] = lane["lane_errors"]
                    record[f"Lane{i}_EyeH"] = round(lane["eye_height"], 1)
                    record[f"Lane{i}_SNR"] = round(lane["snr_db"], 2)

                records.append(record)

        # If P_DB4 was empty but PHY_DB4 exists, process that
        elif not phy_db4_df.empty:
            port_lane_data: Dict[str, List[Dict]] = defaultdict(list)

            for _, row in phy_db4_df.iterrows():
                node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                lane_num = self._safe_int(row.get("LaneNum", row.get("Lane", 0)))
                port_key = f"{node_guid}:{port_num}"
                ports_analyzed.add(port_key)
                total_lanes += 1

                # PHY_DB4 has physical layer diagnostics
                phy_status = str(row.get("Status", ""))
                signal_detect = self._safe_bool(row.get("SignalDetect", True))
                cdr_lock = self._safe_bool(row.get("CDRLock", True))

                lane_data = {
                    "lane_num": lane_num,
                    "phy_status": phy_status,
                    "signal_detect": signal_detect,
                    "cdr_lock": cdr_lock,
                }

                if not signal_detect or not cdr_lock:
                    lanes_with_issues += 1
                    lane_error_distribution[lane_num] += 1

                port_lane_data[port_key].append(lane_data)

            # Aggregate per-port
            for port_key, lanes in port_lane_data.items():
                parts = port_key.split(":")
                node_guid = parts[0]
                port_num = int(parts[1]) if len(parts) > 1 else 0

                node_name = topology.node_label(node_guid) if topology else node_guid
                num_lanes = len(lanes)

                no_signal_lanes = [l for l in lanes if not l["signal_detect"]]
                no_cdr_lanes = [l for l in lanes if not l["cdr_lock"]]

                issues = []
                severity = "normal"

                if no_signal_lanes:
                    issues.append(f"No signal on {len(no_signal_lanes)} lanes")
                    severity = "critical"
                elif no_cdr_lanes:
                    issues.append(f"CDR not locked on {len(no_cdr_lanes)} lanes")
                    severity = "warning"

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_num,
                    "NumLanes": num_lanes,
                    "LanesNoSignal": len(no_signal_lanes),
                    "LanesNoCDR": len(no_cdr_lanes),
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)

        # Build summary
        critical_ports = sum(1 for r in records if r.get("Severity") == "critical")
        warning_ports = sum(1 for r in records if r.get("Severity") == "warning")
        ports_with_issue = sum(1 for r in records if r.get("LanesWithIssues", 0) > 0)
        ports_with_eq_issue = sum(1 for r in records if r.get("LanesWithEQIssues", 0) > 0)

        summary = {
            "total_lanes_analyzed": total_lanes,
            "total_ports_analyzed": len(ports_analyzed),
            "lanes_with_issues": lanes_with_issues,
            "lanes_with_eq_issues": lanes_with_eq_issues,
            "issue_rate_pct": round(lanes_with_issues / max(total_lanes, 1) * 100, 2),
            "lane_error_distribution": dict(sorted(lane_error_distribution.items())),
            "eq_tap_warnings": dict(sorted(eq_tap_warnings.items(), key=lambda x: -x[1])[:10]),
            "p_db4_rows": len(p_db4_df),
            "p_db5_rows": len(p_db5_df),
            "phy_db4_rows": len(phy_db4_df),
            "critical_ports": critical_ports,
            "warning_ports": warning_ports,
            "ports_with_lane_issues": ports_with_issue,
            "ports_with_eq_issues": ports_with_eq_issue,
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("TotalLaneErrors", 0),
            -r.get("LanesWithIssues", 0)
        ))

        return PerLanePerformanceResult(data=records[:2000], anomalies=None, summary=summary)

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

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            if pd.isna(value):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_bool(value: object) -> bool:
        try:
            if pd.isna(value):
                return False
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return int(value) != 0
            return str(value).strip().lower() in ("1", "true", "yes", "locked", "detected")
        except (TypeError, ValueError):
            return False
