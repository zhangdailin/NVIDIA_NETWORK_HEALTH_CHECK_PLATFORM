"""Minimal reader for ibdiagnet *.db_csv datasets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

import pandas as pd

_INDEX_CACHE: Dict[Path, pd.DataFrame] = {}


def read_index_table(file_name: str | Path) -> pd.DataFrame:
    """
    Parse the START_/END_ markers inside an ibdiagnet *.db_csv file.

    This replicates the functionality we previously imported from ib_analysis.
    """
    path = Path(file_name)
    cached = _INDEX_CACHE.get(path)
    if cached is not None:
        return cached

    try:
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise FileNotFoundError(f"Cannot open {file_name}") from exc

    matches = re.findall(r"(\d+):(START|END)_([^\n]*)", _annotate_lines(text))
    if not matches:
        raise ValueError(f"Index markers not found in {file_name}")

    df = (
        pd.DataFrame(matches, columns=["line", "edge", "name"])
        .drop_duplicates(subset=["name", "edge"], keep="last")
        .set_index(["name", "edge"])
        .unstack(-1)["line"]
    )
    df.columns.name = None
    df = df[["START", "END"]].astype(float)
    df["LINES"] = df["END"] - df["START"] - 2
    _INDEX_CACHE[path] = df
    return df


def read_table(file_name: str | Path, table_name: str, index_table: pd.DataFrame) -> pd.DataFrame:
    """
    Slice a specific table from the consolidated ibdiagnet output.
    """
    start, end = index_table.loc[table_name][["START", "END"]]
    return pd.read_csv(
        file_name,
        skiprows=int(start) - 1,
        nrows=int(end - start) - 2,
        encoding="latin-1",
        header=1,
        skipinitialspace=True,
        low_memory=False,
        quotechar="\x07",
        na_values=["N/A", "ERR"],
    )


def _annotate_lines(text: str) -> str:
    lines = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if line.startswith(("START_", "END_")):
            lines.append(f"{idx}:{line}\n")
    return "".join(lines)
