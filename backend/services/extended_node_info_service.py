"""Extended Node Info service for additional node attributes.

Uses tables:
- EXTENDED_NODE_INFO: Extended node attributes (5,291 rows typical)
- GENERAL_INFO_SMP: SMP general information (6,150 rows)
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
class ExtendedNodeInfoResult:
    """Result from Extended Node Info analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class ExtendedNodeInfoService:
    """Analyze extended node information for additional device attributes."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> ExtendedNodeInfoResult:
        """Run Extended Node Info analysis."""
        ext_node_df = self._try_read_table("EXTENDED_NODE_INFO")
        smp_info_df = self._try_read_table("GENERAL_INFO_SMP")

        if ext_node_df.empty and smp_info_df.empty:
            return ExtendedNodeInfoResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        node_type_distribution: Dict[str, int] = defaultdict(int)
        vendor_distribution: Dict[str, int] = defaultdict(int)
        capability_counts: Dict[str, int] = defaultdict(int)
        total_ports = 0

        # Build SMP info lookup
        smp_lookup = {}
        if not smp_info_df.empty:
            for _, row in smp_info_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                smp_lookup[guid] = {
                    "class_version": self._safe_int(row.get("ClassVersion", 0)),
                    "base_version": self._safe_int(row.get("BaseVersion", 0)),
                    "capability_mask": self._safe_hex(row.get("CapabilityMask", "0")),
                    "capability_mask2": self._safe_hex(row.get("CapabilityMask2", "0")),
                    "resp_time_value": self._safe_int(row.get("RespTimeValue", 0)),
                }

        # Process extended node info
        df_to_process = ext_node_df if not ext_node_df.empty else smp_info_df

        for _, row in df_to_process.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("GUID", "")))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Node type
            node_type = str(row.get("NodeType", row.get("Type", "Unknown")))
            node_type_distribution[node_type] += 1

            # Vendor info
            vendor_id = str(row.get("VendorID", row.get("VendorId", "")))
            if vendor_id:
                vendor_distribution[vendor_id] += 1

            # Port count
            num_ports = self._safe_int(row.get("NumPorts", row.get("PortCount", 0)))
            total_ports += num_ports

            # Device ID and revision
            device_id = self._safe_hex(row.get("DeviceID", row.get("DeviceId", "0")))
            revision = self._safe_int(row.get("Revision", row.get("Rev", 0)))

            # LID range
            lid = self._safe_int(row.get("LID", row.get("BaseLID", 0)))
            lid_range = self._safe_int(row.get("LMC", 0))

            # Partition cap
            partition_cap = self._safe_int(row.get("PartitionCap", 0))

            # Get SMP info if available
            smp_info = smp_lookup.get(node_guid, {})

            # Capability analysis
            cap_mask = smp_info.get("capability_mask", 0)
            capabilities = self._decode_capabilities(cap_mask)
            for cap in capabilities:
                capability_counts[cap] += 1

            # Detect potential issues
            issues = []
            severity = "normal"

            if num_ports == 0:
                issues.append("No ports reported")
                severity = "warning"

            if lid == 0:
                issues.append("No LID assigned")
                severity = "warning"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "NodeType": node_type,
                "VendorID": vendor_id,
                "DeviceID": hex(device_id) if isinstance(device_id, int) else device_id,
                "Revision": revision,
                "NumPorts": num_ports,
                "LID": lid,
                "LMC": lid_range,
                "PartitionCap": partition_cap,
                "ClassVersion": smp_info.get("class_version", 0),
                "BaseVersion": smp_info.get("base_version", 0),
                "CapabilityMask": hex(cap_mask) if cap_mask else "0x0",
                "Capabilities": ", ".join(capabilities) if capabilities else "",
                "RespTimeValue": smp_info.get("resp_time_value", 0),
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = {
            "total_nodes": len(df_to_process),
            "total_ports": total_ports,
            "node_type_distribution": dict(sorted(node_type_distribution.items(), key=lambda x: -x[1])),
            "vendor_distribution": dict(sorted(vendor_distribution.items(), key=lambda x: -x[1])),
            "capability_distribution": dict(sorted(capability_counts.items(), key=lambda x: -x[1])),
            "smp_entries": len(smp_info_df),
            "avg_ports_per_node": round(total_ports / max(len(df_to_process), 1), 1),
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            r.get("NodeName", "")
        ))

        return ExtendedNodeInfoResult(data=records[:2000], anomalies=None, summary=summary)

    def _decode_capabilities(self, cap_mask: int) -> List[str]:
        """Decode SMP capability mask."""
        capabilities = []
        cap_definitions = {
            0: "IsSM",
            1: "IsNoticeSupported",
            2: "IsTrapSupported",
            3: "IsOptionalIPDSupported",
            4: "IsAutomaticMigrationSupported",
            5: "IsSLMappingSupported",
            6: "IsMKeyNVRAM",
            7: "IsPKeyNVRAM",
            8: "IsLEDInfoSupported",
            9: "IsSMDisabled",
            10: "IsSystemImageGUIDSupported",
            11: "IsPKeySwitchExternalPortTrapSupported",
            16: "IsCommunicationManagementSupported",
            17: "IsSNMPTunnelingSupported",
            18: "IsReinitSupported",
            19: "IsDeviceManagementSupported",
            20: "IsVendorClassSupported",
            21: "IsDRNoticeSupported",
            22: "IsCapabilityMaskNoticeSupported",
            23: "IsBootManagementSupported",
            24: "IsLinkRoundTripLatencySupported",
            25: "IsClientReregistrationSupported",
            26: "IsOtherLocalChangesNoticeSupported",
            27: "IsLinkSpeedWidthPairsTableSupported",
        }
        for bit, name in cap_definitions.items():
            if cap_mask & (1 << bit):
                capabilities.append(name)
        return capabilities

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
    def _safe_hex(value: object) -> int:
        try:
            if pd.isna(value):
                return 0
            if isinstance(value, (int, float)):
                return int(value)
            s = str(value).strip()
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(float(s))
        except (TypeError, ValueError):
            return 0
