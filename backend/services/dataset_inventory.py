"""Shared dataset inventory/cache for ibdiagnet extracts."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup


class DatasetInventory:
    """Caches index tables, db_csv path, and topology lookup for services."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._db_csv: Optional[Path] = None
        self._index_table: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    @property
    def db_csv(self) -> Path:
        if self._db_csv is None:
            matches = sorted(self.dataset_root.glob("*.db_csv"))
            if not matches:
                raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
            self._db_csv = matches[0]
        return self._db_csv

    @property
    def index_table(self) -> pd.DataFrame:
        if self._index_table is None:
            self._index_table = read_index_table(self.db_csv)
        return self._index_table

    def table_exists(self, table_name: str) -> bool:
        return table_name in self.index_table.index

    def read_table(self, table_name: str) -> pd.DataFrame:
        if not self.table_exists(table_name):
            return pd.DataFrame()
        return read_table(self.db_csv, table_name, self.index_table)

    @property
    def topology(self) -> TopologyLookup:
        if self._topology is None:
            self._topology = TopologyLookup(self.dataset_root)
        return self._topology
