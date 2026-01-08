"""Temperature Alerts service for threshold monitoring.

Uses tables:
- TEMPERATURE_SENSORS_ALERT: Temperature threshold alerts (608 rows typical)
- TEMP_SENSING: Temperature sensing capabilities (6,150 rows typical)
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
class TempAlertsResult:
    """Result from Temperature Alerts analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class TempAlertsService:
    """Analyze temperature alerts and threshold configuration."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> TempAlertsResult:
        """Run Temperature Alerts analysis."""
        temp_alerts_df = self._try_read_table("TEMPERATURE_SENSORS_ALERT")
        temp_sensing_df = self._try_read_table("TEMP_SENSING")

        if temp_alerts_df.empty and temp_sensing_df.empty:
            return TempAlertsResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        alert_status_distribution: Dict[str, int] = defaultdict(int)
        warning_count = 0
        critical_count = 0
        over_threshold_count = 0
        max_temp = 0.0
        total_sensors = 0

        # Build temp sensing lookup
        sensing_lookup = {}
        if not temp_sensing_df.empty:
            for _, row in temp_sensing_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port = self._safe_int(row.get("PortNum", 0))
                key = f"{guid}:{port}"
                sensing_lookup[key] = {
                    "current_temp": self._safe_float(row.get("CurrentTemp", row.get("Temperature", 0))),
                    "max_temp": self._safe_float(row.get("MaxTemp", 0)),
                    "min_temp": self._safe_float(row.get("MinTemp", 0)),
                    "sensor_type": str(row.get("SensorType", row.get("Type", ""))),
                }

        # Process alerts (primary source)
        df_to_process = temp_alerts_df if not temp_alerts_df.empty else temp_sensing_df

        for _, row in df_to_process.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
            port_num = self._safe_int(row.get("PortNum", 0))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Alert status
            alert_status = str(row.get("AlertStatus", row.get("Status", "OK")))
            alert_status_distribution[alert_status] += 1

            # Thresholds
            warning_threshold = self._safe_float(row.get("WarningThreshold", row.get("WarnThresh", 0)))
            critical_threshold = self._safe_float(row.get("CriticalThreshold", row.get("CritThresh", 0)))
            shutdown_threshold = self._safe_float(row.get("ShutdownThreshold", row.get("ShutThresh", 0)))

            # Current temperature (from alert or sensing)
            key = f"{node_guid}:{port_num}"
            sensing_info = sensing_lookup.get(key, {})
            current_temp = self._safe_float(row.get("CurrentTemp", sensing_info.get("current_temp", 0)))
            max_temp = max(max_temp, current_temp)
            total_sensors += 1

            # Hysteresis
            hysteresis = self._safe_float(row.get("Hysteresis", 0))

            # Alert flags
            warning_active = self._safe_bool(row.get("WarningActive", False))
            critical_active = self._safe_bool(row.get("CriticalActive", False))

            # Determine severity
            issues = []
            severity = "normal"

            if critical_active or (critical_threshold > 0 and current_temp >= critical_threshold):
                issues.append(f"Critical temperature: {current_temp}°C >= {critical_threshold}°C")
                severity = "critical"
                critical_count += 1
                over_threshold_count += 1
            elif warning_active or (warning_threshold > 0 and current_temp >= warning_threshold):
                issues.append(f"Warning temperature: {current_temp}°C >= {warning_threshold}°C")
                severity = "warning"
                warning_count += 1
                over_threshold_count += 1

            # Check if approaching threshold
            if severity == "normal" and warning_threshold > 0:
                margin = (warning_threshold - current_temp) / warning_threshold * 100
                if margin < 10:
                    issues.append(f"Approaching warning threshold: {margin:.1f}% margin")
                    severity = "info"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "CurrentTemp": round(current_temp, 1),
                "WarningThreshold": round(warning_threshold, 1),
                "CriticalThreshold": round(critical_threshold, 1),
                "ShutdownThreshold": round(shutdown_threshold, 1),
                "Hysteresis": round(hysteresis, 1),
                "AlertStatus": alert_status,
                "WarningActive": warning_active,
                "CriticalActive": critical_active,
                "SensorType": sensing_info.get("sensor_type", ""),
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = {
            "total_sensors": total_sensors,
            "warning_count": warning_count,
            "critical_count": critical_count,
            "over_threshold_count": over_threshold_count,
            "max_temperature": round(max_temp, 1),
            "alert_status_distribution": dict(sorted(alert_status_distribution.items(), key=lambda x: -x[1])),
            "temp_sensing_entries": len(temp_sensing_df),
            "healthy_sensors": total_sensors - over_threshold_count,
        }

        # Sort by severity and temperature
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("CurrentTemp", 0)
        ))

        return TempAlertsResult(data=records[:2000], anomalies=None, summary=summary)

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
            return str(value).strip().lower() in ("1", "true", "yes", "active")
        except (TypeError, ValueError):
            return False
