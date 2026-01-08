"""N2N Security service for node-to-node communication and management path analysis.

Uses tables:
- N2N_CLASS_PORT_INFO: Node-to-Node class port information (~6K rows)
- N2N_KEY_INFO: N2N key exchange and security information (~6K rows)
- SMP_NODE_INFO: Subnet Management Protocol node info (for cross-reference)

This service analyzes the management path security and N2N communication settings.
N2N communication is critical for in-band management and SM queries.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class N2NSecurityResult:
    """Result from N2N Security analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class N2NSecurityService:
    """Analyze N2N security and management path configuration."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> N2NSecurityResult:
        """Run N2N Security analysis."""
        n2n_class_df = self._try_read_table("N2N_CLASS_PORT_INFO")
        n2n_key_df = self._try_read_table("N2N_KEY_INFO")
        smp_node_df = self._try_read_table("SMP_NODE_INFO")

        if n2n_class_df.empty and n2n_key_df.empty:
            return N2NSecurityResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        total_nodes = 0
        nodes_with_n2n_enabled = 0
        nodes_with_keys = 0
        security_violations = 0
        class_mismatches = 0

        # Distribution tracking
        capability_distribution: Dict[str, int] = defaultdict(int)
        class_distribution: Dict[str, int] = defaultdict(int)
        key_status_distribution: Dict[str, int] = defaultdict(int)

        # Build N2N key lookup
        key_lookup = {}
        if not n2n_key_df.empty:
            for _, row in n2n_key_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                key_lookup[guid] = {
                    "key_present": self._safe_bool(row.get("KeyPresent", row.get("HasKey", False))),
                    "key_status": str(row.get("KeyStatus", row.get("Status", "Unknown"))),
                    "key_violation": self._safe_bool(row.get("KeyViolation", row.get("Violation", False))),
                    "partition_key": str(row.get("PartitionKey", row.get("PKey", ""))),
                    "q_key": str(row.get("QKey", "")),
                    "m_key": str(row.get("MKey", "")),
                    "trap_count": self._safe_int(row.get("TrapCount", 0)),
                }
                if key_lookup[guid]["key_present"]:
                    nodes_with_keys += 1
                key_status_distribution[key_lookup[guid]["key_status"]] += 1

        # Build SMP node info lookup
        smp_lookup = {}
        if not smp_node_df.empty:
            for _, row in smp_node_df.iterrows():
                guid = str(row.get("NodeGuid", row.get("GUID", "")))
                smp_lookup[guid] = {
                    "node_type": str(row.get("NodeType", row.get("Type", ""))),
                    "num_ports": self._safe_int(row.get("NumPorts", row.get("Ports", 0))),
                    "system_image_guid": str(row.get("SystemImageGuid", row.get("SysImgGuid", ""))),
                    "partition_cap": self._safe_int(row.get("PartitionCap", 0)),
                    "device_id": str(row.get("DeviceID", row.get("DevID", ""))),
                    "revision": str(row.get("Revision", "")),
                }

        # Process N2N_CLASS_PORT_INFO (primary source)
        if not n2n_class_df.empty:
            for _, row in n2n_class_df.iterrows():
                node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
                port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))
                total_nodes += 1

                # Get node name
                node_name = topology.node_label(node_guid) if topology else node_guid

                # N2N class and capability info
                base_version = self._safe_int(row.get("BaseVersion", 0))
                class_version = self._safe_int(row.get("ClassVersion", 0))
                capability_mask = self._safe_int(row.get("CapabilityMask", row.get("CapMask", 0)))
                capability_mask2 = self._safe_int(row.get("CapabilityMask2", row.get("CapMask2", 0)))

                # Decode capabilities
                capabilities = self._decode_capabilities(capability_mask, capability_mask2)
                for cap in capabilities:
                    capability_distribution[cap] += 1

                # Response time value
                resp_time = self._safe_int(row.get("RespTimeValue", row.get("ResponseTime", 0)))

                # Redirect/trap settings
                redirect_gid = str(row.get("RedirectGID", ""))
                redirect_qp = self._safe_int(row.get("RedirectQP", 0))
                redirect_pkey = str(row.get("RedirectPKey", ""))
                trap_gid = str(row.get("TrapGID", ""))
                trap_qp = self._safe_int(row.get("TrapQP", 0))
                trap_pkey = str(row.get("TrapPKey", ""))

                # Check if N2N is enabled
                n2n_enabled = capability_mask != 0 or redirect_gid or trap_gid
                if n2n_enabled:
                    nodes_with_n2n_enabled += 1

                # Get key info
                key_info = key_lookup.get(node_guid, {})

                # Get SMP info
                smp_info = smp_lookup.get(node_guid, {})

                # Detect issues
                issues = []
                severity = "normal"

                # Key violations
                if key_info.get("key_violation", False):
                    issues.append("Key violation detected")
                    severity = "critical"
                    security_violations += 1

                # Missing keys on nodes that should have them
                if n2n_enabled and not key_info.get("key_present", False):
                    issues.append("N2N enabled but no key present")
                    if severity != "critical":
                        severity = "warning"

                # High trap count
                trap_count = key_info.get("trap_count", 0)
                if trap_count > 100:
                    issues.append(f"High trap count: {trap_count}")
                    if severity == "normal":
                        severity = "info"

                # Class version mismatch (check if different from typical)
                if class_version > 0 and class_version != 2:  # Version 2 is standard
                    issues.append(f"Non-standard class version: {class_version}")
                    class_mismatches += 1

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_num,
                    "BaseVersion": base_version,
                    "ClassVersion": class_version,
                    "CapabilityMask": capability_mask,
                    "CapabilityMask2": capability_mask2,
                    "Capabilities": ", ".join(capabilities) if capabilities else "None",
                    "ResponseTime": resp_time,
                    "N2NEnabled": n2n_enabled,
                    "RedirectGID": redirect_gid,
                    "RedirectQP": redirect_qp,
                    "RedirectPKey": redirect_pkey,
                    "TrapGID": trap_gid,
                    "TrapQP": trap_qp,
                    "TrapPKey": trap_pkey,
                    "KeyPresent": key_info.get("key_present", False),
                    "KeyStatus": key_info.get("key_status", "Unknown"),
                    "KeyViolation": key_info.get("key_violation", False),
                    "PartitionKey": key_info.get("partition_key", ""),
                    "TrapCount": key_info.get("trap_count", 0),
                    "NodeType": smp_info.get("node_type", ""),
                    "NumPorts": smp_info.get("num_ports", 0),
                    "PartitionCap": smp_info.get("partition_cap", 0),
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)

        # If N2N_CLASS_PORT_INFO is empty but N2N_KEY_INFO exists, process that
        elif not n2n_key_df.empty:
            for _, row in n2n_key_df.iterrows():
                node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
                total_nodes += 1

                node_name = topology.node_label(node_guid) if topology else node_guid
                key_info = key_lookup.get(node_guid, {})
                smp_info = smp_lookup.get(node_guid, {})

                issues = []
                severity = "normal"

                if key_info.get("key_violation", False):
                    issues.append("Key violation")
                    severity = "critical"
                    security_violations += 1

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": 0,
                    "KeyPresent": key_info.get("key_present", False),
                    "KeyStatus": key_info.get("key_status", "Unknown"),
                    "KeyViolation": key_info.get("key_violation", False),
                    "PartitionKey": key_info.get("partition_key", ""),
                    "QKey": key_info.get("q_key", ""),
                    "MKey": key_info.get("m_key", ""),
                    "TrapCount": key_info.get("trap_count", 0),
                    "NodeType": smp_info.get("node_type", ""),
                    "Severity": severity,
                    "Issues": "; ".join(issues) if issues else "",
                }
                records.append(record)

        # Build summary
        summary = {
            "total_nodes": total_nodes,
            "nodes_with_n2n_enabled": nodes_with_n2n_enabled,
            "nodes_with_keys": nodes_with_keys,
            "security_violations": security_violations,
            "class_mismatches": class_mismatches,
            "n2n_coverage_pct": round(nodes_with_n2n_enabled / max(total_nodes, 1) * 100, 1),
            "key_coverage_pct": round(nodes_with_keys / max(total_nodes, 1) * 100, 1),
            "capability_distribution": dict(sorted(capability_distribution.items(), key=lambda x: -x[1])),
            "key_status_distribution": dict(sorted(key_status_distribution.items(), key=lambda x: -x[1])),
            "n2n_class_rows": len(n2n_class_df),
            "n2n_key_rows": len(n2n_key_df),
            "smp_node_rows": len(smp_node_df),
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("TrapCount", 0)
        ))

        return N2NSecurityResult(data=records[:2000], anomalies=None, summary=summary)

    def _decode_capabilities(self, cap_mask: int, cap_mask2: int) -> List[str]:
        """Decode capability masks into human-readable list."""
        capabilities = []

        # Common N2N capability bits (from InfiniBand spec)
        cap_bits = {
            0x0001: "IsTrapSupported",
            0x0002: "IsAutomaticMigrationSupported",
            0x0004: "IsSLMappingSupported",
            0x0008: "IsMKeyNVRAM",
            0x0010: "IsPKeyNVRAM",
            0x0020: "IsLEDInfoSupported",
            0x0040: "IsSMDisabled",
            0x0080: "IsSystemImageGUIDSupported",
            0x0100: "IsPKeySwitchExternalPortTrapSupported",
            0x0400: "IsExtendedSpeedsSupported",
            0x0800: "IsCapabilityMask2Supported",
            0x1000: "IsCommunicationManagementSupported",
            0x2000: "IsSNMPTunnelingSupported",
            0x4000: "IsReinitSupported",
            0x8000: "IsDeviceManagementSupported",
        }

        for bit, name in cap_bits.items():
            if cap_mask & bit:
                capabilities.append(name)

        # CapabilityMask2 bits (extended capabilities)
        cap2_bits = {
            0x0001: "IsSetNodeDescriptionSupported",
            0x0002: "IsPortInfoExtendedSpeedSupported",
            0x0004: "IsCableInfoSupported",
            0x0008: "IsPortInfoCapabilityMaskMatchSupported",
        }

        for bit, name in cap2_bits.items():
            if cap_mask2 & bit:
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
