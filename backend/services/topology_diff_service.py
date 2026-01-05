"""Compares ibdiagnet topology against an expected baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .anomalies import IBH_ANOMALY_AGG_COL, IBH_ANOMALY_AGG_WEIGHT, AnomlyType
from .ibdiagnet import read_index_table, read_table


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
WIDTH_PRIORITY = [
    (0x08, 12),
    (0x04, 8),
    (0x02, 4),
    (0x10, 2),
    (0x01, 1),
]


@dataclass
class ExpectedNode:
    guid: str
    name: Optional[str] = None
    type: Optional[str] = None


@dataclass
class ExpectedLink:
    src_guid: str
    src_port: int
    dst_guid: str
    dst_port: int
    min_speed: Optional[str] = None
    min_width: Optional[str] = None


class TopologyDiffService:
    """Runs expected topology validation if a baseline file is provided."""

    def __init__(self, dataset_root: Path, expected_topology_file: Path):
        self.dataset_root = Path(dataset_root)
        self.expected_topology_file = Path(expected_topology_file)
        if not self.expected_topology_file.exists():
            raise FileNotFoundError(self.expected_topology_file)
        self._expected_nodes, self._expected_links = self._load_expectations()
        self._db_csv = self._find_db_csv()
        self._index = read_index_table(self._db_csv)
        self._ports_df: Optional[pd.DataFrame] = None
        self._links_df: Optional[pd.DataFrame] = None
        self._nodes_df: Optional[pd.DataFrame] = None
        self._port_cache: Dict[Tuple[str, int], Dict[str, Optional[float]]] = {}

    def diff_rows(self) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        rows.extend(self._missing_node_rows())
        rows.extend(self._missing_link_rows())
        rows.extend(self._link_speed_rows())
        return rows

    def _missing_node_rows(self) -> List[Dict[str, object]]:
        actual_guids = set(self._nodes_table()["NodeGUID"])
        missing = []
        for node in self._expected_nodes:
            if node.guid not in actual_guids:
                desc = node.name or node.guid
                missing.append(
                    {
                        "NodeGUID": node.guid,
                        "PortNumber": 0,
                        "Topology Issue": f"Expected node missing: {desc}",
                        IBH_ANOMALY_AGG_COL: AnomlyType.IBH_ASYM_TOPO.value,
                        IBH_ANOMALY_AGG_WEIGHT: 1.0,
                    }
                )
        return missing

    def _missing_link_rows(self) -> List[Dict[str, object]]:
        actual_links = self._link_set()
        missing = []
        for link in self._expected_links:
            key = (link.src_guid, link.src_port, link.dst_guid, link.dst_port)
            if key not in actual_links:
                missing.append(
                    {
                        "NodeGUID": link.src_guid,
                        "PortNumber": link.src_port,
                        "Topology Issue": f"Expected link missing to {link.dst_guid} port {link.dst_port}",
                        IBH_ANOMALY_AGG_COL: AnomlyType.IBH_ASYM_TOPO.value,
                        IBH_ANOMALY_AGG_WEIGHT: 1.0,
                    }
                )
        return missing

    def _link_speed_rows(self) -> List[Dict[str, object]]:
        rows = []
        for link in self._expected_links:
            requirements = self._link_requirements(link)
            if not requirements:
                continue
            src_info = self._port_info(link.src_guid, link.src_port)
            dst_info = self._port_info(link.dst_guid, link.dst_port)
            if requirements["min_speed"] and src_info["speed_priority"] < requirements["min_speed"]:
                rows.append(
                    self._speed_row(
                        link,
                        endpoint="src",
                        description=f"Port below expected speed {requirements['min_speed_label']}",
                    )
                )
            if requirements["min_speed"] and dst_info["speed_priority"] < requirements["min_speed"]:
                rows.append(
                    self._speed_row(
                        link,
                        endpoint="dst",
                        description=f"Peer port below expected speed {requirements['min_speed_label']}",
                    )
                )
            if requirements["min_width"] and src_info["width"] < requirements["min_width"]:
                rows.append(
                    self._speed_row(link, endpoint="src", description="Port width below expectation")
                )
            if requirements["min_width"] and dst_info["width"] < requirements["min_width"]:
                rows.append(
                    self._speed_row(link, endpoint="dst", description="Peer port width below expectation")
                )
        return rows

    def _speed_row(self, link: ExpectedLink, endpoint: str, description: str) -> Dict[str, object]:
        guid = link.src_guid if endpoint == "src" else link.dst_guid
        port = link.src_port if endpoint == "src" else link.dst_port
        return {
            "NodeGUID": guid,
            "PortNumber": port,
            "Topology Issue": description,
            IBH_ANOMALY_AGG_COL: AnomlyType.IBH_LINK_DOWNSHIFT.value,
            IBH_ANOMALY_AGG_WEIGHT: 1.0,
        }

    def _link_requirements(self, link: ExpectedLink) -> Optional[Dict[str, object]]:
        min_speed_label = (link.min_speed or "").strip()
        min_speed_priority = self._speed_priority_from_label(min_speed_label)
        min_width = self._width_from_label(link.min_width)
        if not min_speed_priority and not min_width:
            return None
        return {
            "min_speed_label": min_speed_label or "",
            "min_speed": min_speed_priority,
            "min_width": min_width or 0,
        }

    def _port_info(self, guid: str, port_number: int) -> Dict[str, int]:
        key = (guid, port_number)
        cached = self._port_cache.get(key)
        if cached:
            return cached
        ports = self._ports_table()
        row = ports[(ports["NodeGUID"] == guid) & (ports["PortNumber"] == port_number)]
        if row.empty:
            data = {"speed_priority": 0, "width": 0}
        else:
            item = row.iloc[0]
            speed_priority = self._decode_speed(item.get("LinkSpeedActv"))[0] or 0
            width_value = self._decode_width(item.get("LinkWidthActv"))[0] or 0
            data = {"speed_priority": speed_priority, "width": width_value}
        self._port_cache[key] = data
        return data

    def _link_set(self) -> set[Tuple[str, int, str, int]]:
        links = set()
        df = self._links_table()
        if df.empty:
            return links
        for _, row in df.iterrows():
            g1 = self._normalize_guid(row.get("NodeGuid1"))
            g2 = self._normalize_guid(row.get("NodeGuid2"))
            p1 = self._safe_port(row.get("PortNum1"))
            p2 = self._safe_port(row.get("PortNum2"))
            if g1 and g2 and p1 is not None and p2 is not None:
                links.add((g1, p1, g2, p2))
                links.add((g2, p2, g1, p1))
        return links

    def _load_expectations(self) -> Tuple[List[ExpectedNode], List[ExpectedLink]]:
        raw = json.loads(self.expected_topology_file.read_text(encoding="utf-8"))
        nodes = [
            ExpectedNode(
                guid=self._normalize_guid(entry.get("guid")),
                name=entry.get("name"),
                type=entry.get("type"),
            )
            for entry in raw.get("nodes", [])
            if entry.get("guid")
        ]
        links = []
        for entry in raw.get("links", []):
            src_guid = self._normalize_guid(entry.get("src_guid"))
            dst_guid = self._normalize_guid(entry.get("dst_guid"))
            src_port = self._safe_port(entry.get("src_port"))
            dst_port = self._safe_port(entry.get("dst_port"))
            if not src_guid or not dst_guid or src_port is None or dst_port is None:
                continue
            links.append(
                ExpectedLink(
                    src_guid=src_guid,
                    dst_guid=dst_guid,
                    src_port=src_port,
                    dst_port=dst_port,
                    min_speed=entry.get("min_speed"),
                    min_width=entry.get("min_width"),
                )
            )
        return nodes, links

    def _nodes_table(self) -> pd.DataFrame:
        if self._nodes_df is not None:
            return self._nodes_df
        if "NODES" not in self._index.index:
            self._nodes_df = pd.DataFrame(columns=["NodeGUID"])
            return self._nodes_df
        df = read_table(self._db_csv, "NODES", self._index)
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        self._nodes_df = df
        return df

    def _links_table(self) -> pd.DataFrame:
        if self._links_df is not None:
            return self._links_df
        if "LINKS" not in self._index.index:
            self._links_df = pd.DataFrame()
            return self._links_df
        df = read_table(self._db_csv, "LINKS", self._index)
        self._links_df = df
        return df

    def _ports_table(self) -> pd.DataFrame:
        if self._ports_df is not None:
            return self._ports_df
        if "PORTS" not in self._index.index:
            self._ports_df = pd.DataFrame(
                columns=["NodeGUID", "PortNumber", "LinkSpeedActv", "LinkWidthActv"]
            )
            return self._ports_df
        df = read_table(self._db_csv, "PORTS", self._index)
        df.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber"}, inplace=True)
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        df["PortNumber"] = pd.to_numeric(df["PortNumber"], errors="coerce")
        self._ports_df = df
        return df

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    @staticmethod
    def _normalize_guid(value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.lower().startswith("0x"):
            try:
                return hex(int(text, 16))
            except ValueError:
                return text.lower()
        try:
            if text.isdigit():
                return hex(int(text))
        except ValueError:
            return text.lower()
        return text.lower()

    @staticmethod
    def _safe_port(value: object) -> Optional[int]:
        try:
            if value is None:
                return None
            if isinstance(value, str) and not value.strip():
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _width_from_label(label: Optional[str]) -> Optional[int]:
        if not label:
            return None
        digits = "".join(ch for ch in str(label) if ch.isdigit())
        try:
            return int(digits)
        except ValueError:
            return None

    @staticmethod
    def _speed_priority_from_label(label: str) -> int:
        tokens = label.lower()
        if not tokens:
            return 0
        if "ndr" in tokens or "400" in tokens:
            return 8
        if "hdr" in tokens or "200" in tokens:
            return 7
        if "edr" in tokens or "100" in tokens:
            return 6
        if "fdr10" in tokens:
            return 5
        if "fdr" in tokens:
            return 4
        if "qdr" in tokens or "40" in tokens:
            return 3
        if "ddr" in tokens or "20" in tokens:
            return 2
        if "sdr" in tokens or "10" in tokens:
            return 1
        return 0

    @staticmethod
    def _decode_speed(value) -> Tuple[Optional[int], Optional[str]]:
        try:
            code = int(value)
        except (TypeError, ValueError):
            return (None, None)
        for bit, (label, priority) in SPEED_PRIORITY:
            if code & bit:
                return (priority, label)
        return (None, None)

    @staticmethod
    def _decode_width(value) -> Tuple[Optional[int], Optional[str]]:
        try:
            code = int(value)
        except (TypeError, ValueError):
            return (None, None)
        for bit, width in WIDTH_PRIORITY:
            if code & bit:
                return (width, f"{width}X")
        return (None, None)
