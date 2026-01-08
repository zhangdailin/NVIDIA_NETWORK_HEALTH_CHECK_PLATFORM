"""Temperature sensor analysis service using TEMPERATURE_SENSORS table."""

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

# Temperature thresholds
TEMP_CRITICAL_THRESHOLD = 95  # Near high threshold
TEMP_WARNING_THRESHOLD = 80   # Getting warm
TEMP_NORMAL_THRESHOLD = 70    # Normal operating range


@dataclass
class TemperatureResult:
    """Result from temperature analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class TemperatureService:
    """Analyze switch/device temperature sensors from ibdiagnet data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> TemperatureResult:
        """Run temperature analysis."""
        index_table = self._get_index_table()

        if "TEMPERATURE_SENSORS" not in index_table.index:
            logger.info("TEMPERATURE_SENSORS table not found")
            return TemperatureResult()

        try:
            df = self._read_table("TEMPERATURE_SENSORS")
            if df.empty:
                return TemperatureResult()
        except Exception as e:
            logger.warning(f"Failed to read TEMPERATURE_SENSORS: {e}")
            return TemperatureResult()

        # Get topology for node name lookup
        topology = self._get_topology()

        # Process temperature data
        records = []
        anomaly_rows = []

        for _, row in df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            sensor_index = row.get("SensorIndex", 0)
            sensor_name = str(row.get("SensorName", "unknown"))
            temperature = self._safe_float(row.get("Temperature"))
            max_temperature = self._safe_float(row.get("MaxTemperature"))
            low_threshold = self._safe_float(row.get("LowThreshold"))
            high_threshold = self._safe_float(row.get("HighThreshold"))

            # Get node name from topology
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Determine severity
            severity = "normal"
            if high_threshold > 0 and temperature >= high_threshold:
                severity = "critical"
            elif temperature >= TEMP_CRITICAL_THRESHOLD:
                severity = "critical"
            elif temperature >= TEMP_WARNING_THRESHOLD:
                severity = "warning"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "SensorIndex": int(sensor_index) if pd.notna(sensor_index) else 0,
                "SensorName": sensor_name,
                "Temperature": temperature,
                "MaxTemperature": max_temperature,
                "LowThreshold": low_threshold,
                "HighThreshold": high_threshold,
                "Severity": severity,
                "UtilizationPct": round((temperature / high_threshold * 100), 1) if high_threshold > 0 else 0,
            }

            # 🆕 只添加异常传感器 (过滤掉normal)
            if severity != "normal":
                records.append(record)

            # Track anomalies with proper anomaly types
            if severity == "critical":
                anomaly_rows.append({
                    "NodeGUID": node_guid,
                    "PortNumber": sensor_index,
                    IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_TEMP_CRITICAL),
                    IBH_ANOMALY_AGG_WEIGHT: 1.0,
                })
            elif severity == "warning":
                anomaly_rows.append({
                    "NodeGUID": node_guid,
                    "PortNumber": sensor_index,
                    IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_TEMP_WARNING),
                    IBH_ANOMALY_AGG_WEIGHT: 0.5,
                })

        # Build anomaly DataFrame
        anomalies = pd.DataFrame(anomaly_rows) if anomaly_rows else None

        # Build summary
        summary = self._build_summary(records)

        return TemperatureResult(data=records, anomalies=anomalies, summary=summary)

    def _build_summary(self, records: List[Dict]) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        temps = [r["Temperature"] for r in records if r["Temperature"] > 0]
        critical_count = sum(1 for r in records if r["Severity"] == "critical")
        warning_count = sum(1 for r in records if r["Severity"] == "warning")

        return {
            "total_sensors": len(records),
            "sensors_with_data": len(temps),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "avg_temperature": round(sum(temps) / len(temps), 1) if temps else 0,
            "max_temperature": max(temps) if temps else 0,
            "min_temperature": min(temps) if temps else 0,
        }

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
    def _safe_float(value: object) -> float:
        """Safely convert to float."""
        try:
            if pd.isna(value):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0
