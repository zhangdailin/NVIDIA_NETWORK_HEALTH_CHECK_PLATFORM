"""Performance histogram (RTT) analysis service."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup


@dataclass
class HistogramAnalysis:
    data: List[Dict[str, object]]
    anomalies: pd.DataFrame
    summary: Dict[str, object] = field(default_factory=dict)


class HistogramService:
    TABLE = "PERFORMANCE_HISTOGRAM_PORTS_DATA"

    def __init__(self, dataset_root: Path):
        self.dataset_root = Path(dataset_root)
        self._df: Optional[pd.DataFrame] = None
        self._bin_columns: List[str] = []
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> HistogramAnalysis:
        df = self._load_dataframe()
        if df.empty:
            empty_summary = {
                "total_ports": 0,
                "high_p99_ports": 0,
                "upper_bucket_ports": 0,
                "severe_tail_ports": 0,
                "avg_median_us": 0.0,
                "avg_p99_us": 0.0,
                "top_outliers": [],
            }
            return HistogramAnalysis(data=[], anomalies=pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY), summary=empty_summary)
        df = self._annotate_metrics(df)
        df = self._topology_lookup().annotate_ports(df, guid_col="NodeGUID", port_col="PortNumber")
        display_columns = [
            "NodeGUID",
            "Node Name",
            "Attached To",
            "PortNumber",
            "RttMedianUs",
            "RttP99Us",
            "RttP99OverMedian",
            "RttUpperBucketRatio",
        ]
        existing = [col for col in display_columns if col in df.columns]
        data = df[existing].to_dict(orient="records")
        anomalies = self._build_anomalies(df)
        summary = self._build_summary(df)
        return HistogramAnalysis(data=data, anomalies=anomalies, summary=summary)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        if self.TABLE not in index_table.index:
            self._df = pd.DataFrame()
            return self._df
        df = read_table(db_csv, self.TABLE, index_table)
        if df.empty:
            self._df = pd.DataFrame()
            return self._df
        df.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber"}, inplace=True)
        df["NodeGUID"] = df["NodeGUID"].apply(self._normalize_guid)
        self._bin_columns = [col for col in df.columns if col.startswith("bin[")]
        for column in self._bin_columns + ["min_sampled", "max_sampled"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        self._df = df
        return df

    def _annotate_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["HistogramTotal"] = df[self._bin_columns].sum(axis=1)
        df["RttMedianUs"] = df.apply(lambda row: self._estimate_percentile(row, 0.5), axis=1)
        df["RttP99Us"] = df.apply(lambda row: self._estimate_percentile(row, 0.99), axis=1)
        df["RttP99OverMedian"] = df.apply(
            lambda row: self._ratio(row.get("RttP99Us"), row.get("RttMedianUs")),
            axis=1,
        )

        # Fix: Calculate upper bucket ratio with proper NA handling
        def calculate_upper_ratio(row):
            total = row.get("HistogramTotal", 0)
            if not total or total <= 0:
                return 0.0  # Return 0 instead of NA for empty histograms
            upper_sum = sum(row.get(col, 0) or 0 for col in self._bin_columns[-2:])
            return float(upper_sum) / float(total)

        df["RttUpperBucketRatio"] = df.apply(calculate_upper_ratio, axis=1)

        df["RttOutlierFlag"] = df.apply(
            lambda row: self._is_outlier(row.get("RttP99OverMedian"), row.get("RttUpperBucketRatio")),
            axis=1,
        )
        return df

    def _estimate_percentile(self, row, quantile: float) -> float:
        total = row.get("HistogramTotal")
        if not total or total <= 0 or not self._bin_columns:
            return 0.0
        target = total * quantile
        cumulative = 0.0
        selected_idx = len(self._bin_columns) - 1
        for idx, col in enumerate(self._bin_columns):
            cumulative += row.get(col, 0) or 0
            if cumulative >= target:
                selected_idx = idx
                break
        min_val = row.get("min_sampled") or 0.0
        max_val = row.get("max_sampled") or min_val
        span = max(max_val - min_val, 1e-6)
        bucket_fraction = (selected_idx + 0.5) / len(self._bin_columns)
        return min_val + span * bucket_fraction

    @staticmethod
    def _ratio(p99: Optional[float], median: Optional[float]) -> float:
        if not median or median <= 0 or p99 is None:
            return 0.0
        return float(p99) / float(median)

    @staticmethod
    def _is_outlier(ratio: float, upper_ratio: float) -> bool:
        """Check if RTT metrics indicate an outlier. Handles pandas NA values."""
        import pandas as pd

        # Handle pandas NA values
        if pd.isna(ratio):
            ratio = 0.0
        if pd.isna(upper_ratio):
            upper_ratio = 0.0

        # Convert to float safely, handling None and other edge cases
        try:
            ratio = float(ratio) if ratio else 0.0
        except (TypeError, ValueError):
            ratio = 0.0

        try:
            upper_ratio = float(upper_ratio) if upper_ratio else 0.0
        except (TypeError, ValueError):
            upper_ratio = 0.0

        return ratio >= 3.0 or upper_ratio >= 0.1

    def _build_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        mask = df["RttOutlierFlag"].fillna(False)
        if not bool(mask.any()):
            return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)
        payload = df.loc[mask, IBH_ANOMALY_TBL_KEY + ["RttP99OverMedian", "RttUpperBucketRatio"]].copy()

        def calculate_weight(row):
            """Calculate anomaly weight with NA handling."""
            import pandas as pd
            p99_ratio = row.get("RttP99OverMedian")
            upper_ratio = row.get("RttUpperBucketRatio")

            # Handle NA values
            if pd.isna(p99_ratio):
                p99_ratio = 0.0
            if pd.isna(upper_ratio):
                upper_ratio = 0.0

            # Convert to float safely
            try:
                p99_ratio = float(p99_ratio) if p99_ratio else 0.0
            except (TypeError, ValueError):
                p99_ratio = 0.0

            try:
                upper_ratio = float(upper_ratio) if upper_ratio else 0.0
            except (TypeError, ValueError):
                upper_ratio = 0.0

            return max(0.1, min(5.0, p99_ratio / 5.0 + upper_ratio * 2))

        payload[str(AnomlyType.IBH_UNUSUAL_RTT_NUM)] = payload.apply(calculate_weight, axis=1)
        return payload[IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_UNUSUAL_RTT_NUM)]]

    def _build_summary(self, df: pd.DataFrame) -> Dict[str, object]:
        summary = {
            "total_ports": int(len(df)),
            "high_p99_ports": 0,
            "upper_bucket_ports": 0,
            "severe_tail_ports": 0,
            "avg_median_us": 0.0,
            "avg_p99_us": 0.0,
            "top_outliers": [],
        }
        if df.empty:
            return summary

        ratio = pd.to_numeric(df.get("RttP99OverMedian"), errors="coerce").fillna(0.0)
        upper = pd.to_numeric(df.get("RttUpperBucketRatio"), errors="coerce").fillna(0.0)
        median = pd.to_numeric(df.get("RttMedianUs"), errors="coerce").fillna(0.0)
        p99 = pd.to_numeric(df.get("RttP99Us"), errors="coerce").fillna(0.0)

        summary["high_p99_ports"] = int((ratio >= 3.0).sum())
        summary["upper_bucket_ports"] = int((upper >= 0.1).sum())
        summary["severe_tail_ports"] = int((ratio >= 5.0).sum())
        summary["avg_median_us"] = float(median.mean())
        summary["avg_p99_us"] = float(p99.mean())

        df_top = df.assign(__ratio=ratio).sort_values("__ratio", ascending=False).head(5)
        summary["top_outliers"] = [
            {
                "node_name": row.get("Node Name") or row.get("NodeName") or row.get("NodeGUID"),
                "node_guid": row.get("NodeGUID"),
                "port_number": row.get("PortNumber"),
                "ratio": float(row.get("__ratio", 0.0) or 0.0),
                "upper_ratio": float(row.get("RttUpperBucketRatio") or 0.0),
                "median_us": float(row.get("RttMedianUs") or 0.0),
                "p99_us": float(row.get("RttP99Us") or 0.0),
            }
            for _, row in df_top.iterrows()
        ]
        return summary

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
        if text.lower().startswith("0x"):
            try:
                return hex(int(text, 16))
            except ValueError:
                return text.lower()
        return text.lower()

    def _topology_lookup(self) -> TopologyLookup:
        if self._topology is None:
            self._topology = TopologyLookup(self.dataset_root)
        return self._topology
