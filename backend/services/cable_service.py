"""Cable/optic analysis service with performance optimizations."""
from __future__ import annotations

import logging
import math
import numbers
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import concurrent.futures
import numpy as np
from functools import lru_cache
import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .dataset_inventory import DatasetInventory
from .topology_lookup import TopologyLookup

# 导入配置管理器
try:
    from config.thresholds import threshold_config
except ImportError:
    threshold_config = None

logger = logging.getLogger(__name__)


CABLE_TABLE = "CABLE_INFO"

# 从配置加载温度阈值
def _get_temp_thresholds():
    if threshold_config:
        return {
            'warning': threshold_config.get('cable.temperature.warning', 70),
            'critical': threshold_config.get('cable.temperature.critical', 80)
        }
    return {'warning': 70, 'critical': 80}

TEMP_THRESHOLDS = _get_temp_thresholds()
TEMP_WARNING_THRESHOLD = TEMP_THRESHOLDS['warning']
TEMP_CRITICAL_THRESHOLD = TEMP_THRESHOLDS['critical']

LENGTH_BUCKETS = ["0-1m", "1-3m", "3-5m", "5-10m", "10-30m", "30-100m", ">100m", "Unknown"]
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
    summary: Dict[str, object] = field(default_factory=dict)


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
    "Severity",  # Add Severity field for frontend
]

# 从配置加载最大行数
def _get_max_cable_rows():
    if threshold_config:
        return threshold_config.get('cable.max_display_rows', 2000)
    return 2000

MAX_CABLE_ROWS = _get_max_cable_rows()


