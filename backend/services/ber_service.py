"""BER analysis service."""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

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
        "PortNumber",
        "Node Name",
        "Attached To",
        "Raw BER",
        "Effective BER",
        "Symbol BER",
        "IBH Anomaly",
        "EventName",
        "Summary",
        "SymbolBERSeverity",
        "SymbolBERLog10Value",
        "Log10 Symbol BER",
        "Log10 Effective BER",
        "Log10 Raw BER",
    ]

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._df: pd.DataFrame | None = None
        self._warnings_df: pd.DataFrame | None = None
        self._topology: TopologyLookup | None = None
        self._pm_counters_df: pd.DataFrame | None = None
        self._index_table: pd.DataFrame | None = None

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
        if not df.empty:
            frames.append(df)
        if warnings_df is not None and not warnings_df.empty:
            frames.append(warnings_df)

        records: List[dict] = []
        if frames:
            combined = pd.concat(frames, ignore_index=True, sort=False)
            combined = self._topology_lookup().annotate_ports(combined, guid_col="NodeGUID", port_col="PortNumber")

            severity_col = combined.get("SymbolBERSeverity")
            if severity_col is not None:
                combined["IBH Anomaly"] = severity_col.astype(str).str.lower().apply(
                    lambda sev: AnomlyType.IBH_HIGH_SYMBOL_BER.value if sev in {"critical", "warning"} else ""
                )
            else:
                combined["IBH Anomaly"] = ""

            for column in self.DISPLAY_COLUMNS:
                if column not in combined.columns:
                    combined[column] = None

            combined = combined[self.DISPLAY_COLUMNS]
            records = combined.to_dict(orient="records")
        return BerAnalysis(data=records, anomalies=anomalies)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df

        net_dump_df = self._parse_net_dump_file()
        if not net_dump_df.empty:
            net_dump_df["RawBERValue"] = net_dump_df["Raw BER"].apply(self._parse_ber_string)
            net_dump_df["EffectiveBERValue"] = net_dump_df["Effective BER"].apply(self._parse_ber_string)
            net_dump_df["SymbolBERValue"] = net_dump_df["Symbol BER"].apply(self._parse_ber_string)
            net_dump_df["Log10 Raw BER"] = net_dump_df["RawBERValue"].apply(self._safe_log10)
            net_dump_df["Log10 Effective BER"] = net_dump_df["EffectiveBERValue"].apply(self._safe_log10)
            net_dump_df["Log10 Symbol BER"] = net_dump_df["SymbolBERValue"].apply(self._safe_log10)
            net_dump_df = net_dump_df.dropna(subset=["RawBERValue", "EffectiveBERValue", "SymbolBERValue"], how="all")
            net_dump_df = self._merge_pm_counters(net_dump_df)
            self._df = net_dump_df
            return self._df

        logger.warning(
            "No ibdiagnet2.net_dump_ext data found under %s; BER table will be empty",
            self.dataset_root
        )
        self._df = pd.DataFrame()
        return self._df

    def _load_warnings_dataframe(self) -> pd.DataFrame:
        if self._warnings_df is not None:
            return self._warnings_df
        db_csv = self._find_db_csv()
        index_table = self._get_index_table()
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

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    def _get_index_table(self) -> pd.DataFrame:
        if self._index_table is None:
            db_csv = self._find_db_csv()
            self._index_table = read_index_table(db_csv)
        return self._index_table

    def _load_pm_counters(self) -> pd.DataFrame:
        if self._pm_counters_df is not None:
            return self._pm_counters_df
        try:
            db_csv = self._find_db_csv()
        except FileNotFoundError:
            self._pm_counters_df = pd.DataFrame()
            return self._pm_counters_df

        index_table = self._get_index_table()
        pm_df = pd.DataFrame()
        for table in ("PERFQUERY_EXT_ERRORS", "PM"):
            if table in index_table.index:
                try:
                    pm_df = read_table(db_csv, table, index_table)
                    if not pm_df.empty:
                        break
                except Exception:  # pragma: no cover - corrupt table should not crash
                    continue
        if pm_df.empty:
            self._pm_counters_df = pd.DataFrame()
            return self._pm_counters_df

        rename_map = {
            "NodeGuid": "NodeGUID",
            "PortNum": "PortNumber",
        }
        pm_df = pm_df.rename(columns=rename_map)
        keep_cols = ["NodeGUID", "PortNumber"]
        for column in ("SymbolErrorCounter", "SymbolErrorCounterExt"):
            if column in pm_df.columns:
                keep_cols.append(column)
        pm_df = pm_df[keep_cols].drop_duplicates(subset=["NodeGUID", "PortNumber"], keep="last")
        pm_df["NodeGUID"] = pm_df["NodeGUID"].astype(str).apply(self._normalize_guid_text)
        self._pm_counters_df = pm_df
        return self._pm_counters_df

    def _merge_pm_counters(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        pm_df = self._load_pm_counters()
        if pm_df.empty:
            df["SymbolErrorCounter"] = 0
            df["SymbolErrorCounterExt"] = 0
            return df
        merged = df.merge(pm_df, how="left", on=["NodeGUID", "PortNumber"])
        for column in ("SymbolErrorCounter", "SymbolErrorCounterExt"):
            merged[column] = pd.to_numeric(merged.get(column), errors="coerce").fillna(0).astype(int)
        return merged

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

    def _annotate_symbol_ber(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        log_series = df.get("SymbolBERLog10Value")
        if log_series is None:
            log_series = pd.to_numeric(df.get("Log10 Symbol BER"), errors="coerce")
            df["SymbolBERLog10Value"] = log_series

        def to_value(log_value):
            if pd.isna(log_value):
                return None
            return math.pow(10, log_value)

        df["SymbolBERValue"] = log_series.apply(to_value)
        critical_threshold = float(os.environ.get("IBA_BER_TH", "1e-12"))
        warning_threshold = float(os.environ.get("IBA_BER_WARN_TH", "1e-15"))
        threshold_log = math.log10(critical_threshold)
        warning_log = math.log10(min(critical_threshold, warning_threshold))

        def classify(log_value):
            if pd.isna(log_value):
                return "unknown"
            if log_value > threshold_log:
                return "critical"
            if log_value > warning_log:
                return "warning"
            return "normal"

        df["SymbolBERSeverity"] = log_series.apply(classify)
        df["SymbolBERThreshold"] = critical_threshold

        self._annotate_raw_effective_ber(df, threshold_log, warning_log)

    def _annotate_raw_effective_ber(self, df: pd.DataFrame, critical_log: float, warning_log: float) -> None:
        if df.empty:
            return

        fb_min = int(os.environ.get("IBA_BER_FALLBACK_MIN", "1024"))
        min_symbol_log = float(os.environ.get("IBA_BER_SYMBOL_VALID_MIN_LOG10", "-60"))
        symbol_err = pd.to_numeric(df.get("Symbol Err"), errors="coerce").fillna(0).astype(int)
        effective_err = pd.to_numeric(df.get("Effective Err"), errors="coerce").fillna(0).astype(int)
        pm_symbol = pd.to_numeric(df.get("SymbolErrorCounter"), errors="coerce").fillna(0).astype(int)
        pm_symbol_ext = pd.to_numeric(df.get("SymbolErrorCounterExt"), errors="coerce").fillna(0).astype(int)
        df["Symbol Err"] = symbol_err
        df["Effective Err"] = effective_err
        df["_TotalSymbolErrors"] = symbol_err + pm_symbol + pm_symbol_ext

        def log_meets(value, threshold):
            return value is not None and pd.notna(value) and float(value) >= threshold

        def classify_row(row):
            severity = row.get("SymbolBERSeverity", "normal") or "normal"
            total_errors = int(row.get("_TotalSymbolErrors", 0) or 0)
            fallback_errors = int(row.get("Effective Err", 0) or 0)
            err_gate = total_errors if total_errors > 0 else fallback_errors
            if err_gate < fb_min:
                return severity

            sym_log = row.get("Log10 Symbol BER")
            eff_log = row.get("Log10 Effective BER")
            raw_log = row.get("Log10 Raw BER")

            symbol_log_valid = sym_log is not None and pd.notna(sym_log) and float(sym_log) > min_symbol_log

            if symbol_log_valid:
                if log_meets(sym_log, critical_log):
                    return self._max_severity(severity, "critical")
                if log_meets(sym_log, warning_log):
                    severity = self._max_severity(severity, "warning")
            else:
                if log_meets(eff_log, critical_log):
                    return self._max_severity(severity, "critical")
                if log_meets(eff_log, warning_log):
                    severity = self._max_severity(severity, "warning")
                elif log_meets(raw_log, critical_log):
                    return self._max_severity(severity, "critical")
                elif log_meets(raw_log, warning_log):
                    severity = self._max_severity(severity, "warning")
            return severity

        df["SymbolBERSeverity"] = df.apply(classify_row, axis=1)
        df.drop(columns=["_TotalSymbolErrors"], inplace=True, errors="ignore")

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

    def _parse_net_dump_file(self) -> pd.DataFrame:
        """Parse ibdiagnet2.net_dump_ext for BER data if available."""
        net_dump_files = sorted(self.dataset_root.glob("*net_dump_ext"))
        if not net_dump_files:
            return pd.DataFrame()

        records: List[Dict[str, object]] = []
        for file_path in net_dump_files:
            try:
                with open(file_path, "r", encoding="latin-1") as handle:
                    for line in handle:
                        stripped = line.strip()
                        if not stripped or stripped.startswith("#"):
                            continue
                        if not (stripped.startswith("CA") or stripped.startswith("SW")):
                            continue
                        parts = [part.strip() for part in stripped.split(":")]
                        if len(parts) < 15:
                            continue
                        try:
                            port_number = int(parts[2])
                        except ValueError:
                            continue
                        try:
                            raw = parts[12]
                            eff = parts[13]
                            sym = parts[14]
                            sym_err = parts[15] if len(parts) > 15 else "0"
                            eff_err = parts[16] if len(parts) > 16 else "0"
                        except IndexError:
                            continue
                        node_guid = self._normalize_guid_text(parts[3])
                        node_name = parts[17].strip('"') if len(parts) > 17 else parts[3]
                        records.append(
                            {
                                "NodeGUID": node_guid,
                                "PortNumber": port_number,
                                "Node Name": node_name,
                                "Attached To": parts[9],
                                "Raw BER": raw,
                                "Effective BER": eff,
                                "Symbol BER": sym,
                                "Symbol Err": sym_err,
                                "Effective Err": eff_err,
                            }
                        )
            except OSError:
                continue

        return pd.DataFrame(records)

    @staticmethod
    def _normalize_guid_text(value: str) -> str:
        text = value.strip()
        if text.lower().startswith("0x"):
            return text.lower()
        try:
            int(text, 16)
            return f"0x{text.lower()}"
        except ValueError:
            return text

    @staticmethod
    def _parse_ber_string(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            text = str(value).strip()
            if not text or text.lower() == "na":
                return None
            return float(text)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_log10(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if value <= 0:
            return None
        return math.log10(value)

    @staticmethod
    def _format_ber_value(value: object) -> str:
        """Format BER values identically to legacy IB analysis output."""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if math.isnan(numeric) or math.isinf(numeric):
            return "N/A"
        if numeric == 0:
            return "0.00E+00"
        if numeric < 0:
            return "N/A"
        exponent = int(math.floor(math.log10(numeric)))
        mantissa = numeric / math.pow(10, exponent)
        return f"{mantissa:.2f}E{exponent:+03d}"

    @staticmethod
    def _max_severity(current: str, candidate: str) -> str:
        order = {"unknown": 0, "normal": 1, "warning": 2, "critical": 3}
        current = current or "normal"
        candidate = candidate or "normal"
        return candidate if order.get(candidate, 0) >= order.get(current, 0) else current
