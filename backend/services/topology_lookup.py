"""Lightweight topology lookup utilities for ibdiagnet datasets."""

from __future__ import annotations

import logging
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
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
        self._nodes_df_cache: Optional[pd.DataFrame] = None

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
            # Optimized: Use vectorized merge instead of apply(axis=1)
            neighbor_map = self._neighbor_map()
            if neighbor_map:
                # Normalize GUIDs for lookup
                normalized_guids = df[guid_col].apply(self._normalize_guid)
                ports = df[port_col].apply(self._safe_port)

                # Vectorized lookup using tuple keys
                attached_guids = []
                attached_ports = []
                for guid, port in zip(normalized_guids, ports):
                    if guid is not None and port is not None:
                        endpoint = neighbor_map.get((guid, port))
                        if endpoint:
                            attached_guids.append(endpoint[0])
                            attached_ports.append(endpoint[1])
                        else:
                            attached_guids.append(None)
                            attached_ports.append(None)
                    else:
                        attached_guids.append(None)
                        attached_ports.append(None)

                df["Attached To GUID"] = attached_guids
                df["Attached To Port"] = attached_ports
            else:
                df["Attached To GUID"] = None
                df["Attached To Port"] = None

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

    def _load_nodes_df(self) -> Optional[pd.DataFrame]:
        """Load NODES table once and cache it."""
        if self._nodes_df_cache is not None:
            return self._nodes_df_cache
        if "NODES" not in self._index_table.index:
            return None
        nodes = read_table(self._db_csv, "NODES", self._index_table)
        # Vectorized GUID normalization
        nodes["NodeGUID"] = self._vectorized_normalize_guid(nodes["NodeGUID"])
        self._nodes_df_cache = nodes
        return nodes

    def _node_name_map(self) -> Dict[str, str]:
        if self._node_names is not None:
            return self._node_names
        nodes = self._load_nodes_df()
        if nodes is None:
            self._node_names = {}
            return self._node_names
        nodes_copy = nodes.copy()
        nodes_copy["NodeDesc"] = nodes_copy["NodeDesc"].astype(str).str.strip('"')
        self._node_names = {
            guid: desc
            for guid, desc in zip(nodes_copy["NodeGUID"], nodes_copy["NodeDesc"])
            if guid
        }
        return self._node_names

    def _node_type_map(self) -> Dict[str, str]:
        if self._node_types is not None:
            return self._node_types
        nodes = self._load_nodes_df()
        if nodes is None:
            self._node_types = {}
            return self._node_types
        label_map = {0: "Unknown", 1: "HCA", 2: "Switch", 3: "Router"}
        # Vectorized label mapping
        nodes_copy = nodes.copy()
        nodes_copy["NodeTypeLabel"] = nodes_copy["NodeType"].apply(
            lambda v: label_map.get(int(v), str(v)) if pd.notna(v) else None
        )
        self._node_types = {
            guid: label
            for guid, label in zip(nodes_copy["NodeGUID"], nodes_copy["NodeTypeLabel"])
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

        # Vectorized processing instead of iterrows
        links["g1"] = self._vectorized_normalize_guid(links.get("NodeGuid1"))
        links["g2"] = self._vectorized_normalize_guid(links.get("NodeGuid2"))
        links["p1"] = links.get("PortNum1").apply(self._safe_port)
        links["p2"] = links.get("PortNum2").apply(self._safe_port)

        # Build neighbor map from vectorized data
        for g1, g2, p1, p2 in zip(links["g1"], links["g2"], links["p1"], links["p2"]):
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
    def _vectorized_normalize_guid(series: pd.Series) -> pd.Series:
        """Vectorized GUID normalization for better performance."""
        if series is None or series.empty:
            return series

        def normalize_single(value):
            if value is None or pd.isna(value):
                return None
            text = str(value).strip()
            if not text or text.lower() == "na":
                return None

            if text.lower().startswith("0x"):
                hex_part = text[2:]
                prefix = True
            else:
                hex_part = text
                prefix = False

            # Quick validation
            if len(hex_part) > 32:
                return text.lower()

            try:
                if prefix:
                    return hex(int(text, 16))
                elif text.isdigit():
                    return hex(int(text))
            except (ValueError, OverflowError):
                pass
            return text.lower()

        return series.apply(normalize_single)

    @staticmethod
    def _normalize_guid(value: object) -> Optional[str]:
        """Normalize GUID format with validation."""
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "na":
            return None

        if text.lower().startswith("0x"):
            hex_part = text[2:]
            prefix = True
        else:
            hex_part = text
            prefix = False

        # Validate length (typical GUID is 16 hex digits, max 32)
        if len(hex_part) > 32:
            return text.lower()

        try:
            if prefix:
                return hex(int(text, 16))
            elif text.isdigit():
                return hex(int(text))
        except (ValueError, OverflowError):
            pass
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
