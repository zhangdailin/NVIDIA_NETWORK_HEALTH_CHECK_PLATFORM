"""Buffer Histogram service for buffer congestion analysis.

Uses tables:
- PERFORMANCE_HISTOGRAM_BUFFER_DATA: Buffer congestion histograms (50,828 rows typical)
- PERFORMANCE_HISTOGRAM_BUFFER_CONTROL: Buffer histogram control settings
- PERFORMANCE_HISTOGRAM_INFO: Histogram configuration summary
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
class BufferHistogramResult:
    """Result from Buffer Histogram analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class BufferHistogramService:
    """Analyze buffer congestion histograms for bottleneck detection."""

    # Buffer utilization thresholds
    HIGH_UTILIZATION_THRESHOLD = 80  # Percentage
    CRITICAL_UTILIZATION_THRESHOLD = 95

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> BufferHistogramResult:
        """Run Buffer Histogram analysis."""
        buffer_data_df = self._try_read_table("PERFORMANCE_HISTOGRAM_BUFFER_DATA")
        buffer_control_df = self._try_read_table("PERFORMANCE_HISTOGRAM_BUFFER_CONTROL")
        histogram_info_df = self._try_read_table("PERFORMANCE_HISTOGRAM_INFO")

        if buffer_data_df.empty:
            return BufferHistogramResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        high_utilization_count = 0
        critical_utilization_count = 0
        vl_distribution: Dict[int, int] = defaultdict(int)
        buffer_type_distribution: Dict[str, int] = defaultdict(int)
        max_utilization = 0.0
        total_samples = 0

        # Get column names for dynamic analysis
        columns = list(buffer_data_df.columns)
        bin_columns = [c for c in columns if c.startswith("bin") or c.startswith("Bin")]

        for _, row in buffer_data_df.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("NodeGUID", "")))
            port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
            vl = self._safe_int(row.get("VL", 0))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Buffer type
            buffer_type = str(row.get("BufferType", row.get("Type", "Unknown")))
            buffer_type_distribution[buffer_type] += 1

            # Track VL distribution
            vl_distribution[vl] += 1

            # Extract bin values
            bin_values = []
            for col in bin_columns:
                bin_values.append(self._safe_int(row.get(col, 0)))

            # Calculate utilization metrics
            total_count = sum(bin_values)
            total_samples += total_count

            # Higher bins indicate more congestion
            if total_count > 0 and len(bin_values) > 0:
                # Calculate weighted average (higher bins = more congestion)
                weighted_sum = sum(i * v for i, v in enumerate(bin_values))
                avg_bin = weighted_sum / total_count if total_count > 0 else 0
                utilization_pct = (avg_bin / max(len(bin_values) - 1, 1)) * 100

                # Count high bins (top 25% of bins)
                high_bin_threshold = len(bin_values) * 3 // 4
                high_bin_count = sum(bin_values[high_bin_threshold:])
                high_bin_pct = (high_bin_count / total_count * 100) if total_count > 0 else 0
            else:
                utilization_pct = 0
                high_bin_pct = 0
                avg_bin = 0

            max_utilization = max(max_utilization, utilization_pct)

            # Determine severity
            issues = []
            severity = "normal"

            if high_bin_pct >= self.CRITICAL_UTILIZATION_THRESHOLD:
                issues.append(f"Critical buffer congestion: {high_bin_pct:.1f}% in high bins")
                severity = "critical"
                critical_utilization_count += 1
            elif high_bin_pct >= self.HIGH_UTILIZATION_THRESHOLD:
                issues.append(f"High buffer utilization: {high_bin_pct:.1f}% in high bins")
                severity = "warning"
                high_utilization_count += 1

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "VL": vl,
                "BufferType": buffer_type,
                "TotalSamples": total_count,
                "AvgBin": round(avg_bin, 2),
                "UtilizationPct": round(utilization_pct, 1),
                "HighBinPct": round(high_bin_pct, 1),
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }

            # Add individual bin values for first 10 bins
            for i, val in enumerate(bin_values[:10]):
                record[f"Bin{i}"] = val

            records.append(record)

        # Get histogram info summary
        histogram_config = {}
        if not histogram_info_df.empty:
            for _, row in histogram_info_df.iterrows():
                node_guid = str(row.get("NodeGuid", ""))
                histogram_config[node_guid] = {
                    "enabled": self._safe_bool(row.get("Enabled", True)),
                    "num_bins": self._safe_int(row.get("NumBins", 0)),
                }

        # Build summary
        summary = {
            "total_entries": len(buffer_data_df),
            "total_samples": total_samples,
            "high_utilization_count": high_utilization_count,
            "critical_utilization_count": critical_utilization_count,
            "max_utilization_pct": round(max_utilization, 1),
            "vl_distribution": dict(sorted(vl_distribution.items())),
            "buffer_type_distribution": dict(sorted(buffer_type_distribution.items(), key=lambda x: -x[1])),
            "histogram_nodes_configured": len(histogram_config),
            "control_entries": len(buffer_control_df),
        }

        # Sort by severity and utilization
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("HighBinPct", 0)
        ))

        return BufferHistogramResult(data=records[:2000], anomalies=None, summary=summary)

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
    def _safe_bool(value: object) -> bool:
        try:
            if pd.isna(value):
                return False
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return int(value) != 0
            return str(value).strip().lower() in ("1", "true", "yes", "enabled")
        except (TypeError, ValueError):
            return False
