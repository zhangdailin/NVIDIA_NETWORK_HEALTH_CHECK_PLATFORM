"""Power supply analysis service using POWER_SUPPLIES and POWER_SENSORS tables."""

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
class PowerResult:
    """Result from power analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class PowerService:
    """Analyze power supplies and sensors from ibdiagnet data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> PowerResult:
        """Run power supply analysis."""
        index_table = self._get_index_table()
        records = []
        anomaly_rows = []

        # Process POWER_SUPPLIES table
        if "POWER_SUPPLIES" in index_table.index:
            try:
                psu_df = self._read_table("POWER_SUPPLIES")
                self._process_power_supplies(psu_df, records, anomaly_rows)
            except Exception as e:
                logger.warning(f"Failed to read POWER_SUPPLIES: {e}")

        # Build anomaly DataFrame
        anomalies = pd.DataFrame(anomaly_rows) if anomaly_rows else None

        # Build summary
        summary = self._build_summary(records)

        return PowerResult(data=records, anomalies=anomalies, summary=summary)

    def _process_power_supplies(
        self,
        df: pd.DataFrame,
        records: List[Dict],
        anomaly_rows: List[Dict],
    ) -> None:
        """Process POWER_SUPPLIES table."""
        if df.empty:
            return

        topology = self._get_topology()

        for _, row in df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            psu_index = row.get("PSUIndex", 0)
            is_present = str(row.get("IsPresent", "")).lower() == "yes"
            dc_state = str(row.get("DCState", ""))
            alert_state = str(row.get("AlertState", ""))
            fan_state = str(row.get("FanState", ""))
            temp_state = str(row.get("TemperatureState", ""))
            power_consumption = self._safe_float(row.get("PowerConsumption"))
            power_cap = self._safe_float(row.get("PowerCap"))
            serial = str(row.get("SerialNumber", ""))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Determine severity
            severity = "normal"
            issues = []

            if not is_present:
                severity = "warning"
                issues.append("PSU not present")
            else:
                if dc_state and dc_state.lower() not in ("ok", ""):
                    severity = "critical"
                    issues.append(f"DC state: {dc_state}")
                if alert_state and alert_state.lower() not in ("ok", "", "nan"):
                    severity = "critical"
                    issues.append(f"Alert: {alert_state}")
                if fan_state and fan_state.lower() not in ("ok", ""):
                    if severity != "critical":
                        severity = "warning"
                    issues.append(f"Fan: {fan_state}")
                if temp_state and temp_state.lower() not in ("ok", "", "nan"):
                    if severity != "critical":
                        severity = "warning"
                    issues.append(f"Temp: {temp_state}")

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PSUIndex": int(psu_index) if pd.notna(psu_index) else 0,
                "IsPresent": is_present,
                "DCState": dc_state,
                "AlertState": alert_state if pd.notna(row.get("AlertState")) else "",
                "FanState": fan_state,
                "TemperatureState": temp_state if pd.notna(row.get("TemperatureState")) else "",
                "PowerConsumption": power_consumption,
                "PowerCap": power_cap,
                "SerialNumber": serial if serial != "nan" else "",
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }

            # 🆕 只添加异常PSU (过滤掉normal)
            if severity != "normal":
                records.append(record)

            # Track anomalies with proper anomaly types
            if severity == "critical":
                anomaly_rows.append({
                    "NodeGUID": node_guid,
                    "PortNumber": psu_index,
                    IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_PSU_CRITICAL),
                    IBH_ANOMALY_AGG_WEIGHT: 1.0,
                })
            elif severity == "warning":
                anomaly_rows.append({
                    "NodeGUID": node_guid,
                    "PortNumber": psu_index,
                    IBH_ANOMALY_AGG_COL: str(AnomlyType.IBH_PSU_WARNING),
                    IBH_ANOMALY_AGG_WEIGHT: 0.5,
                })

    def _build_summary(self, records: List[Dict]) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {}

        present_count = sum(1 for r in records if r.get("IsPresent"))
        critical_count = sum(1 for r in records if r.get("Severity") == "critical")
        warning_count = sum(1 for r in records if r.get("Severity") == "warning")
        power_values = [r["PowerConsumption"] for r in records if r["PowerConsumption"] > 0]

        return {
            "total_psus": len(records),
            "present_count": present_count,
            "not_present_count": len(records) - present_count,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "total_power_consumption": sum(power_values) if power_values else 0,
            "avg_power_consumption": round(sum(power_values) / len(power_values), 1) if power_values else 0,
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
