"""BER analysis service."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

BER_TABLE_CANDIDATES = ["PM_BER", "EFF_BER"]
WARNINGS_TABLE = "WARNINGS_SYMBOL_BER_CHECK"
WARNING_SEVERITY = {
    "BER_THRESHOLD_EXCEEDED": "critical",
    "BER_NEAR_THRESHOLD": "warning",
    "BER_RS_FEC_EXCESSIVE_ERRORS": "critical",
    "BER_RS_FEC_HIGH_ERRORS": "warning",
    "BER_NO_THRESHOLD_IS_SUPPORTED": "info",
}


@dataclass
class BerAnalysis:
    data: List[dict]
    anomalies: pd.DataFrame


class BerService:
    """Parses BER table and computes severity similar to ib_analysis.ber."""

    DISPLAY_COLUMNS = [
        "NodeGUID",
        "Node Name",
        "Attached To",
        "PortNumber",
        "EventName",
        "Summary",
        "SymbolBERSeverity",
    ]

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._df: pd.DataFrame | None = None
        self._warnings_df: pd.DataFrame | None = None
        self._topology: TopologyLookup | None = None

    def run(self) -> BerAnalysis:
        df = self._load_dataframe()
        warnings_df = self._load_warnings_dataframe()
        self._annotate_symbol_ber(df)
        self._annotate_warning_rows(warnings_df)
        anomalies = self._build_anomalies(df, warnings_df)
        frames = []
        if not df.empty:
            frames.append(df)
        if warnings_df is not None and not warnings_df.empty:
            frames.append(warnings_df)
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            combined = self._topology_lookup().annotate_ports(combined, guid_col="NodeGUID", port_col="PortNumber")
            existing = [col for col in self.DISPLAY_COLUMNS if col in combined.columns]
            combined = combined[existing]
            records = combined.to_dict(orient="records")
        else:
            records = []
        return BerAnalysis(data=records, anomalies=anomalies)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        ber_table = self._pick_ber_table(index_table)
        if ber_table is None:
            logger.warning("No BER table (%s) found in %s", ", ".join(BER_TABLE_CANDIDATES), db_csv)
            self._df = pd.DataFrame()
            return self._df
        try:
            df = read_table(db_csv, ber_table, index_table)
        except KeyError:
            logger.warning("BER table %s missing from %s", ber_table, db_csv)
            self._df = pd.DataFrame()
            return self._df
        if df.empty:
            logger.warning("BER table %s empty in %s", ber_table, db_csv)
            self._df = pd.DataFrame()
            return self._df
        df.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber", "PortGuid": "PortGUID"}, inplace=True)
        df["NodeGUID"] = df.apply(self._remove_redundant_zero, axis=1)
        self._process_mantissa_exponent_fields(df)
        self._df = df
        return df

    def _load_warnings_dataframe(self) -> pd.DataFrame:
        if self._warnings_df is not None:
            return self._warnings_df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        if WARNINGS_TABLE not in index_table.index:
            self._warnings_df = pd.DataFrame()
            return self._warnings_df
        try:
            warnings_df = read_table(db_csv, WARNINGS_TABLE, index_table)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to read BER warnings table: %s", exc)
            self._warnings_df = pd.DataFrame()
            return self._warnings_df
        if warnings_df.empty:
            self._warnings_df = pd.DataFrame()
            return self._warnings_df
        warnings_df = warnings_df.rename(columns={"PortNum": "PortNumber"})
        warnings_df["NodeGUID"] = warnings_df.apply(self._remove_redundant_zero, axis=1)
        warnings_df["Summary"] = warnings_df["Summary"].astype(str).str.strip('"')
        self._warnings_df = warnings_df
        return self._warnings_df

    @staticmethod
    def _pick_ber_table(index_table: pd.DataFrame) -> Optional[str]:
        for candidate in BER_TABLE_CANDIDATES:
            if candidate in index_table.index:
                return candidate
        return None

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    @staticmethod
    def _remove_redundant_zero(row) -> str:
        guid = str(row.get("NodeGUID", ""))
        if guid.startswith("0x"):
            return hex(int(guid, 16))
        return guid

    def _process_mantissa_exponent_fields(self, df: pd.DataFrame) -> None:
        if "field12" not in df.columns:
            return
        for col in ["Raw BER", "Effective BER", "Symbol BER"]:
            df[f"Log10 {col}"] = df.apply(lambda row: self._log10(row, col), axis=1)

    @staticmethod
    def _log10(row, col):
        try:
            val = float(row[col])
            if val == 0.0:
                return -50.0
            return math.log10(val)
        except (ValueError, TypeError):
            return 0.0

    def _annotate_symbol_ber(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        log_series = pd.to_numeric(df.get("Log10 Symbol BER"), errors="coerce")
        df["SymbolBERLog10Value"] = log_series

        def to_value(log_value):
            if pd.isna(log_value):
                return None
            return math.pow(10, log_value)

        df["SymbolBERValue"] = log_series.apply(to_value)
        threshold_log = math.log10(1e-12)
        warning_log = math.log10(1e-15)

        def classify(log_value):
            if pd.isna(log_value):
                return "unknown"
            if log_value > threshold_log:
                return "critical"
            if log_value > warning_log:
                return "warning"
            return "normal"

        df["SymbolBERSeverity"] = log_series.apply(classify)
        df["SymbolBERThreshold"] = 1e-12

    def _annotate_warning_rows(self, warnings_df: pd.DataFrame | None) -> None:
        if warnings_df is None or warnings_df.empty:
            return
        severity = warnings_df["EventName"].map(lambda name: WARNING_SEVERITY.get(name, "info"))
        warnings_df["SymbolBERSeverity"] = severity
        warnings_df["SymbolBERLog10Value"] = None
        warnings_df["SymbolBERThreshold"] = None
        warnings_df["BerWarning"] = True

    def _build_anomalies(self, df: pd.DataFrame, warnings_df: pd.DataFrame | None) -> pd.DataFrame:
        severity_map = {"critical": 1.0, "warning": 0.5}
        frames = []
        if not df.empty and "SymbolBERSeverity" in df.columns:
            frames.append(df[IBH_ANOMALY_TBL_KEY + ["SymbolBERSeverity"]].copy())
        if warnings_df is not None and not warnings_df.empty:
            frames.append(warnings_df[IBH_ANOMALY_TBL_KEY + ["SymbolBERSeverity"]].copy())
        if not frames:
            return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)
        payload = pd.concat(frames, ignore_index=True)
        payload[str(AnomlyType.IBH_HIGH_SYMBOL_BER)] = payload["SymbolBERSeverity"].map(
            lambda sev: severity_map.get(sev, 0.0)
        )
        return payload[IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_HIGH_SYMBOL_BER)]]

    def _topology_lookup(self) -> TopologyLookup:
        if self._topology is None:
            self._topology = TopologyLookup(self.dataset_root)
        return self._topology
