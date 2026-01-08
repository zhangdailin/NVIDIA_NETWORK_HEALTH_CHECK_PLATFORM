"""Cable/optic analysis service."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


CABLE_TABLE = "CABLE_INFO"
SPEED_PRIORITY = [
    (0x800, ("HDR/NDR", 7)),
    (0x400, ("EDR/HDR100", 6)),
    (0x200, ("FDR10", 5)),
    (0x100, ("FDR", 4)),
    (0x80, ("QDR", 3)),
    (0x40, ("DDR", 2)),
    (0x20, ("SDR+", 1)),
    (0x10, ("SDR", 1)),
    (0x8, ("Legacy", 0)),
    (0x4, ("Legacy", 0)),
    (0x2, ("Legacy", 0)),
    (0x1, ("Legacy", 0)),
]


@dataclass
class CableRecord:
    row: Dict[str, object]


@dataclass
class CableAnalysis:
    data: List[Dict[str, object]]
    anomalies: pd.DataFrame


DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",
    "Attached To",
    "Node Type",
    "Attached To Type",
    "PortNumber",
    "Vendor",
    "PN",
    "SN",
    "Temperature (c)",
    "SupplyVoltageReporting",
    "TX Bias Alarm and Warning",
    "TX Power Alarm and Warning",
    "RX Power Alarm and Warning",
    "Latched Voltage Alarm and Warning",
    "HighTemperatureAlarm",
    "HighTemperatureWarning",
    "LowTemperatureAlarm",
    "LowTemperatureWarning",
    "HighSupplyVoltageAlarm",
    "HighSupplyVoltageWarning",
    "LowSupplyVoltageAlarm",
    "LowSupplyVoltageWarning",
    "LengthSMFiber",
    "LengthCopperOrActive",
    "TypeDesc",
    "SupportedSpeedDesc",
    "CableComplianceStatus",
    "CableSpeedStatus",
    "LocalActiveLinkSpeed",
]


class CableService:
    """Loads cable telemetry and computes optical anomalies."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._df: pd.DataFrame | None = None
        self._topology: TopologyLookup | None = None
        self._ports: pd.DataFrame | None = None

    def clear_cache(self):
        """Clear cached DataFrames to free memory."""
        self._df = None
        self._topology = None
        self._ports = None

    def run(self) -> CableAnalysis:
        df = self._load_dataframe()
        anomalies = self._build_anomalies(df)

        # 🆕 只返回异常数据 (过滤掉normal)
        # 添加Severity列基于温度和告警
        df['Severity'] = df.apply(self._calculate_severity, axis=1)

        # 过滤只保留异常
        anomaly_df = df[df['Severity'] != 'normal']

        logger.info(f"Cable: Filtered {len(df)} → {len(anomaly_df)} anomalies (removed {len(df)-len(anomaly_df)} normal cables)")

        return CableAnalysis(data=anomaly_df.to_dict(orient="records"), anomalies=anomalies)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        df = read_table(db_csv, CABLE_TABLE, index_table)
        df = df.replace('"', "", regex=True)
        df.rename(
            columns={
                "NodeGuid": "NodeGUID",
                "PortNum": "PortNumber",
                "PortGuid": "PortGUID",
                "FWVersion": "ConnectorFW",
            },
            inplace=True,
        )
        df["Temperature (c)"] = df.apply(self._temperature_stoi, axis=1)
        df["NodeGUID"] = df.apply(self._remove_redundant_zero, axis=1)
        df = self._annotate_length_compliance(df)
        df = self._annotate_port_capabilities(df)
        df = self._topology_lookup().annotate_ports(df, guid_col="NodeGUID", port_col="PortNumber")
        existing_columns = [col for col in DISPLAY_COLUMNS if col in df.columns]
        df = df[existing_columns].copy()
        self._df = df
        return df

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    @staticmethod
    def _remove_redundant_zero(row) -> str:
        """Remove redundant zeros from GUID. Can handle both dict/row and string."""
        # Handle when called with a string value directly (from Series.apply)
        if isinstance(row, str):
            guid = row
        # Handle when called with a dict/row object
        elif isinstance(row, dict) or hasattr(row, "get"):
            guid = str(row.get("NodeGUID", ""))
        else:
            guid = str(row)

        if guid.startswith("0x"):
            try:
                return hex(int(guid, 16))
            except (ValueError, OverflowError):
                logger.warning(f"Invalid hex GUID format: {guid}")
                return guid
        return guid

    @staticmethod
    def _temperature_stoi(row):
        temperature_str = row.get("Temperature")
        if temperature_str is None:
            return pd.NA
        temperature_str = str(temperature_str).strip()
        if not temperature_str:
            return pd.NA
        match = re.search(r'"([^"]*)"', temperature_str)
        if match:
            temperature_str = match.group(1).strip()
        if not temperature_str:
            return pd.NA
        if temperature_str.upper() in {"NA", "N/A"}:
            return pd.NA
        if temperature_str.endswith("C"):
            temperature_str = temperature_str[:-1].strip()
        if not temperature_str:
            return pd.NA
        try:
            return int(float(temperature_str))
        except ValueError:
            logger.warning(f"Failed to parse temperature value: {temperature_str}")
            return pd.NA

    def _build_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        records = []
        temp_threshold = 70.0
        temp_df = df[IBH_ANOMALY_TBL_KEY + ["Temperature (c)"]].copy()
        temp_df["Temperature (c)"] = pd.to_numeric(temp_df["Temperature (c)"], errors="coerce")
        label = str(AnomlyType.IBH_OPTICAL_TEMP_HIGH)
        temp_df[label] = temp_df["Temperature (c)"].apply(
            lambda value: max(0.1, float(value) - temp_threshold) if pd.notna(value) and float(value) >= temp_threshold else 0.0
        )
        records.append(temp_df[IBH_ANOMALY_TBL_KEY + [label]])

        for column, anomaly in [
            ("TX Bias Alarm and Warning", AnomlyType.IBH_OPTICAL_TX_BIAS),
            ("TX Power Alarm and Warning", AnomlyType.IBH_OPTICAL_TX_POWER),
            ("RX Power Alarm and Warning", AnomlyType.IBH_OPTICAL_RX_POWER),
            ("Latched Voltage Alarm and Warning", AnomlyType.IBH_OPTICAL_VOLTAGE),
        ]:
            if column in df.columns:
                alarm_df = df[IBH_ANOMALY_TBL_KEY + [column]].copy()
                alarm_df[str(anomaly)] = alarm_df[column].apply(self._alarm_weight)
                records.append(alarm_df[IBH_ANOMALY_TBL_KEY + [str(anomaly)]])

        for column in ["CableComplianceStatus", "CableSpeedStatus"]:
            if column in df.columns:
                status_df = df[IBH_ANOMALY_TBL_KEY + [column]].copy()
                status_df[str(AnomlyType.IBH_CABLE_MISMATCH)] = status_df[column].apply(self._status_weight)
                records.append(status_df[IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_CABLE_MISMATCH)]])

        if records:
            out = records[0]
            for extra in records[1:]:
                out = pd.merge(out, extra, on=IBH_ANOMALY_TBL_KEY, how="outer")
            return out.fillna(0)
        return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)

    @staticmethod
    def _alarm_weight(value) -> float:
        if value is None:
            return 0.0
        text = str(value).strip()
        if not text:
            return 0.0
        token = text.split()[0]
        try:
            if token.lower().startswith("0x"):
                return 1.0 if int(token, 16) else 0.0
            parsed = int(token)
            return 1.0 if parsed else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def _status_weight(value) -> float:
        if value is None:
            return 0.0
        text = str(value).strip()
        if not text or text.upper() == "OK":
            return 0.0
        return 1.0

    def _topology_lookup(self) -> TopologyLookup:
        if self._topology is None:
            self._topology = TopologyLookup(self.dataset_root)
        return self._topology

    def _annotate_length_compliance(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["LengthSMFiber"] = pd.to_numeric(df.get("LengthSMFiber"), errors="coerce")
        df["LengthCopperOrActive"] = pd.to_numeric(df.get("LengthCopperOrActive"), errors="coerce")
        df["CableComplianceStatus"] = df.apply(self._evaluate_cable_limit, axis=1)
        return df

    def _evaluate_cable_limit(self, row) -> str:
        type_desc = str(row.get("TypeDesc", "")).lower()
        supported_speed = str(row.get("SupportedSpeedDesc", "")).lower()
        length_sm = row.get("LengthSMFiber")
        length_cu = row.get("LengthCopperOrActive")
        if "fiber" in type_desc:
            limit_map = {"hdr": 1000, "fdr": 2000}
            for keyword, limit in limit_map.items():
                if keyword in supported_speed and pd.notna(length_sm) and float(length_sm) > limit:
                    return f"SMF length exceeds {limit}m"
        elif "copper" in type_desc or "passive" in type_desc:
            limit_map = {"hdr": 5, "fdr": 3}
            for keyword, limit in limit_map.items():
                if keyword in supported_speed and pd.notna(length_cu) and float(length_cu) > limit:
                    return f"Copper length exceeds {limit}m"
        return "OK"

    def _annotate_port_capabilities(self, df: pd.DataFrame) -> pd.DataFrame:
        ports = self._ports_table()
        if ports.empty:
            df["LocalActiveLinkSpeed"] = pd.NA
            df["LocalActiveLinkSpeedValue"] = pd.NA
            df["LocalSupportedLinkSpeed"] = pd.NA
            return df
        subset = ports[
            [
                "NodeGUID",
                "PortNumber",
                "LinkSpeedActv",
                "LinkSpeedSup",
            ]
        ].copy()
        subset["LinkSpeedActv"] = pd.to_numeric(subset["LinkSpeedActv"], errors="coerce")
        subset["LinkSpeedSup"] = pd.to_numeric(subset["LinkSpeedSup"], errors="coerce")
        subset["LocalActiveLinkSpeedValue"], subset["LocalActiveLinkSpeed"] = zip(
            *subset["LinkSpeedActv"].map(self._decode_speed)
        )
        subset["LocalSupportedLinkSpeedValue"], subset["LocalSupportedLinkSpeed"] = zip(
            *subset["LinkSpeedSup"].map(self._decode_speed)
        )
        # Ensure PortNumber columns have the same dtype before merging
        df["PortNumber"] = df["PortNumber"].astype(str)
        subset["PortNumber"] = subset["PortNumber"].astype(str)
        merged = df.merge(
            subset,
            on=["NodeGUID", "PortNumber"],
            how="left",
        )
        merged = self._evaluate_media_compatibility(merged)
        return merged

    def _evaluate_media_compatibility(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["CableSpeedStatus"] = df.apply(self._speed_mismatch_status, axis=1)
        return df

    def _speed_mismatch_status(self, row) -> str:
        cable_desc = str(row.get("SupportedSpeedDesc", "")).lower()
        cable_priority = self._speed_desc_priority(cable_desc)
        port_priority = row.get("LocalActiveLinkSpeedValue")
        if pd.notna(port_priority) and port_priority > cable_priority and cable_priority > 0:
            return f"Cable rated for {row.get('SupportedSpeedDesc')} but port at {row.get('LocalActiveLinkSpeed')}"
        type_desc = str(row.get("TypeDesc", "")).lower()
        length_sm = row.get("LengthSMFiber")
        if "sm" in type_desc and (pd.isna(length_sm) or float(length_sm) <= 0) and cable_priority >= 7:
            return "SMF length missing for HDR+ optic"
        return "OK"

    def _speed_desc_priority(self, desc: str) -> int:
        tokens = desc.lower()
        if any(token in tokens for token in ["ndr", "400g"]):
            return 8
        if "hdr" in tokens or "200g" in tokens:
            return 7
        if "edr" in tokens or "100g" in tokens:
            return 6
        if "fdr10" in tokens:
            return 5
        if "fdr" in tokens:
            return 4
        if "qdr" in tokens or "40g" in tokens:
            return 3
        if "ddr" in tokens or "20g" in tokens:
            return 2
        if "sdr" in tokens or "10g" in tokens:
            return 1
        return 0

    def _ports_table(self) -> pd.DataFrame:
        if hasattr(self, "_ports") and self._ports is not None:
            return self._ports
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        if "PORTS" not in index_table.index:
            self._ports = pd.DataFrame()
            return self._ports
        ports = read_table(db_csv, "PORTS", index_table)
        ports.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber"}, inplace=True)
        ports["NodeGUID"] = ports["NodeGUID"].apply(self._remove_redundant_zero)
        self._ports = ports
        return self._ports

    @staticmethod
    def _decode_speed(value):
        try:
            code = int(value)
        except (TypeError, ValueError):
            return (0, None)
        for bit, (label, priority) in SPEED_PRIORITY:
            if code & bit:
                return (priority, label)
        return (0, None)

    def _calculate_severity(self, row) -> str:
        """Calculate severity based on temperature and alarms.

        Returns: 'critical', 'warning', or 'normal'
        """
        TEMP_WARNING_THRESHOLD = 70
        TEMP_CRITICAL_THRESHOLD = 80

        severity = "normal"

        # Check temperature
        temp = row.get('Temperature (c)')
        if pd.notna(temp):
            try:
                temp_value = float(temp)
                if temp_value >= TEMP_CRITICAL_THRESHOLD:
                    severity = "critical"
                elif temp_value >= TEMP_WARNING_THRESHOLD:
                    severity = "warning"
            except (ValueError, TypeError):
                pass

        # Check alarms
        alarm_columns = [
            'TX Bias Alarm and Warning',
            'TX Power Alarm and Warning',
            'RX Power Alarm and Warning',
            'Latched Voltage Alarm and Warning'
        ]

        for col in alarm_columns:
            if col in row.index and self._alarm_weight(row.get(col)) > 0:
                severity = "critical"
                break

        # Check compliance status
        compliance_status = row.get('CableComplianceStatus', 'OK')
        speed_status = row.get('CableSpeedStatus', 'OK')

        if (str(compliance_status).upper() != 'OK' and str(compliance_status) != '') or \
           (str(speed_status).upper() != 'OK' and str(speed_status) != ''):
            if severity == "normal":
                severity = "warning"

        return severity
