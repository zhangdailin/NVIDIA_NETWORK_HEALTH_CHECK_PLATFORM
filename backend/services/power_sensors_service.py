"""Power Sensors service for granular power monitoring.

Uses tables:
- POWER_SENSORS: Individual power sensor readings (6,688 rows typical)
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
class PowerSensorsResult:
    """Result from Power Sensors analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PowerSensorsService:
    """Analyze individual power sensor readings for detailed power monitoring."""

    # Power thresholds (in watts/milliwatts depending on sensor type)
    WARNING_UTILIZATION_PCT = 80
    CRITICAL_UTILIZATION_PCT = 95

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PowerSensorsResult:
        """Run Power Sensors analysis."""
        power_sensors_df = self._try_read_table("POWER_SENSORS")

        if power_sensors_df.empty:
            return PowerSensorsResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        sensor_type_distribution: Dict[str, int] = defaultdict(int)
        warning_count = 0
        critical_count = 0
        total_power_mw = 0
        max_power_mw = 0
        sensors_by_node: Dict[str, int] = defaultdict(int)

        for _, row in power_sensors_df.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("GUID", "")))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Sensor identification
            sensor_index = self._safe_int(row.get("SensorIndex", row.get("Index", 0)))
            sensor_name = str(row.get("SensorName", row.get("Name", f"Sensor_{sensor_index}")))
            sensor_type = str(row.get("SensorType", row.get("Type", "Unknown")))
            sensor_type_distribution[sensor_type] += 1
            sensors_by_node[node_guid] += 1

            # Power readings
            current_power = self._safe_float(row.get("CurrentPower", row.get("Power", 0)))
            max_power_cap = self._safe_float(row.get("MaxPower", row.get("PowerCap", 0)))
            min_power = self._safe_float(row.get("MinPower", 0))
            avg_power = self._safe_float(row.get("AvgPower", current_power))

            # Voltage and current (if available)
            voltage = self._safe_float(row.get("Voltage", 0))
            current = self._safe_float(row.get("Current", 0))

            # Track totals
            total_power_mw += current_power
            max_power_mw = max(max_power_mw, current_power)

            # Calculate utilization
            utilization_pct = (current_power / max_power_cap * 100) if max_power_cap > 0 else 0

            # Status from device
            status = str(row.get("Status", row.get("State", "OK")))

            # Detect issues
            issues = []
            severity = "normal"

            if utilization_pct >= self.CRITICAL_UTILIZATION_PCT:
                issues.append(f"Critical power utilization: {utilization_pct:.1f}%")
                severity = "critical"
                critical_count += 1
            elif utilization_pct >= self.WARNING_UTILIZATION_PCT:
                issues.append(f"High power utilization: {utilization_pct:.1f}%")
                severity = "warning"
                warning_count += 1

            if status.lower() not in ("ok", "normal", "good", ""):
                issues.append(f"Sensor status: {status}")
                if severity == "normal":
                    severity = "warning"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "SensorIndex": sensor_index,
                "SensorName": sensor_name,
                "SensorType": sensor_type,
                "CurrentPower": round(current_power, 2),
                "MaxPowerCap": round(max_power_cap, 2),
                "MinPower": round(min_power, 2),
                "AvgPower": round(avg_power, 2),
                "UtilizationPct": round(utilization_pct, 1),
                "Voltage": round(voltage, 3) if voltage else None,
                "Current": round(current, 3) if current else None,
                "Status": status,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = {
            "total_sensors": len(power_sensors_df),
            "unique_nodes": len(sensors_by_node),
            "warning_count": warning_count,
            "critical_count": critical_count,
            "total_power_mw": round(total_power_mw, 2),
            "total_power_w": round(total_power_mw / 1000, 2),
            "max_sensor_power_mw": round(max_power_mw, 2),
            "avg_sensors_per_node": round(len(power_sensors_df) / max(len(sensors_by_node), 1), 1),
            "sensor_type_distribution": dict(sorted(sensor_type_distribution.items(), key=lambda x: -x[1])),
        }

        # Sort by severity and utilization
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("UtilizationPct", 0)
        ))

        return PowerSensorsResult(data=records[:2000], anomalies=None, summary=summary)

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
