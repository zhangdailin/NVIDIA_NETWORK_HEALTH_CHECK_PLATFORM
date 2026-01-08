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

BER_TABLE_CANDIDATES = ["PM_BER", "EFF_BER", "PHY_DB16"]
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
        "SymbolBERLog10Value",
        "Log10 Symbol BER",
        "Log10 Effective BER",
        "Log10 Raw BER",
        "Symbol BER",
        "Effective BER",
        "Raw BER",
    ]

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._df: pd.DataFrame | None = None
        self._warnings_df: pd.DataFrame | None = None
        self._topology: TopologyLookup | None = None

    def clear_cache(self):
        """Clear cached DataFrames to free memory."""
        self._df = None
        self._warnings_df = None
        self._topology = None

    def run(self) -> BerAnalysis:
        df = self._load_dataframe()
        warnings_df = self._load_warnings_dataframe()
        self._annotate_symbol_ber(df)
        self._annotate_warning_rows(warnings_df)
        anomalies = self._build_anomalies(df, warnings_df)
        frames = []

        # 🆕 只添加异常数据 (critical或warning)
        if not df.empty and "SymbolBERSeverity" in df.columns:
            anomaly_df = df[df["SymbolBERSeverity"].isin(["critical", "warning"])]
            if not anomaly_df.empty:
                frames.append(anomaly_df)
                logger.info(f"BER: Filtered {len(df)} → {len(anomaly_df)} anomalies (removed {len(df)-len(anomaly_df)} normal ports)")

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
        """Remove redundant zeros from GUID. Can handle both dict/row and string."""
        # Handle when called with a string value directly (from Series.apply)
        if isinstance(row, str):
            guid = row
        # Handle when called with a dict/row object
        elif isinstance(row, dict) or hasattr(row, "get"):
            guid = str(row.get("NodeGUID", ""))
        else:
            guid = str(row)

        if guid.startswith("0x"):
            try:
                return hex(int(guid, 16))
            except (ValueError, OverflowError):
                logger.warning(f"Invalid hex GUID format: {guid}")
                return guid
        return guid

    def _process_mantissa_exponent_fields(self, df: pd.DataFrame) -> None:
        """Process BER fields, supporting both direct columns and mantissa/exponent pairs (field12-17)."""
        if "field12" in df.columns:
            # Table uses mantissa/exponent pairs (e.g. PHY_DB16 style)
            mappings = [
                ("field12", "field13", "Log10 Raw BER", "Raw BER"),
                ("field14", "field15", "Log10 Effective BER", "Effective BER"),
                ("field16", "field17", "Log10 Symbol BER", "Symbol BER"),
            ]
            for m_col, e_col, log_col, str_col in mappings:
                if m_col in df.columns and e_col in df.columns:
                    df[log_col] = df.apply(lambda row: self._me_to_log10(row[m_col], row[e_col]), axis=1)
                    df[str_col] = df.apply(lambda row: self._me_to_sci(row[m_col], row[e_col]), axis=1)
        else:
            # Standard table with direct BER columns (e.g. PM_BER)
            for col in ["Raw BER", "Effective BER", "Symbol BER"]:
                if col in df.columns:
                    df[f"Log10 {col}"] = df.apply(lambda row: self._log10(row, col), axis=1)
                    # Ensure we have a string representation
                    df[col] = df[col].apply(lambda v: f"{v:e}" if isinstance(v, (int, float)) and v > 0 else str(v))

    @staticmethod
    def _me_to_log10(m, e):
        """Convert mantissa/exponent pair to log10 value."""
        try:
            m_val = int(float(m))
            e_val = int(float(e))
            if m_val == 0:
                return -50.0
            return math.log10(abs(m_val)) - e_val
        except (ValueError, TypeError, OverflowError):
            return -50.0

    @staticmethod
    def _me_to_sci(m, e) -> str:
        """Convert mantissa/exponent to scientific notation string."""
        try:
            m_val = int(float(m))
            e_val = int(float(e))
            if m_val == 0:
                return "0e+00"
            log10_val = math.log10(abs(m_val)) - e_val
            exponent = int(math.floor(log10_val))
            mantissa = 10 ** (log10_val - exponent)
            return f"{mantissa:.1f}e{exponent:+03d}"
        except (ValueError, TypeError, OverflowError):
            return "N/A"

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
