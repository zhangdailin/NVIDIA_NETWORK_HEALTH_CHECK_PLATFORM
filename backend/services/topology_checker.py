"""Detects topology data quality issues such as duplicate GUIDs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .anomalies import (
    IBH_ANOMALY_AGG_COL,
    IBH_ANOMALY_AGG_WEIGHT,
    AnomlyType,
)
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup


@dataclass
class TopologyIssue:
    node_guid: str
    description: str
    count: int


class TopologyChecker:
    """Loads lightweight topology tables (NODES) and finds duplicates."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = Path(dataset_root)
        self._db_csv = self._find_db_csv()
        self._index = read_index_table(self._db_csv)
        self._nodes_df: pd.DataFrame | None = None
        self._topology = TopologyLookup(dataset_root)

    def duplicate_guid_issues(self) -> List[TopologyIssue]:
        df = self._nodes_table()
        if df.empty:
            return []
        duplicates = df.groupby("NodeGUID").size().reset_index(name="count")
        duplicates = duplicates[duplicates["count"] > 1]
        issues = []
        for _, row in duplicates.iterrows():
            guid = row["NodeGUID"]
            node_names = sorted(df[df["NodeGUID"] == guid]["NodeDesc"].unique())
            issues.append(
                TopologyIssue(
                    node_guid=guid,
                    description=f"Duplicate NodeGUID detected: {guid} ({', '.join(node_names)})",
                    count=int(row["count"]),
                )
            )
        return issues

    def duplicate_namedesc_issues(self) -> List[TopologyIssue]:
        df = self._nodes_table()
        if df.empty:
            return []
        duplicates = df.groupby("NodeDesc").size().reset_index(name="count")
        duplicates = duplicates[duplicates["count"] > 1]
        issues = []
        for _, row in duplicates.iterrows():
            desc = row["NodeDesc"]
            guids = sorted(df[df["NodeDesc"] == desc]["NodeGUID"].unique())
            issues.append(
                TopologyIssue(
                    node_guid=guids[0],
                    description=f"Duplicate Node Description '{desc}' across GUIDs {', '.join(guids)}",
                    count=int(row["count"]),
                )
            )
        return issues

    def to_issue_rows(self) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for issue in self.duplicate_guid_issues():
            rows.append(
                {
                    "NodeGUID": issue.node_guid,
                    "PortNumber": 0,
                    "Topology Issue": issue.description,
                    IBH_ANOMALY_AGG_COL: AnomlyType.IBH_DUPLICATE_GUID.value,
                    IBH_ANOMALY_AGG_WEIGHT: issue.count,
                }
            )
        for issue in self.duplicate_namedesc_issues():
            rows.append(
                {
                    "NodeGUID": issue.node_guid,
                    "PortNumber": 0,
                    "Topology Issue": issue.description,
                    IBH_ANOMALY_AGG_COL: AnomlyType.IBH_DUPLICATE_DESC.value,
                    IBH_ANOMALY_AGG_WEIGHT: issue.count,
                }
            )
        return rows

    def _nodes_table(self) -> pd.DataFrame:
        if self._nodes_df is not None:
            return self._nodes_df
        if "NODES" not in self._index.index:
            self._nodes_df = pd.DataFrame()
            return self._nodes_df
        df = read_table(self._db_csv, "NODES", self._index)
        df.rename(columns={"NodeGuid": "NodeGUID"}, inplace=True)
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        df["NodeDesc"] = df["NodeDesc"].astype(str).str.strip('"')
        self._nodes_df = df
        return self._nodes_df

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

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
            except ValueError:
                return text.lower()
        try:
            if text.isdigit():
                return hex(int(text))
        except ValueError:
            return text
        return text.lower()
