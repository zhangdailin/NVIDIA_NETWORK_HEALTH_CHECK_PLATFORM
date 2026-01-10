"""BER analysis service."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
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
SYMBOL_BER_SENTINEL_TEXT = "1.50E-254"
SYMBOL_BER_SENTINEL_VALUE = 1.5e-254


@dataclass
class BerAnalysis:
    data: List[dict]
    anomalies: pd.DataFrame


class BerService:
    """Parses BER table and computes severity similar to ib_analysis.ber."""

    DISPLAY_COLUMNS = [
        "NodeGUID",
        "LID",
        "Peer LID",
        "PortNumber",
        "Node Name",
        "Attached To",
        "Raw BER",
        "Effective BER",
        "Symbol BER",
        "Symbol Err",
        "Effective Err",
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
        self._phy_db16_df: pd.DataFrame | None = None

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
            # Filter out empty or all-NA dataframes to avoid FutureWarning
            non_empty_frames = [f for f in frames if not f.empty and not f.isna().all().all()]
            if not non_empty_frames:
                return []
            combined = pd.concat(non_empty_frames, ignore_index=True, sort=False)
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
        phy_df = self._load_phy_db16_dataframe()
        combined_df = self._combine_ber_sources(net_dump_df, phy_df)

        if not combined_df.empty:
            combined_df = self._ensure_numeric_ber_columns(combined_df)
            combined_df = combined_df.dropna(
                subset=["RawBERValue", "EffectiveBERValue", "SymbolBERValue"],
                how="all"
            )
            combined_df = self._merge_pm_counters(combined_df)
            self._df = combined_df
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
        candidate_tables = ("PM_DELTA", "PM_INFO", "PERFQUERY_EXT_ERRORS", "PM")
        for table in candidate_tables:
            if table not in index_table.index:
                continue
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
        required_cols = {"NodeGUID", "PortNumber"}
        if not required_cols.issubset(pm_df.columns):
            self._pm_counters_df = pd.DataFrame()
            return self._pm_counters_df

        keep_cols = ["NodeGUID", "PortNumber"]
        has_symbol_counter = False
        for column in ("SymbolErrorCounter", "SymbolErrorCounterExt"):
            if column in pm_df.columns:
                keep_cols.append(column)
                has_symbol_counter = True
        if not has_symbol_counter:
            self._pm_counters_df = pd.DataFrame()
            return self._pm_counters_df

        pm_df = (
            pm_df[keep_cols]
            .drop_duplicates(subset=["NodeGUID", "PortNumber"], keep="last")
            .copy()
        )
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

        # Use vectorized operations instead of apply for better performance
        for column in ("SymbolErrorCounter", "SymbolErrorCounterExt"):
            if column in merged.columns:
                merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).clip(lower=0).astype("int64")
            else:
                merged[column] = 0

        if "Symbol Err" not in merged.columns:
            merged["Symbol Err"] = 0
        merged["Symbol Err"] = pd.to_numeric(merged["Symbol Err"], errors="coerce").fillna(0).astype("int64")
        return merged

    @staticmethod
    @lru_cache(maxsize=10000)
    def _cached_remove_redundant_zero(guid: str) -> str:
        """Cached version of _remove_redundant_zero to handle repeated values."""
        if guid.startswith("0x"):
            try:
                return hex(int(guid, 16))
            except (ValueError, OverflowError):
                logger.warning(f"Invalid hex GUID format: {guid}")
                return guid
        return guid

    @staticmethod
    def _remove_redundant_zero(row) -> str:
        """Remove redundant zeros from GUID. Can handle both dict/row and string."""
        # Handle when called with a string value directly (from Series.apply)
        if isinstance(row, str):
            return BerService._cached_remove_redundant_zero(row)
        # Handle when called with a dict/row object
        elif isinstance(row, dict) or hasattr(row, "get"):
            guid = str(row.get("NodeGUID", ""))
            return BerService._cached_remove_redundant_zero(guid)
        else:
            guid = str(row)
            return BerService._cached_remove_redundant_zero(guid)

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
        df["SymbolBERThreshold"] = SYMBOL_BER_SENTINEL_VALUE

        def requires_warning(row: pd.Series) -> bool:
            text_value = str(row.get("Symbol BER", "") or "").strip()
            numeric_value: Optional[float] = None
            if text_value:
                try:
                    numeric_value = float(text_value)
                except (TypeError, ValueError):
                    numeric_value = None
                if numeric_value is None:
                    return text_value.upper() != SYMBOL_BER_SENTINEL_TEXT
            if numeric_value is None:
                numeric_value = row.get("SymbolBERValue")
            if numeric_value is None or pd.isna(numeric_value):
                return False
            return not math.isclose(
                numeric_value,
                SYMBOL_BER_SENTINEL_VALUE,
                rel_tol=0.0,
                abs_tol=1e-320,
            )

        df["SymbolBERSeverity"] = df.apply(
            lambda row: "warning" if requires_warning(row) else "normal",
            axis=1,
        )

        self._annotate_raw_effective_ber(df)

    def _annotate_raw_effective_ber(self, df: pd.DataFrame) -> None:
        if df.empty:
            return

        symbol_err = (
            pd.to_numeric(df.get("Symbol Err"), errors="coerce").fillna(0).astype("int64")
        )
        effective_err = (
            pd.to_numeric(df.get("Effective Err"), errors="coerce").fillna(0).astype("int64")
        )
        df["Symbol Err"] = symbol_err
        df["Effective Err"] = effective_err

        def classify_row(row):
            severity = row.get("SymbolBERSeverity", "normal") or "normal"
            symbol_count = int(row.get("Symbol Err", 0) or 0)
            if symbol_count > 0:
                return self._max_severity(severity, "critical")
            if row.get("BerWarning"):
                return self._max_severity(severity, "warning")
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
                        lid_value = self._extract_numeric_token(parts[4])
                        peer_lid_value = self._extract_numeric_token(parts[9])
                        records.append(
                            {
                                "NodeGUID": node_guid,
                                "PortNumber": port_number,
                                "Node Name": node_name,
                                "Attached To": parts[9],
                                "LID": lid_value,
                                "Peer LID": peer_lid_value,
                                "Raw BER": raw,
                                "Effective BER": eff,
                                "Symbol BER": sym,
                                "Symbol Err": self._parse_int_token(sym_err),
                                "Effective Err": self._parse_int_token(eff_err),
                            }
                        )
            except OSError:
                continue

        return pd.DataFrame(records)

    def _load_phy_db16_dataframe(self) -> pd.DataFrame:
        if self._phy_db16_df is not None:
            return self._phy_db16_df

        try:
            index_table = self._get_index_table()
        except FileNotFoundError:
            self._phy_db16_df = pd.DataFrame()
            return self._phy_db16_df

        if "PHY_DB16" not in index_table.index:
            self._phy_db16_df = pd.DataFrame()
            return self._phy_db16_df

        try:
            phy_df = read_table(self._find_db_csv(), "PHY_DB16", index_table)
        except Exception as exc:  # pragma: no cover - corrupt dataset
            logger.warning("Failed to read PHY_DB16 table: %s", exc)
            self._phy_db16_df = pd.DataFrame()
            return self._phy_db16_df

        if phy_df.empty:
            self._phy_db16_df = pd.DataFrame()
            return self._phy_db16_df

        phy_df = phy_df.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber"})
        phy_df["NodeGUID"] = phy_df.apply(self._remove_redundant_zero, axis=1)
        phy_df["PortNumber"] = pd.to_numeric(phy_df["PortNumber"], errors="coerce")
        phy_df = phy_df.dropna(subset=["NodeGUID", "PortNumber"])

        records: List[Dict[str, object]] = []
        mappings = [
            ("Raw BER", "RawBERValue", "Log10 Raw BER", "field12", "field13"),
            ("Effective BER", "EffectiveBERValue", "Log10 Effective BER", "field14", "field15"),
            ("Symbol BER", "SymbolBERValue", "Log10 Symbol BER", "field16", "field17"),
        ]

        for _, row in phy_df.iterrows():
            node_guid = row["NodeGUID"]
            port_number = int(row["PortNumber"])
            payload = {"NodeGUID": node_guid, "PortNumber": port_number}
            for string_col, value_col, log_col, mantissa_col, exponent_col in mappings:
                mantissa = row.get(mantissa_col)
                exponent = row.get(exponent_col)
                value = self._mantissa_exponent_to_value(mantissa, exponent)
                payload[value_col] = value
                if value is not None:
                    payload[string_col] = self._format_ber_value(value)
                    payload[log_col] = self._safe_log10(value)
            payload["SymbolBERLog10Value"] = payload.get("Log10 Symbol BER")
            records.append(payload)

        if not records:
            self._phy_db16_df = pd.DataFrame()
            return self._phy_db16_df

        self._phy_db16_df = pd.DataFrame(records)
        return self._phy_db16_df

    def _combine_ber_sources(self, net_dump_df: pd.DataFrame, phy_df: pd.DataFrame) -> pd.DataFrame:
        if net_dump_df is None or net_dump_df.empty:
            if phy_df is None:
                return pd.DataFrame()
            df = phy_df.copy()
            if "Symbol Err" not in df.columns:
                df["Symbol Err"] = 0
            if "Effective Err" not in df.columns:
                df["Effective Err"] = 0
            return df
        if phy_df is None or phy_df.empty:
            return net_dump_df

        net = net_dump_df.set_index(["NodeGUID", "PortNumber"])
        phy = phy_df.set_index(["NodeGUID", "PortNumber"])
        combined_index = net.index.union(phy.index)
        net = net.reindex(combined_index)
        phy = phy.reindex(combined_index)
        merged = net.copy()

        for column in phy.columns:
            if column not in merged.columns:
                merged[column] = None

        override_columns = [
            "Raw BER",
            "Effective BER",
            "Symbol BER",
            "RawBERValue",
            "EffectiveBERValue",
            "SymbolBERValue",
            "Log10 Raw BER",
            "Log10 Effective BER",
            "Log10 Symbol BER",
            "SymbolBERLog10Value",
        ]
        for column in override_columns:
            if column in phy.columns:
                merged[column] = phy[column].combine_first(merged[column])

        merged = merged.reset_index()
        for column in ("Symbol Err", "Effective Err"):
            if column not in merged.columns:
                merged[column] = 0
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype(int)
        for column in ("LID", "Peer LID"):
            if column not in merged.columns:
                merged[column] = None
        return merged

    def _ensure_numeric_ber_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        column_map = [
            ("Raw BER", "RawBERValue", "Log10 Raw BER"),
            ("Effective BER", "EffectiveBERValue", "Log10 Effective BER"),
            ("Symbol BER", "SymbolBERValue", "Log10 Symbol BER"),
        ]
        for string_col, value_col, log_col in column_map:
            if string_col not in df.columns:
                df[string_col] = None
            existing_values = pd.to_numeric(df.get(value_col), errors="coerce")
            needs_recalc = existing_values.isna()
            if needs_recalc.any():
                parsed = df.loc[needs_recalc, string_col].apply(self._parse_ber_string)
                existing_values.loc[needs_recalc] = parsed
            df[value_col] = existing_values
            df[log_col] = df[value_col].apply(self._safe_log10)

        if "SymbolBERLog10Value" not in df.columns:
            df["SymbolBERLog10Value"] = df["Log10 Symbol BER"]
        else:
            mask = df["SymbolBERLog10Value"].isna()
            df.loc[mask, "SymbolBERLog10Value"] = df.loc[mask, "Log10 Symbol BER"]
        return df

    @staticmethod
    def _extract_numeric_token(value: object) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        token = text.split()[0]
        return token or None

    @staticmethod
    def _parse_int_token(value: object) -> int:
        token = BerService._extract_numeric_token(value)
        if token is None:
            return 0
        try:
            if token.lower().startswith("0x"):
                return int(token, 16)
            return int(float(token))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    @lru_cache(maxsize=10000)
    def _cached_normalize_guid_text(value: str) -> str:
        """Cached version of _normalize_guid_text."""
        text = value.strip()
        if text.lower().startswith("0x"):
            return text.lower()
        try:
            int(text, 16)
            return f"0x{text.lower()}"
        except ValueError:
            return text

    @staticmethod
    def _normalize_guid_text(value: str) -> str:
        return BerService._cached_normalize_guid_text(value)

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
    def _mantissa_exponent_to_value(mantissa: object, exponent: object) -> Optional[float]:
        try:
            mantissa_value = float(mantissa)
            exponent_value = float(exponent)
        except (TypeError, ValueError):
            return None
        if mantissa_value == 0:
            return None
        # Some PHY_DB16 rows store placeholder exponents in the billions when the value is absent.
        # Treat anything wildly out of range as missing so we can fall back to net_dump_ext numbers.
        if exponent_value > 1000:
            return None
        try:
            return mantissa_value * math.pow(10.0, -exponent_value)
        except OverflowError:
            return None

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
