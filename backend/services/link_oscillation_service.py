"""Link oscillation (link flap) analysis service."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .dataset_inventory import DatasetInventory
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

PM_INFO_TABLE = "PM_INFO"


@dataclass
class LinkOscillationResult:
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class LinkOscillationService:
    """Builds bi-directional link flap records using PM counters."""

    def __init__(self, dataset_root: Path, dataset_inventory: DatasetInventory | None = None):
        self.dataset_root = dataset_root
        self._inventory = dataset_inventory or DatasetInventory(dataset_root)
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> LinkOscillationResult:
        df = self._load_pm_info()
        if df.empty:
            return LinkOscillationResult()

        topology = self._get_topology()
        node_meta = self._build_node_meta()
        port_meta = self._build_port_meta()

        pair_records: Dict[Tuple[Tuple[str, int], Tuple[str, int]], Dict[str, object]] = {}

        for _, row in df.iterrows():
            node_guid = row["NodeGUID"]
            port_number = row["PortNumber"]
            neighbor_guid = topology.attached_guid(node_guid, port_number) if topology else None
            neighbor_port = topology.attached_port(node_guid, port_number) if topology else None
            if not neighbor_guid or neighbor_port is None:
                continue

            endpoints = self._pair_key(node_guid, port_number, neighbor_guid, neighbor_port)
            entry = pair_records.setdefault(
                endpoints,
                {
                    "endpoints": endpoints,
                    "node_a": None,
                    "node_b": None,
                    "total_link_flaps": 0.0,
                    "max_side_flaps": 0.0,
                },
            )

            side_key = "node_a" if endpoints[0] == (node_guid, port_number) else "node_b"
            endpoint_payload = self._build_endpoint_payload(row, node_meta, port_meta)
            entry[side_key] = endpoint_payload
            entry["total_link_flaps"] += endpoint_payload["link_down_total"]
            entry["max_side_flaps"] = max(entry["max_side_flaps"], endpoint_payload["link_down_total"])

        records: List[Dict[str, object]] = []
        for entry in pair_records.values():
            node_a = entry.get("node_a")
            node_b = entry.get("node_b")
            if not node_a or not node_b:
                continue
            total_flaps = entry["total_link_flaps"]
            severity = self._classify(total_flaps)
            records.append(
                {
                    "NodeDesc1": node_a["node_desc"],
                    "PortNum1": node_a["port_number"],
                    "DeviceID1": node_a["device_id"],
                    "LID1": node_a["lid"],
                    "Vendor1": node_a["vendor"],
                    "LinkDownedCounter1": node_a["link_down_total"],
                    "LinkDownedCounterExt1": node_a["link_down_ext"],
                    "LinkDownedCounterBase1": node_a["link_down_base"],
                    "NodeDesc2": node_b["node_desc"],
                    "PortNum2": node_b["port_number"],
                    "DeviceID2": node_b["device_id"],
                    "LID2": node_b["lid"],
                    "Vendor2": node_b["vendor"],
                    "LinkDownedCounter2": node_b["link_down_total"],
                    "LinkDownedCounterExt2": node_b["link_down_ext"],
                    "LinkDownedCounterBase2": node_b["link_down_base"],
                    "TotalLinkFlaps": total_flaps,
                    "Severity": severity,
                }
            )

        if not records:
            return LinkOscillationResult()

        # Sort by total flaps desc
        records.sort(key=lambda item: item["TotalLinkFlaps"], reverse=True)
        max_rows = 200
        trimmed = records[:max_rows]

        summary = {
            "total_paths": len(records),
            "critical_paths": sum(1 for rec in records if rec["Severity"] == "critical"),
            "warning_paths": sum(1 for rec in records if rec["Severity"] == "warning"),
            "max_link_flaps": trimmed[0]["TotalLinkFlaps"],
            "top_path": {
                "node_a": trimmed[0]["NodeDesc1"],
                "node_b": trimmed[0]["NodeDesc2"],
                "total_flaps": trimmed[0]["TotalLinkFlaps"],
            },
            "preview_rows": len(trimmed),
        }

        return LinkOscillationResult(data=trimmed, summary=summary)

    def _load_pm_info(self) -> pd.DataFrame:
        try:
            df = self._inventory.read_table(PM_INFO_TABLE)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to read %s: %s", PM_INFO_TABLE, exc)
            return pd.DataFrame()
        if df.empty:
            return df
        df = df.copy()
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        df["PortNumber"] = pd.to_numeric(df["PortNumber"], errors="coerce").fillna(0).astype(int)
        for column in ("LinkDownedCounter", "LinkDownedCounterExt"):
            if column not in df.columns:
                df[column] = 0
        df["LinkDownedCounter"] = pd.to_numeric(df["LinkDownedCounter"], errors="coerce").fillna(0.0)
        df["LinkDownedCounterExt"] = pd.to_numeric(df["LinkDownedCounterExt"], errors="coerce").fillna(0.0)
        df["LinkDownCount"] = df["LinkDownedCounter"] + df["LinkDownedCounterExt"]
        df = df[df["LinkDownCount"] > 0]
        return df

    def _build_node_meta(self) -> Dict[str, Dict[str, object]]:
        try:
            nodes = self._inventory.read_table("NODES")
        except Exception:
            nodes = pd.DataFrame()
        if nodes.empty:
            return {}
        nodes = nodes.copy()
        nodes["NodeGUID"] = nodes["NodeGUID"].apply(self._normalize_guid)
        nodes["NodeDesc"] = nodes["NodeDesc"].astype(str).str.strip('"')
        nodes["DeviceID"] = pd.to_numeric(nodes.get("DeviceID"), errors="coerce").fillna(0).astype(int)
        nodes["VendorID"] = pd.to_numeric(nodes.get("VendorID"), errors="coerce").fillna(0).astype(int)
        return {
            guid: {
                "node_desc": row["NodeDesc"],
                "device_id": row["DeviceID"],
                "vendor": self._vendor_name(row["VendorID"], row["NodeDesc"]),
            }
            for guid, row in nodes.set_index("NodeGUID").iterrows()
            if guid
        }

    def _build_port_meta(self) -> Dict[Tuple[str, int], Dict[str, object]]:
        try:
            ports = self._inventory.read_table("PORTS")
        except Exception:
            ports = pd.DataFrame()
        if ports.empty:
            return {}
        ports = ports.copy()
        ports["NodeGuid"] = ports["NodeGuid"].apply(self._normalize_guid)
        ports["PortNum"] = pd.to_numeric(ports["PortNum"], errors="coerce").fillna(0).astype(int)
        ports["LID"] = pd.to_numeric(ports.get("LID"), errors="coerce").fillna(0).astype(int)
        return {
            (row["NodeGuid"], row["PortNum"]): {
                "lid": row.get("LID", 0),
            }
            for _, row in ports.iterrows()
            if row["NodeGuid"]
        }

    def _build_endpoint_payload(
        self,
        row: pd.Series,
        node_meta: Dict[str, Dict[str, object]],
        port_meta: Dict[Tuple[str, int], Dict[str, object]],
    ) -> Dict[str, object]:
        guid = row["NodeGUID"]
        port_number = row["PortNumber"]
        base = float(row.get("LinkDownedCounter") or 0.0)
        ext = float(row.get("LinkDownedCounterExt") or 0.0)
        total = float(row.get("LinkDownCount") or (base + ext))
        if total <= 0:
            total = base + ext
        node_info = node_meta.get(guid, {})
        port_info = port_meta.get((guid, port_number), {})
        return {
            "node_guid": guid,
            "node_desc": node_info.get("node_desc") or guid,
            "port_number": port_number,
            "device_id": node_info.get("device_id"),
            "vendor": node_info.get("vendor", "Unknown"),
            "lid": port_info.get("lid", 0),
            "link_down_total": float(total),
            "link_down_ext": float(ext),
            "link_down_base": float(base),
        }

    def _pair_key(
        self,
        guid_a: str,
        port_a: int,
        guid_b: str,
        port_b: int,
    ) -> Tuple[Tuple[str, int], Tuple[str, int]]:
        endpoints = sorted(
            [
                (guid_a, port_a if port_a is not None else 0),
                (guid_b, port_b if port_b is not None else 0),
            ],
            key=lambda item: (item[0] or "", item[1]),
        )
        return (endpoints[0], endpoints[1])

    def _get_topology(self) -> TopologyLookup:
        if self._topology is None:
            try:
                self._topology = TopologyLookup(self.dataset_root)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to create topology lookup: %s", exc)
                self._topology = None
        return self._topology

    @staticmethod
    def _normalize_guid(value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        if text.lower().startswith("0x"):
            try:
                return hex(int(text, 16))
            except (ValueError, TypeError):
                return text.lower()
        try:
            return hex(int(text))
        except (ValueError, TypeError):
            return text.lower()

    @staticmethod
    def _vendor_name(vendor_id: int, node_desc: str) -> str:
        vendor_map = {
            713: "NVIDIA",
            32832: "NVIDIA",
            4319: "OEM",
        }
        if vendor_id in vendor_map:
            return vendor_map[vendor_id]
        if "nvidia" in (node_desc or "").lower():
            return "NVIDIA"
        if "mellanox" in (node_desc or "").lower():
            return "Mellanox"
        return f"Vendor {vendor_id}" if vendor_id else "Unknown"

    @staticmethod
    def _classify(total_flaps: float) -> str:
        if total_flaps >= 100:
            return "critical"
        if total_flaps >= 20:
            return "warning"
        return "info"
