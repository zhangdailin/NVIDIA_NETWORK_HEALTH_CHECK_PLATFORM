"""Lightweight topology lookup utilities for ibdiagnet datasets."""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from .ibdiagnet import read_index_table, read_table

logger = logging.getLogger(__name__)


class TopologyLookup:
    """Provides node labels and neighbor information for a dataset."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = Path(dataset_root)
        self._db_csv = self._find_db_csv()
        self._index_table = read_index_table(self._db_csv)
        self._node_names: Optional[Dict[str, str]] = None
        self._node_types: Optional[Dict[str, str]] = None
        self._port_neighbors: Optional[Dict[Tuple[str, int], Tuple[str, Optional[int]]]] = None

    def node_label(self, guid: object) -> Optional[str]:
        norm = self._normalize_guid(guid)
        if norm is None:
            return None
        return self._node_name_map().get(norm)

    def node_type(self, guid: object) -> Optional[str]:
        norm = self._normalize_guid(guid)
        if norm is None:
            return None
        return self._node_type_map().get(norm)

    def attached_guid(self, guid: object, port_number: object) -> Optional[str]:
        endpoint = self._attached_endpoint(guid, port_number)
        if endpoint:
            return endpoint[0]
        return None

    def attached_port(self, guid: object, port_number: object) -> Optional[int]:
        endpoint = self._attached_endpoint(guid, port_number)
        if endpoint:
            return endpoint[1]
        return None

    def _attached_endpoint(self, guid: object, port_number: object) -> Optional[Tuple[str, Optional[int]]]:
        norm_guid = self._normalize_guid(guid)
        port = self._safe_port(port_number)
        if norm_guid is None or port is None:
            return None
        return self._neighbor_map().get((norm_guid, port))

    def annotate_ports(self, df: pd.DataFrame, guid_col: str = "NodeGUID", port_col: str = "PortNumber") -> pd.DataFrame:
        if guid_col not in df.columns:
            return df
        df = df.copy()
        df["Node Name"] = df[guid_col].map(self.node_label)
        df["Node Type"] = df[guid_col].map(self.node_type)
        if port_col in df.columns:
            df["Attached To GUID"] = df.apply(
                lambda row: self.attached_guid(row.get(guid_col), row.get(port_col)),
                axis=1,
            )
            df["Attached To Port"] = df.apply(
                lambda row: self.attached_port(row.get(guid_col), row.get(port_col)),
                axis=1,
            )
            df["Attached To"] = df["Attached To GUID"].map(self.node_label)
            df["Attached To Type"] = df["Attached To GUID"].map(self.node_type)
        return df

    def annotate_nodes(self, df: pd.DataFrame, guid_col: str = "NodeGUID") -> pd.DataFrame:
        if guid_col not in df.columns:
            return df
        df = df.copy()
        df["Node Name"] = df[guid_col].map(self.node_label)
        df["Node Type"] = df[guid_col].map(self.node_type)
        return df

    def _node_name_map(self) -> Dict[str, str]:
        if self._node_names is not None:
            return self._node_names
        if "NODES" not in self._index_table.index:
            self._node_names = {}
            return self._node_names
        nodes = read_table(self._db_csv, "NODES", self._index_table)
        nodes["NodeGUID"] = nodes["NodeGUID"].apply(self._normalize_guid)
        nodes["NodeDesc"] = nodes["NodeDesc"].astype(str).str.strip('"')
        self._node_names = {
            guid: desc
            for guid, desc in zip(nodes["NodeGUID"], nodes["NodeDesc"])
            if guid
        }
        return self._node_names

    def _node_type_map(self) -> Dict[str, str]:
        if self._node_types is not None:
            return self._node_types
        if "NODES" not in self._index_table.index:
            self._node_types = {}
            return self._node_types
        nodes = read_table(self._db_csv, "NODES", self._index_table)
        nodes["NodeGUID"] = nodes["NodeGUID"].apply(self._normalize_guid)
        label_map = {0: "Unknown", 1: "HCA", 2: "Switch", 3: "Router"}
        def label(value):
            try:
                return label_map.get(int(value), str(value))
            except (TypeError, ValueError):
                return str(value) if value is not None else None
        nodes["NodeTypeLabel"] = nodes["NodeType"].apply(label)
        self._node_types = {
            guid: label
            for guid, label in zip(nodes["NodeGUID"], nodes["NodeTypeLabel"])
            if guid
        }
        return self._node_types

    def _neighbor_map(self) -> Dict[Tuple[str, int], str]:
        if self._port_neighbors is not None:
            return self._port_neighbors
        neighbors: Dict[Tuple[str, int], Tuple[str, Optional[int]]] = {}
        if "LINKS" not in self._index_table.index:
            self._port_neighbors = neighbors
            return neighbors
        links = read_table(self._db_csv, "LINKS", self._index_table)
        for _, row in links.iterrows():
            g1 = self._normalize_guid(row.get("NodeGuid1"))
            g2 = self._normalize_guid(row.get("NodeGuid2"))
            p1 = self._safe_port(row.get("PortNum1"))
            p2 = self._safe_port(row.get("PortNum2"))
            if g1 and g2 and p1 is not None:
                neighbors[(g1, p1)] = (g2, p2)
            if g1 and g2 and p2 is not None:
                neighbors[(g2, p2)] = (g1, p1)
        self._port_neighbors = neighbors
        return neighbors

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    @staticmethod
    def _normalize_guid(value: object) -> Optional[str]:
        """Normalize GUID format with validation."""
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "na":
            return None

        # Validate GUID format (hex string with optional 0x prefix)
        import re
        if text.lower().startswith("0x"):
            hex_part = text[2:]
            prefix = True
        else:
            hex_part = text
            prefix = False

        # Validate hex format
        if not re.match(r'^[0-9a-f]+$', hex_part.lower()):
            logger.warning(f"Invalid GUID format: {text}")
            return text.lower()

        # Validate length (typical GUID is 16 hex digits, max 32)
        if len(hex_part) > 32:
            logger.warning(f"GUID too long: {text}")
            return text.lower()

        try:
            if prefix:
                return hex(int(text, 16))
            elif text.isdigit():
                return hex(int(text))
        except (ValueError, OverflowError):
            logger.warning(f"Failed to normalize GUID: {text}")
        return text.lower()

    @staticmethod
    def _safe_port(value: object) -> Optional[int]:
        if value is None:
            return None
        try:
            if isinstance(value, str) and not value.strip():
                return None
            if isinstance(value, float) and math.isnan(value):
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None
