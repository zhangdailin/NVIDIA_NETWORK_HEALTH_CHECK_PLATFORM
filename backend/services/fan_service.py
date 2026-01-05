"""Switch chassis fan health service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup


@dataclass
class FanAnalysis:
    data: List[Dict[str, object]]
    anomalies: pd.DataFrame


DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",
    "SensorIndex",
    "PortNumber",
    "FanSpeed",
    "MinSpeed",
    "MaxSpeed",
    "FanStatus",
    "FanAlert",
    "FansUnderLimit",
    "FansOverLimit",
]


class FanService:
    """Loads fan alert/speed/threshold tables and reports anomalies."""

    ALERT_TABLE = "FANS_ALERT"
    SPEED_TABLE = "FANS_SPEED"
    THRESHOLD_TABLE = "FANS_THRESHOLDS"

    def __init__(self, dataset_root: Path):
        self.dataset_root = Path(dataset_root)
        self._db_csv = self._find_db_csv()
        self._index = read_index_table(self._db_csv)
        self._alerts: Optional[pd.DataFrame] = None
        self._speeds: Optional[pd.DataFrame] = None
        self._thresholds: Optional[pd.DataFrame] = None
        self._df: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> FanAnalysis:
        df = self._load_dataframe()
        anomalies = self._build_anomalies(df)
        display_df = self._decorate_dataframe(df)
        records = display_df.to_dict(orient="records") if not display_df.empty else []
        return FanAnalysis(data=records, anomalies=anomalies)

    def data(self) -> List[Dict[str, object]]:
        display_df = self._decorate_dataframe(self._load_dataframe())
        if display_df.empty:
            return []
        return display_df.to_dict(orient="records")

    def anomalies(self) -> pd.DataFrame:
        df = self._load_dataframe()
        return self._build_anomalies(df)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        merged = self._merged()
        if merged.empty:
            self._df = pd.DataFrame(columns=["NodeGUID", "SensorIndex"])
            return self._df
        merged["SensorIndex"] = pd.to_numeric(merged.get("SensorIndex"), errors="coerce")
        merged["PortNumber"] = merged["SensorIndex"].apply(
            lambda value: int(value) if pd.notna(value) else 0
        )
        merged["FanAlert"] = merged.apply(self._evaluate_fan, axis=1)
        self._df = merged
        return self._df

    def _decorate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        decorated = df.copy()
        decorated = self._topology_lookup().annotate_nodes(decorated, guid_col="NodeGUID")
        decorated["FanStatus"] = decorated["FanAlert"].apply(
            lambda val: "Alert" if pd.notna(val) and float(val) > 0 else "OK"
        )
        existing = [col for col in DISPLAY_COLUMNS if col in decorated.columns]
        return decorated[existing]

    def _build_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)
        payload = df[["NodeGUID", "PortNumber", "FanAlert"]].copy()
        payload["FanAlert"] = pd.to_numeric(payload["FanAlert"], errors="coerce").fillna(0.0)
        mask = payload["FanAlert"] > 0
        if not bool(mask.any()):
            return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)
        filtered = payload.loc[mask]
        filtered[str(AnomlyType.IBH_FAN_FAILURE)] = filtered["FanAlert"].apply(
            lambda val: max(0.1, float(val))
        )
        return filtered[IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_FAN_FAILURE)]]

    def _merged(self) -> pd.DataFrame:
        speeds = self._speeds_table()
        thresholds = self._thresholds_table()
        alerts = self._alerts_table()
        if speeds.empty:
            return pd.DataFrame()
        merged = speeds.merge(
            thresholds,
            on=["NodeGUID", "SensorIndex"],
            how="left",
            suffixes=("", "_thr"),
        )
        if not alerts.empty:
            merged = merged.merge(alerts, on="NodeGUID", how="left")
        return merged

    def _alerts_table(self) -> pd.DataFrame:
        if self._alerts is not None:
            return self._alerts
        if self.ALERT_TABLE not in self._index.index:
            self._alerts = pd.DataFrame()
            return self._alerts
        df = read_table(self._db_csv, self.ALERT_TABLE, self._index)
        df.rename(columns={"NodeGuid": "NodeGUID"}, inplace=True)
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        df["FansUnderLimit"] = pd.to_numeric(df.get("FansUnderLimit"), errors="coerce")
        df["FansOverLimit"] = pd.to_numeric(df.get("FansOverLimit"), errors="coerce")
        self._alerts = df
        return self._alerts

    def _speeds_table(self) -> pd.DataFrame:
        if self._speeds is not None:
            return self._speeds
        if self.SPEED_TABLE not in self._index.index:
            self._speeds = pd.DataFrame()
            return self._speeds
        df = read_table(self._db_csv, self.SPEED_TABLE, self._index)
        df.rename(columns={"NodeGuid": "NodeGUID"}, inplace=True)
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        df["FanSpeed"] = pd.to_numeric(df.get("FanSpeed"), errors="coerce")
        self._speeds = df
        return self._speeds

    def _thresholds_table(self) -> pd.DataFrame:
        if self._thresholds is not None:
            return self._thresholds
        if self.THRESHOLD_TABLE not in self._index.index:
            self._thresholds = pd.DataFrame()
            return self._thresholds
        df = read_table(self._db_csv, self.THRESHOLD_TABLE, self._index)
        df.rename(columns={"NodeGuid": "NodeGUID"}, inplace=True)
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        df["MinSpeed"] = pd.to_numeric(df.get("MinSpeed"), errors="coerce")
        df["MaxSpeed"] = pd.to_numeric(df.get("MaxSpeed"), errors="coerce")
        self._thresholds = df
        return self._thresholds

    def _evaluate_fan(self, row) -> float:
        speed = row.get("FanSpeed")
        min_speed = row.get("MinSpeed")
        max_speed = row.get("MaxSpeed")
        if pd.isna(speed) or pd.isna(min_speed):
            return 0.0
        speed_val = float(speed)
        min_val = float(min_speed)
        if speed_val < min_val:
            return float(min_val - speed_val)
        if pd.notna(max_speed):
            max_val = float(max_speed)
            if speed_val > max_val:
                return float(speed_val - max_val)
        return 0.0

    def _topology_lookup(self) -> TopologyLookup:
        if self._topology is None:
            self._topology = TopologyLookup(self.dataset_root)
        return self._topology

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
        return text.lower()
