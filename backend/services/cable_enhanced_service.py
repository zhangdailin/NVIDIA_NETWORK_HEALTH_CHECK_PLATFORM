"""Cable Enhanced service for detailed cable/optic analysis.

Uses tables:
- CABLE_INFO: Detailed cable information (~12K rows)
- CABLE_INFO_EXT: Extended cable info with vendor details
- CABLE_INFO_DATA: Raw cable diagnostic data
- OPTICS_INFO: Optical module details
- MLNX_TRANS_INFO: Mellanox transceiver information

This service provides enhanced cable analysis including:
- Cable type and length validation
- Optical power monitoring (TX/RX)
- DOM (Digital Optical Monitoring) data
- Vendor and compliance verification
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

# Temperature thresholds for optics (Celsius)
TEMP_WARNING_THRESHOLD = 70
TEMP_CRITICAL_THRESHOLD = 80

# Optical power thresholds (dBm)
TX_POWER_LOW_WARNING = -8.0
TX_POWER_LOW_CRITICAL = -10.0
RX_POWER_LOW_WARNING = -14.0
RX_POWER_LOW_CRITICAL = -16.0


@dataclass
class CableEnhancedResult:
    """Result from Cable Enhanced analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class CableEnhancedService:
    """Analyze enhanced cable and optics data."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> CableEnhancedResult:
        """Run Cable Enhanced analysis."""
        cable_info_df = self._try_read_table("CABLE_INFO")
        cable_info_ext_df = self._try_read_table("CABLE_INFO_EXT")
        optics_info_df = self._try_read_table("OPTICS_INFO")
        mlnx_trans_df = self._try_read_table("MLNX_TRANS_INFO")
        cable_data_df = self._try_read_table("CABLE_INFO_DATA")

        if cable_info_df.empty and optics_info_df.empty and mlnx_trans_df.empty:
            return CableEnhancedResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        total_cables = 0
        optical_count = 0
        copper_count = 0
        aoc_count = 0
        temp_warning_count = 0
        temp_critical_count = 0
        power_warning_count = 0
        power_critical_count = 0
        compliance_issues = 0
        dom_capable_count = 0

        # Vendor distribution
        vendor_distribution: Dict[str, int] = defaultdict(int)
        cable_type_distribution: Dict[str, int] = defaultdict(int)
        speed_distribution: Dict[str, int] = defaultdict(int)
        length_distribution: Dict[str, int] = defaultdict(int)

        # Build extended info lookup
        ext_lookup = {}
        if not cable_info_ext_df.empty:
            for _, row in cable_info_ext_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                key = f"{guid}:{port}"
                ext_lookup[key] = {
                    "vendor_pn": str(row.get("VendorPN", row.get("PartNumber", ""))),
                    "vendor_sn": str(row.get("VendorSN", row.get("SerialNumber", ""))),
                    "vendor_rev": str(row.get("VendorRev", row.get("Revision", ""))),
                    "date_code": str(row.get("DateCode", row.get("ManufDate", ""))),
                    "wavelength": self._safe_float(row.get("Wavelength", 0)),
                    "max_case_temp": self._safe_float(row.get("MaxCaseTemp", 0)),
                    "power_class": str(row.get("PowerClass", "")),
                }

        # Build optics info lookup
        optics_lookup = {}
        if not optics_info_df.empty:
            for _, row in optics_info_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                key = f"{guid}:{port}"
                optics_lookup[key] = {
                    "tx_power_dbm": self._safe_float(row.get("TxPower_dBm", row.get("TxPower", 0))),
                    "rx_power_dbm": self._safe_float(row.get("RxPower_dBm", row.get("RxPower", 0))),
                    "tx_bias_ma": self._safe_float(row.get("TxBias_mA", row.get("TxBias", 0))),
                    "voltage_v": self._safe_float(row.get("Voltage_V", row.get("Voltage", 0))),
                    "temperature_c": self._safe_float(row.get("Temperature_C", row.get("Temperature", 0))),
                    "los_alarm": self._safe_bool(row.get("LOS", row.get("LossOfSignal", False))),
                    "tx_fault": self._safe_bool(row.get("TxFault", False)),
                    "dom_capable": self._safe_bool(row.get("DOMCapable", row.get("DDM", True))),
                }

        # Build MLNX transceiver lookup
        mlnx_lookup = {}
        if not mlnx_trans_df.empty:
            for _, row in mlnx_trans_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                key = f"{guid}:{port}"
                mlnx_lookup[key] = {
                    "tech_type": str(row.get("TechType", row.get("Technology", ""))),
                    "form_factor": str(row.get("FormFactor", row.get("Type", ""))),
                    "fw_version": str(row.get("FWVersion", row.get("Firmware", ""))),
                    "cable_info": str(row.get("CableInfo", "")),
                    "connector_type": str(row.get("ConnectorType", row.get("Connector", ""))),
                    "mlnx_verified": self._safe_bool(row.get("MLNXVerified", row.get("Verified", False))),
                }

        # Process CABLE_INFO (primary source)
        df_to_process = cable_info_df if not cable_info_df.empty else optics_info_df

        for _, row in df_to_process.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
            port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
            key = f"{node_guid}:{port_num}"
            total_cables += 1

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Basic cable info
            vendor = str(row.get("Vendor", row.get("VendorName", "Unknown")))
            vendor_distribution[vendor] += 1

            cable_type = str(row.get("CableType", row.get("Type", "Unknown")))
            cable_type_distribution[cable_type] += 1

            # Categorize cable type
            cable_type_lower = cable_type.lower()
            is_optical = "optical" in cable_type_lower or "fiber" in cable_type_lower or "sm" in cable_type_lower
            is_aoc = "aoc" in cable_type_lower or "active" in cable_type_lower
            is_copper = "copper" in cable_type_lower or "dac" in cable_type_lower or "passive" in cable_type_lower

            if is_optical:
                optical_count += 1
            elif is_aoc:
                aoc_count += 1
            elif is_copper:
                copper_count += 1

            # Cable length
            length_m = self._safe_float(row.get("Length", row.get("CableLength", 0)))
            length_bucket = self._categorize_length(length_m)
            length_distribution[length_bucket] += 1

            # Speed/rate
            speed = str(row.get("Speed", row.get("Rate", row.get("SupportedSpeed", ""))))
            if speed:
                speed_distribution[speed] += 1

            # Compliance
            compliance_code = str(row.get("ComplianceCode", row.get("Compliance", "")))
            speed_compliant = self._safe_bool(row.get("SpeedCompliant", True))
            if not speed_compliant:
                compliance_issues += 1

            # Get extended info
            ext_info = ext_lookup.get(key, {})

            # Get optics info
            optics_info = optics_lookup.get(key, {})
            temperature = optics_info.get("temperature_c", self._safe_float(row.get("Temperature", 0)))
            tx_power = optics_info.get("tx_power_dbm", 0)
            rx_power = optics_info.get("rx_power_dbm", 0)
            tx_bias = optics_info.get("tx_bias_ma", 0)
            voltage = optics_info.get("voltage_v", 0)
            dom_capable = optics_info.get("dom_capable", False)
            if dom_capable:
                dom_capable_count += 1

            # Get MLNX transceiver info
            mlnx_info = mlnx_lookup.get(key, {})

            # Detect issues
            issues = []
            severity = "normal"

            # Temperature checks
            if temperature >= TEMP_CRITICAL_THRESHOLD:
                issues.append(f"Critical temp: {temperature:.1f}°C")
                severity = "critical"
                temp_critical_count += 1
            elif temperature >= TEMP_WARNING_THRESHOLD:
                issues.append(f"High temp: {temperature:.1f}°C")
                if severity != "critical":
                    severity = "warning"
                temp_warning_count += 1

            # TX power checks
            if tx_power != 0:
                if tx_power < TX_POWER_LOW_CRITICAL:
                    issues.append(f"TX power critical: {tx_power:.1f}dBm")
                    severity = "critical"
                    power_critical_count += 1
                elif tx_power < TX_POWER_LOW_WARNING:
                    issues.append(f"TX power low: {tx_power:.1f}dBm")
                    if severity != "critical":
                        severity = "warning"
                    power_warning_count += 1

            # RX power checks
            if rx_power != 0:
                if rx_power < RX_POWER_LOW_CRITICAL:
                    issues.append(f"RX power critical: {rx_power:.1f}dBm")
                    severity = "critical"
                    power_critical_count += 1
                elif rx_power < RX_POWER_LOW_WARNING:
                    issues.append(f"RX power low: {rx_power:.1f}dBm")
                    if severity != "critical":
                        severity = "warning"
                    power_warning_count += 1

            # LOS and faults
            if optics_info.get("los_alarm", False):
                issues.append("Loss of Signal alarm")
                severity = "critical"
            if optics_info.get("tx_fault", False):
                issues.append("TX Fault")
                severity = "critical"

            # Compliance check
            if not speed_compliant:
                issues.append("Speed compliance issue")
                if severity == "normal":
                    severity = "warning"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "Vendor": vendor,
                "CableType": cable_type,
                "IsOptical": is_optical,
                "IsAOC": is_aoc,
                "IsCopper": is_copper,
                "LengthM": length_m,
                "Speed": speed,
                "ComplianceCode": compliance_code,
                "SpeedCompliant": speed_compliant,
                "Temperature_C": round(temperature, 1),
                "TxPower_dBm": round(tx_power, 2) if tx_power != 0 else None,
                "RxPower_dBm": round(rx_power, 2) if rx_power != 0 else None,
                "TxBias_mA": round(tx_bias, 2) if tx_bias != 0 else None,
                "Voltage_V": round(voltage, 3) if voltage != 0 else None,
                "DOMCapable": dom_capable,
                "VendorPN": ext_info.get("vendor_pn", ""),
                "VendorSN": ext_info.get("vendor_sn", ""),
                "DateCode": ext_info.get("date_code", ""),
                "Wavelength": ext_info.get("wavelength", 0),
                "PowerClass": ext_info.get("power_class", ""),
                "TechType": mlnx_info.get("tech_type", ""),
                "FormFactor": mlnx_info.get("form_factor", ""),
                "ConnectorType": mlnx_info.get("connector_type", ""),
                "FWVersion": mlnx_info.get("fw_version", ""),
                "MLNXVerified": mlnx_info.get("mlnx_verified", False),
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }

            # 🆕 只添加异常端口 (过滤掉normal)
            if severity != "normal":
                records.append(record)

        # Build summary
        summary = {
            "total_cables": total_cables,
            "optical_count": optical_count,
            "aoc_count": aoc_count,
            "copper_count": copper_count,
            "dom_capable_count": dom_capable_count,
            "temp_warning_count": temp_warning_count,
            "temp_critical_count": temp_critical_count,
            "power_warning_count": power_warning_count,
            "power_critical_count": power_critical_count,
            "compliance_issues": compliance_issues,
            "vendor_distribution": dict(sorted(vendor_distribution.items(), key=lambda x: -x[1])[:10]),
            "cable_type_distribution": dict(sorted(cable_type_distribution.items(), key=lambda x: -x[1])),
            "speed_distribution": dict(sorted(speed_distribution.items(), key=lambda x: -x[1])),
            "length_distribution": dict(sorted(length_distribution.items())),
            "cable_info_rows": len(cable_info_df),
            "optics_info_rows": len(optics_info_df),
            "mlnx_trans_rows": len(mlnx_trans_df),
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("Temperature_C", 0)
        ))

        return CableEnhancedResult(data=records[:2000], anomalies=None, summary=summary)

    def _categorize_length(self, length_m: float) -> str:
        """Categorize cable length into buckets."""
        if length_m <= 0:
            return "Unknown"
        elif length_m <= 1:
            return "0-1m"
        elif length_m <= 3:
            return "1-3m"
        elif length_m <= 5:
            return "3-5m"
        elif length_m <= 10:
            return "5-10m"
        elif length_m <= 30:
            return "10-30m"
        elif length_m <= 100:
            return "30-100m"
        else:
            return ">100m"

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
            return str(value).strip().lower() in ("1", "true", "yes")
        except (TypeError, ValueError):
            return False