class CableService:
    """Loads cable telemetry and computes optical anomalies with performance optimizations."""

    def __init__(self, dataset_root: Path, dataset_inventory: DatasetInventory | None = None):
        self.dataset_root = dataset_root
        self._inventory = dataset_inventory or DatasetInventory(dataset_root)
        self._df: pd.DataFrame | None = None
        self._ports: pd.DataFrame | None = None

    def clear_cache(self):
        """Clear cached DataFrames to free memory."""
        self._df = None
        self._ports = None

    def run(self, return_only_issues: bool = True) -> CableAnalysis:
        df = self._load_dataframe()
        anomalies = self._build_anomalies(df)

        # Vectorized Severity calculation instead of apply(axis=1)
        df["Severity"] = self._vectorized_calculate_severity(df)
        summary = self._build_summary(df)

        # Log severity distribution
        severity_counts = df["Severity"].value_counts()
        logger.info(f"Cable severity distribution: {severity_counts.to_dict()}")

        # Filter to only issues (critical/warning) if requested
        if return_only_issues:
            df_filtered = df[df["Severity"].isin(["critical", "warning"])]
            logger.info("Cable: filtered %d rows to %d issues (critical/warning)", len(df), len(df_filtered))

            # Log alarm columns presence
            alarm_columns = [
                'TX Bias Alarm and Warning',
                'TX Power Alarm and Warning',
                'RX Power Alarm and Warning',
                'Latched Voltage Alarm and Warning'
            ]
            for col in alarm_columns:
                if col in df_filtered.columns:
                    non_zero = df_filtered[col].apply(self._alarm_weight).sum()
                    logger.info(f"Cable: {col} has {non_zero} non-zero alarms in filtered data")

            df = df_filtered

        # NOW filter columns to only display columns (after Severity is calculated)
        existing_columns = [col for col in DISPLAY_COLUMNS if col in df.columns]
        df = df[existing_columns].copy()

        records = df.to_dict(orient="records")
        total_records = len(records)
        if MAX_CABLE_ROWS and total_records > MAX_CABLE_ROWS:
            logger.info("Cable: trimming %d rows to preview first %d", total_records, MAX_CABLE_ROWS)
            records = records[:MAX_CABLE_ROWS]

        return CableAnalysis(data=records, anomalies=anomalies, summary=summary)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df

        # Read the table efficiently in one go
        df = self._inventory.read_table(CABLE_TABLE)
        logger.info(f"Cable: loaded {len(df)} rows from {CABLE_TABLE}")

        # Batch rename columns to avoid multiple operations
        df.rename(
            columns={
                "NodeGuid": "NodeGUID",
                "PortNum": "PortNumber",
                "PortGuid": "PortGUID",
                "FWVersion": "ConnectorFW",
            },
            inplace=True,
        )

        # Process temperature values with vectorized operation instead of apply
        df["Temperature (c)"] = self._vectorized_temperature_stoi(df.get("Temperature", pd.Series()))

        # Process NodeGUIDs efficiently
        df["NodeGUID"] = df["NodeGUID"].apply(self._remove_redundant_zero)

        # Log alarm columns presence before processing
        alarm_columns = [
            'TX Bias Alarm and Warning',
            'TX Power Alarm and Warning',
            'RX Power Alarm and Warning',
            'Latched Voltage Alarm and Warning'
        ]
        for col in alarm_columns:
            if col in df.columns:
                non_null = df[col].notna().sum()
                non_zero = df[col].apply(self._alarm_weight).sum()
                logger.info(f"Cable: column '{col}' has {non_null} non-null values, {int(non_zero)} non-zero alarms")
            else:
                logger.warning(f"Cable: column '{col}' not found in data")

        # Batch annotate with different functions
        df = self._annotate_length_compliance(df)
        df = self._annotate_port_capabilities(df)

        # Topology lookup
        df = self._topology_lookup().annotate_ports(df, guid_col="NodeGUID", port_col="PortNumber")

        # NOTE: Do NOT filter columns here - we need to keep all columns for Severity calculation
        # The filtering will happen in run() after Severity is calculated

        # Keep it cached
        self._df = df
        return df

    @staticmethod
    @lru_cache(maxsize=10000)
    def _cached_remove_redundant_zero(guid: str) -> str:
        """Cached version of _remove_redundant_zero to handle repeated values."""
        if guid.startswith("0x"):
            try:
                return hex(int(guid, 16))
            except (ValueError, OverflowError):
                logger.warning(f"Invalid hex GUID format: {guid}")
                return guid
        return guid

    @staticmethod
    def _remove_redundant_zero(guid: str) -> str:
        """Remove redundant zeros from GUID."""
        if isinstance(guid, str):
            return CableService._cached_remove_redundant_zero(guid)
        return guid

    @staticmethod
    def _vectorized_temperature_stoi(temperature_series):
        """Vectorized temperature parsing for performance."""
        def parse_single_temp(temp_val):
            if pd.isna(temp_val):
                return pd.NA
            temperature_str = str(temp_val).strip()
            if not temperature_str or temperature_str.upper() in {"NA", "N/A"}:
                return pd.NA

            # Extract content from quotes if needed
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

        # Apply the function efficiently to the series
        return temperature_series.apply(parse_single_temp)

    def _build_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        records = []
        temp_threshold = 70.0

        # Handle temperature column efficiently
        temp_df = df[IBH_ANOMALY_TBL_KEY + ["Temperature (c)"]].copy()
        temp_df["Temperature (c)"] = pd.to_numeric(temp_df["Temperature (c)"], errors="coerce")
        label = str(AnomlyType.IBH_OPTICAL_TEMP_HIGH)
        temp_df[label] = temp_df["Temperature (c)"].apply(
            lambda value: max(0.1, float(value) - temp_threshold) if pd.notna(value) and float(value) >= temp_threshold else 0.0
        )
        records.append(temp_df[IBH_ANOMALY_TBL_KEY + [label]])

        # Process alarm columns in batch
        alarm_columns = [
            ("TX Bias Alarm and Warning", AnomlyType.IBH_OPTICAL_TX_BIAS),
            ("TX Power Alarm and Warning", AnomlyType.IBH_OPTICAL_TX_POWER),
            ("RX Power Alarm and Warning", AnomlyType.IBH_OPTICAL_RX_POWER),
            ("Latched Voltage Alarm and Warning", AnomlyType.IBH_OPTICAL_VOLTAGE),
        ]

        for column, anomaly in alarm_columns:
            if column in df.columns:
                alarm_df = df[IBH_ANOMALY_TBL_KEY + [column]].copy()
                alarm_df[str(anomaly)] = alarm_df[column].apply(self._alarm_weight)
                records.append(alarm_df[IBH_ANOMALY_TBL_KEY + [str(anomaly)]])

        # Process status columns
        for column in ["CableComplianceStatus", "CableSpeedStatus"]:
            if column in df.columns:
                status_df = df[IBH_ANOMALY_TBL_KEY + [column]].copy()
                status_df[str(AnomlyType.IBH_CABLE_MISMATCH)] = status_df[column].apply(self._status_weight)
                records.append(status_df[IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_CABLE_MISMATCH)]])

        # Efficiently merge all records
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
                alarm_value = int(token, 16)
                has_alarm = 1.0 if alarm_value else 0.0
                if has_alarm > 0:
                    logger.debug(f"Alarm detected: {value} -> weight={has_alarm}")
                return has_alarm
            parsed = int(token)
            has_alarm = 1.0 if parsed else 0.0
            if has_alarm > 0:
                logger.debug(f"Alarm detected: {value} -> weight={has_alarm}")
            return has_alarm
        except ValueError:
            logger.warning(f"Failed to parse alarm value: {value}")
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
        return self._inventory.topology

    def _annotate_length_compliance(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Use vectorized operations where possible
        df["LengthSMFiber"] = pd.to_numeric(df.get("LengthSMFiber"), errors="coerce")
        df["LengthCopperOrActive"] = pd.to_numeric(df.get("LengthCopperOrActive"), errors="coerce")
        # Apply function efficiently
        df["CableComplianceStatus"] = df.apply(self._evaluate_cable_limit, axis=1)
        return df

    def _evaluate_cable_limit(self, row) -> str:
        """Evaluate cable length compliance.
        Note: Copper length exceeds are now considered informational, not warnings.
        """
        type_desc = str(row.get("TypeDesc", "")).lower()
        supported_speed = str(row.get("SupportedSpeedDesc", "")).lower()
        length_sm = row.get("LengthSMFiber")
        length_cu = row.get("LengthCopperOrActive")

        if "fiber" in type_desc:
            # 从配置加载光纤长度限制
            if threshold_config:
                limit_map = {
                    "hdr": threshold_config.get("cable.length_limits.fiber.hdr", 1000),
                    "fdr": threshold_config.get("cable.length_limits.fiber.fdr", 2000)
                }
            else:
                limit_map = {"hdr": 1000, "fdr": 2000}
            for keyword, limit in limit_map.items():
                if keyword in supported_speed and pd.notna(length_sm) and float(length_sm) > limit:
                    return f"SMF length exceeds {limit}m"
        elif "copper" in type_desc or "passive" in type_desc:
            # Copper length exceeds are now ignored (not treated as warnings)
            # Uncomment the lines below if you want to re-enable copper length warnings
            # limit_map = {"hdr": 5, "fdr": 3}
            # for keyword, limit in limit_map.items():
            #     if keyword in supported_speed and pd.notna(length_cu) and float(length_cu) > limit:
            #         return f"Copper length exceeds {limit}m"
            pass
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

        # Vectorize the speed decoding
        result_actv = subset["LinkSpeedActv"].apply(self._decode_speed)
        subset["LocalActiveLinkSpeedValue"], subset["LocalActiveLinkSpeed"] = zip(
            *result_actv
        )

        result_supp = subset["LinkSpeedSup"].apply(self._decode_speed)
        subset["LocalSupportedLinkSpeedValue"], subset["LocalSupportedLinkSpeed"] = zip(
            *result_supp
        )

        # Ensure PortNumber columns have the same dtype before merging
        df["PortNumber"] = df["PortNumber"].astype(str)
        subset["PortNumber"] = subset["PortNumber"].astype(str)

        # Perform merge operation efficiently
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
        if not self._inventory.table_exists("PORTS"):
            self._ports = pd.DataFrame()
            return self._ports
        ports = self._inventory.read_table("PORTS")
        ports.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber"}, inplace=True)
        # Use vectorized function to process NodeGUIDs
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

    def _vectorized_calculate_severity(self, df: pd.DataFrame) -> pd.Series:
        """Vectorized severity calculation for better performance."""
        import numpy as np

        # 使用配置的温度阈值
        TEMP_WARNING_THRESHOLD = TEMP_THRESHOLDS['warning']
        TEMP_CRITICAL_THRESHOLD = TEMP_THRESHOLDS['critical']

        # Start with all normal
        severity = pd.Series("normal", index=df.index)

        # Track what caused severity changes for debugging
        critical_reasons = []
        warning_reasons = []

        # DEBUG: Log sample data
        logger.info(f"Cable: Starting severity calculation for {len(df)} rows")
        if len(df) > 0:
            sample_row = df.iloc[0]
            logger.info(f"Cable: Sample row columns: {list(sample_row.index)[:20]}")

        # Check temperature - vectorized
        if "Temperature (c)" in df.columns:
            temp = pd.to_numeric(df["Temperature (c)"], errors="coerce")
            temp_critical_mask = temp >= TEMP_CRITICAL_THRESHOLD
            temp_warning_mask = (temp >= TEMP_WARNING_THRESHOLD) & (temp < TEMP_CRITICAL_THRESHOLD)

            critical_count = temp_critical_mask.sum()
            warning_count = temp_warning_mask.sum()

            # DEBUG: Log temperature stats
            temp_valid = temp.notna().sum()
            temp_min = temp.min() if temp_valid > 0 else None
            temp_max = temp.max() if temp_valid > 0 else None
            logger.info(f"Cable: Temperature - valid: {temp_valid}, min: {temp_min}, max: {temp_max}, critical: {critical_count}, warning: {warning_count}")

            if critical_count > 0:
                critical_reasons.append(f"Temperature critical: {critical_count} ports")
            if warning_count > 0:
                warning_reasons.append(f"Temperature warning: {warning_count} ports")

            severity = np.where(temp_critical_mask, "critical", severity)
            severity = np.where(
                temp_warning_mask & (severity != "critical"),
                "warning",
                severity
            )

        # Check alarms - vectorized
        alarm_columns = [
            'TX Bias Alarm and Warning',
            'TX Power Alarm and Warning',
            'RX Power Alarm and Warning',
            'Latched Voltage Alarm and Warning'
        ]

        for col in alarm_columns:
            if col in df.columns:
                # DEBUG: Log sample alarm values
                sample_values = df[col].head(10).tolist()
                logger.info(f"Cable: {col} sample values: {sample_values}")

                alarm_weights = df[col].apply(self._alarm_weight)
                alarm_count = (alarm_weights > 0).sum()

                # DEBUG: Log alarm weight stats
                logger.info(f"Cable: {col} - total weights: {alarm_weights.sum()}, non-zero count: {alarm_count}")

                if alarm_count > 0:
                    critical_reasons.append(f"{col}: {alarm_count} alarms")
                    logger.info(f"Cable: {col} triggered {alarm_count} critical alarms")
                    # DEBUG: Show which rows have alarms
                    alarm_rows = df[alarm_weights > 0].index.tolist()[:5]
                    logger.info(f"Cable: {col} alarm row indices (first 5): {alarm_rows}")
                severity = np.where(alarm_weights > 0, "critical", severity)
            else:
                logger.warning(f"Cable: {col} not found in dataframe columns")

        # Check compliance status - vectorized
        if "CableComplianceStatus" in df.columns:
            compliance = df["CableComplianceStatus"].fillna("").astype(str).str.upper()
            compliance_issue = (compliance != "OK") & (compliance != "")
            compliance_count = compliance_issue.sum()

            # DEBUG: Log compliance stats
            sample_compliance = df["CableComplianceStatus"].head(10).tolist()
            logger.info(f"Cable: CableComplianceStatus sample: {sample_compliance}, issues: {compliance_count}")

            if compliance_count > 0:
                warning_reasons.append(f"Compliance issues: {compliance_count} ports")
            severity = np.where(compliance_issue & (severity == "normal"), "warning", severity)

        if "CableSpeedStatus" in df.columns:
            speed = df["CableSpeedStatus"].fillna("").astype(str).str.upper()
            speed_issue = (speed != "OK") & (speed != "")
            speed_count = speed_issue.sum()

            # DEBUG: Log speed stats
            sample_speed = df["CableSpeedStatus"].head(10).tolist()
            logger.info(f"Cable: CableSpeedStatus sample: {sample_speed}, issues: {speed_count}")

            if speed_count > 0:
                warning_reasons.append(f"Speed issues: {speed_count} ports")
            severity = np.where(speed_issue & (severity == "normal"), "warning", severity)

        # Log summary of severity reasons
        if critical_reasons:
            logger.info(f"Cable critical reasons: {', '.join(critical_reasons)}")
        if warning_reasons:
            logger.info(f"Cable warning reasons: {', '.join(warning_reasons)}")

        # DEBUG: Log final severity distribution
        final_counts = pd.Series(severity).value_counts()
        logger.info(f"Cable: Final severity counts before return: {final_counts.to_dict()}")

        return pd.Series(severity, index=df.index)

    def _calculate_severity(self, row) -> str:
        """Calculate severity based on temperature and alarms.
        Returns: 'critical', 'warning', or 'normal'
        """
        # 使用配置的温度阈值
        TEMP_WARNING_THRESHOLD = TEMP_THRESHOLDS['warning']
        TEMP_CRITICAL_THRESHOLD = TEMP_THRESHOLDS['critical']

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

    def _build_summary(self, df: pd.DataFrame) -> Dict[str, object]:
        summary = {
            "total_cables": int(len(df)),
            "critical_count": 0,
            "warning_count": 0,
            "healthy_count": 0,
            "optical_count": 0,
            "aoc_count": 0,
            "copper_count": 0,
            "dom_capable_count": 0,
            "temp_warning_count": 0,
            "temp_critical_count": 0,
            "power_warning_count": 0,
            "power_critical_count": 0,
            "compliance_issues": 0,
            "vendor_distribution": {},
            "cable_type_distribution": {},
            "speed_distribution": {},
            "length_distribution": {},
            "cable_info_rows": int(len(df)),
            "optics_info_rows": 0,
            "mlnx_trans_rows": 0,
        }
        if df.empty:
            return summary

        # Use vectorized operations where possible for better performance
        severity_counts = df["Severity"].value_counts(dropna=False)
        summary["critical_count"] = int(severity_counts.get("critical", 0))
        summary["warning_count"] = int(severity_counts.get("warning", 0))
        summary["healthy_count"] = max(
            0, int(summary["total_cables"] - summary["critical_count"] - summary["warning_count"])
        )

        temp_series = pd.to_numeric(df.get("Temperature (c)"), errors="coerce")
        # 使用配置的温度阈值
        temp_warning = TEMP_THRESHOLDS['warning']
        temp_critical = TEMP_THRESHOLDS['critical']
        summary["temp_critical_count"] = int((temp_series >= temp_critical).sum())
        summary["temp_warning_count"] = int(
            ((temp_series >= temp_warning) & (temp_series < temp_critical)).sum()
        )

        # Create mask for alarm conditions efficiently
        alarm_mask = pd.Series(False, index=df.index)
        alarm_columns = [
            "TX Bias Alarm and Warning",
            "TX Power Alarm and Warning",
            "RX Power Alarm and Warning",
            "Latched Voltage Alarm and Warning",
        ]
        for column in alarm_columns:
            if column in df.columns:
                alarm_mask = alarm_mask | (df[column].apply(self._alarm_weight) > 0)
        summary["power_critical_count"] = int(alarm_mask.sum())
        summary["power_warning_count"] = summary["power_critical_count"]

        # Compliance check
        compliance_mask = pd.Series(False, index=df.index)
        for column in ["CableComplianceStatus", "CableSpeedStatus"]:
            if column in df.columns:
                statuses = df[column].fillna("").astype(str).str.strip().str.lower()
                compliance_mask = compliance_mask | ~statuses.isin({"", "ok"})
        summary["compliance_issues"] = int(compliance_mask.sum())

        # Vectorize cable type categorization
        if "TypeDesc" in df.columns:
            type_series = df["TypeDesc"]
        elif "CableType" in df.columns:
            type_series = df["CableType"]
        else:
            type_series = pd.Series()

        if not type_series.empty:
            # Use numpy to make this more efficient
            cable_types = type_series.fillna("Unknown").astype(str).values
            for value in cable_types:
                category = self._categorize_cable_type(value)
                if category == "optical":
                    summary["optical_count"] += 1
                elif category == "aoc":
                    summary["aoc_count"] += 1
                elif category == "copper":
                    summary["copper_count"] += 1
            summary["cable_type_distribution"] = (
                type_series.fillna("Unknown").astype(str).value_counts().head(10).to_dict()
            )

        if "Vendor" in df.columns:
            summary["vendor_distribution"] = (
                df["Vendor"]
                .fillna("Unknown")
                .astype(str)
                .str.strip()
                .replace("", "Unknown")
                .value_counts()
                .head(10)
                .to_dict()
            )

        if "SupportedSpeedDesc" in df.columns:
            summary["speed_distribution"] = (
                df["SupportedSpeedDesc"]
                    .fillna("Unknown")
                    .astype(str)
                    .str.strip()
                    .replace("", "Unknown")
                    .value_counts()
                    .head(10)
                    .to_dict()
            )

        if "DOMCapable" in df.columns:
            summary["dom_capable_count"] = int(df["DOMCapable"].apply(self._truthy_flag).sum())

        # Vectorized length distribution calculation using pd.cut
        length_col = None
        for key in ("LengthCopperOrActive", "LengthSMFiber", "Length"):
            if key in df.columns:
                candidate = pd.to_numeric(df[key], errors="coerce")
                if length_col is None:
                    length_col = candidate
                else:
                    length_col = length_col.fillna(candidate)

        if length_col is not None:
            length_buckets_series = pd.cut(
                length_col,
                bins=[0, 1, 3, 5, 10, 30, 100, float('inf')],
                labels=["0-1m", "1-3m", "3-5m", "5-10m", "10-30m", "30-100m", ">100m"],
                right=True
            )
            # Convert to string to handle NaN values properly
            length_buckets_series = length_buckets_series.astype(str).replace('nan', 'Unknown')
            length_counts = length_buckets_series.value_counts().to_dict()
            summary["length_distribution"] = {
                bucket: length_counts.get(bucket, 0)
                for bucket in LENGTH_BUCKETS
                if length_counts.get(bucket, 0) > 0
            }
        else:
            summary["length_distribution"] = {}

        return summary

    @staticmethod
    def _categorize_cable_type(value: str) -> str:
        tokens = str(value).strip().lower()
        if not tokens:
            return ""
        if any(token in tokens for token in ["aoc", "active"]):
            return "aoc"
        if any(token in tokens for token in ["copper", "dac", "passive"]):
            return "copper"
        if any(token in tokens for token in ["optical", "fiber", "smf", "om", "mmf"]):
            return "optical"
        return ""

    def _categorize_length_bucket(self, row) -> str:
        value = None
        for key in ("LengthCopperOrActive", "LengthSMFiber", "Length"):
            if key in row:
                candidate = row.get(key)
                if pd.notna(candidate):
                    try:
                        numeric = float(candidate)
                    except (TypeError, ValueError):
                        continue
                    if numeric > 0:
                        value = numeric
                        break
        if value is None:
            return "Unknown"
        if value <= 1:
            return "0-1m"
        if value <= 3:
            return "1-3m"
        if value <= 5:
            return "3-5m"
        if value <= 10:
            return "5-10m"
        if value <= 30:
            return "10-30m"
        if value <= 100:
            return "30-100m"
        return ">100m"

    @staticmethod
    def _truthy_flag(value: object) -> bool:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, numbers.Number):
            return int(value) != 0
        return str(value).strip().lower() in {"1", "true", "yes", "y"}