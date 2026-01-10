"""Xmit (congestion) analysis service."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .dataset_inventory import DatasetInventory
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

XMIT_TABLE = "PM_DELTA"
CREDIT_WATCHDOG_TABLE = "CREDIT_WATCHDOG_TIMEOUT_COUNTERS"

DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",
    "Node Type",
    "Attached To",
    "Attached To Type",
    "PortNumber",
    "Attached To Port",
    "PortState",
    "PortPhyState",
    "NeighborPortState",
    "NeighborPortPhyState",
    "NeighborIsActive",
    "CongestionLevel",
    "WaitSeconds",
    "WaitRatioPct",
    "XmitCongestionPct",
    "FECNCount",
    "BECNCount",
    "PortXmitData",
    "PortRcvData",
    "PortXmitPkts",
    "PortRcvPkts",
    "PortXmitWait",
    "PortXmitWaitTotal",
    "PortXmitDataTotal",
    "PortRcvDataExtended",
    "PortXmitDataExtended",
    "LinkDownedCounter",
    "LinkErrorRecoveryCounter",
    "PortRcvErrors",
    "PortXmitDiscards",
    "SymbolErrorCounter",
    "PortRcvRemotePhysicalErrors",
    "ActiveLinkWidth",
    "SupportedLinkWidth",
    "ActiveLinkSpeed",
    "SupportedLinkSpeed",
    "LinkComplianceStatus",
    "CreditWatchdogTimeout",
]
WIDTH_PRIORITY = [
    (0x08, 12),
    (0x04, 8),
    (0x02, 4),
    (0x10, 2),
    (0x01, 1),
]
SPEED_PRIORITY = [
    (0x800, ("HDR/NDR", 7)),
    (0x400, ("EDR/HDR100", 6)),
    (0x200, ("FDR10", 5)),
    (0x100, ("FDR", 4)),
    (0x80, ("QDR", 3)),
    (0x40, ("DDR", 2)),
    (0x20, ("SDR+", 1)),
    (0x10, ("SDR", 1)),
    (0x8, ("Legacy", 0)),
    (0x4, ("Legacy", 0)),
    (0x2, ("Legacy", 0)),
    (0x1, ("Legacy", 0)),
]


@dataclass
class XmitAnalysis:
    data: List[dict]
    anomalies: pd.DataFrame
    summary: Dict[str, object] = field(default_factory=dict)


class XmitService:
    """Computes congestion insights similar to ib_analysis.xmit."""

    def __init__(self, dataset_root: Path, dataset_inventory: DatasetInventory | None = None):
        self.dataset_root = dataset_root
        self._inventory = dataset_inventory or DatasetInventory(dataset_root)
        self._df: pd.DataFrame | None = None
        self._ports_df: pd.DataFrame | None = None
        self._credit_df: pd.DataFrame | None = None

    def clear_cache(self):
        """Clear cached DataFrames to free memory."""
        self._df = None
        self._topology = None
        self._ports_df = None
        self._credit_df = None

    def run(self) -> XmitAnalysis:
        df = self._load_dataframe()
        anomalies = self._build_anomalies(df)
        summary = self._build_summary(df)
        return XmitAnalysis(data=df.to_dict(orient="records"), anomalies=anomalies, summary=summary)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        df = self._inventory.read_table(XMIT_TABLE)
        df["NodeGUID"] = df.apply(self._remove_redundant_zero, axis=1)
        df["PortXmitWaitTotal"] = pd.to_numeric(df.get("PortXmitWaitExt", 0), errors="coerce").fillna(0)
        df["PortXmitDataTotal"] = pd.to_numeric(df.get("PortXmitDataExtended", 0), errors="coerce").fillna(0)
        tick_to_seconds = 4e-9
        duration = self._extract_duration(self._inventory.db_csv)
        df["WaitSeconds"] = df["PortXmitWaitTotal"] * tick_to_seconds
        # Safe duration conversion with validation
        try:
            duration_float = float(duration) if duration else 0.0
            duration_seconds = duration_float if duration_float > 0 else 1.0
        except (ValueError, TypeError):
            duration_seconds = 1.0
        df["WaitRatioPct"] = (df["WaitSeconds"] / duration_seconds) * 100
        df["CongestionLevel"] = df["WaitRatioPct"].apply(self._classify_wait_ratio)

        fecn = self._extract_counter(df, "PortRcvFECN", "PortRcvFECNExt")
        if fecn is not None:
            df["FECNCount"] = fecn
        becn = self._extract_counter(df, "PortRcvBECN", "PortRcvBECNExt")
        if becn is not None:
            df["BECNCount"] = becn
        cong = self._extract_counter(df, "PortXmitTimeCong", "PortXmitTimeCongExt")
        if cong is not None:
            df["XmitCongestionSeconds"] = cong * tick_to_seconds
            df["XmitCongestionPct"] = (df["XmitCongestionSeconds"] / duration_seconds) * 100
        df = self._merge_port_metadata(df)
        df = self._annotate_link_compliance(df)
        df = self._topology_lookup().annotate_ports(df, guid_col="NodeGUID", port_col="PortNumber")
        df = self._annotate_neighbor_state(df)
        existing = [col for col in DISPLAY_COLUMNS if col in df.columns]
        df = df[existing].copy()
        self._df = df
        return df

    @staticmethod
    def _remove_redundant_zero(row) -> str:
        if isinstance(row, dict) or hasattr(row, "get"):
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

    @staticmethod
    def _extract_duration(file_name: Path) -> float:
        pattern = "--pm_pause_time"
        try:
            with open(file_name, "r", encoding="latin-1") as handle:
                for _ in range(30):
                    line = handle.readline()
                    if not line:
                        break
                    if pattern in line:
                        try:
                            return float(line.strip().split()[-1])
                        except (ValueError, IndexError):
                            return 1.0
        except OSError:
            return 1.0
        return 1.0

    @staticmethod
    def _classify_wait_ratio(value):
        try:
            val = float(value)
        except (TypeError, ValueError):
            return "unknown"
        if val >= 5:
            return "severe"
        if val >= 1:
            return "warning"
        if val >= 0:
            return "normal"
        return "unknown"

    @staticmethod
    def _extract_counter(df: pd.DataFrame, primary: str, secondary: str | None = None):
        series = None
        if primary in df.columns:
            series = pd.to_numeric(df[primary], errors="coerce").fillna(0)
        if secondary and secondary in df.columns:
            extra = pd.to_numeric(df[secondary], errors="coerce").fillna(0)
            series = extra if series is None else (series + extra)
        return series

    def _build_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        frames = [
            self._build_counter_anomaly(df, "FECNCount", AnomlyType.IBH_FECN_ALERT),
            self._build_counter_anomaly(df, "BECNCount", AnomlyType.IBH_BECN_ALERT),
            self._build_ratio_anomaly(df, "XmitCongestionPct", AnomlyType.IBH_XMIT_TIME_CONG),
            self._build_ratio_anomaly(df, "WaitRatioPct", AnomlyType.IBH_HIGH_XMIT_WAIT),
            self._build_link_downgrade_anomaly(df),
            self._build_credit_watchdog_anomaly(df),
        ]
        frames = [frame for frame in frames if frame is not None]
        if not frames:
            return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)
        out = frames[0]
        for extra in frames[1:]:
            out = pd.merge(out, extra, on=IBH_ANOMALY_TBL_KEY, how="outer")
        return out.fillna(0)

    def _build_counter_anomaly(self, df: pd.DataFrame, column: str, anomaly: AnomlyType):
        if column not in df.columns:
            return None
        payload = df[IBH_ANOMALY_TBL_KEY + [column]].copy()
        payload[str(anomaly)] = payload[column].apply(self._counter_weight)
        return payload[IBH_ANOMALY_TBL_KEY + [str(anomaly)]]

    @staticmethod
    def _counter_weight(value):
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.0
        if val <= 0:
            return 0.0
        return max(0.1, math.log10(val + 1.0))

    def _build_ratio_anomaly(self, df: pd.DataFrame, column: str, anomaly: AnomlyType):
        if column not in df.columns:
            return None
        payload = df[IBH_ANOMALY_TBL_KEY + [column]].copy()
        payload[str(anomaly)] = payload[column].apply(self._ratio_weight)
        return payload[IBH_ANOMALY_TBL_KEY + [str(anomaly)]]

    @staticmethod
    def _ratio_weight(value):
        try:
            val = float(value)
        except (TypeError, ValueError):
            return 0.0
        if val >= 5:
            return val / 5.0
        if val >= 1:
            return val / 10.0
        return 0.0

    def _merge_port_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        ports = self._ports_table()
        if ports.empty:
            return df

        # Ensure PortNumber columns have the same dtype before merging
        df["PortNumber"] = df["PortNumber"].astype(str)
        ports_subset = ports[
            [
                "NodeGUID",
                "PortNumber",
                "PortState",
                "PortPhyState",
                "LinkWidthActv",
                "LinkWidthSup",
                "LinkWidthEn",
                "LinkSpeedActv",
                "LinkSpeedEn",
                "LinkSpeedSup",
            ]
        ].copy()
        ports_subset["PortNumber"] = ports_subset["PortNumber"].astype(str)

        merged = df.merge(
            ports_subset,
            on=["NodeGUID", "PortNumber"],
            how="left",
        )
        credit = self._credit_watchdog_table()
        if not credit.empty:
            credit["PortNumber"] = credit["PortNumber"].astype(str)
            merged = merged.merge(
                credit,
                on=["NodeGUID", "PortNumber"],
                how="left",
            )
        if "CreditWatchdogTimeout" not in merged.columns:
            merged["CreditWatchdogTimeout"] = 0.0
        merged["PortState"] = merged["PortState"].apply(self._decode_port_state)
        merged["PortPhyState"] = merged["PortPhyState"].apply(self._decode_port_phy_state)
        return merged

    def _annotate_link_compliance(self, df: pd.DataFrame) -> pd.DataFrame:
        if "LinkWidthActv" not in df.columns:
            return df
        df = df.copy()
        df["ActiveLinkWidthValue"], df["ActiveLinkWidth"] = zip(
            *df["LinkWidthActv"].map(self._decode_width)
        )
        df["SupportedLinkWidthValue"], df["SupportedLinkWidth"] = zip(
            *df["LinkWidthSup"].map(self._decode_width)
        )
        df["ActiveLinkSpeedValue"], df["ActiveLinkSpeed"] = zip(
            *df["LinkSpeedActv"].map(self._decode_speed)
        )
        df["SupportedLinkSpeedValue"], df["SupportedLinkSpeed"] = zip(
            *df["LinkSpeedSup"].map(self._decode_speed)
        )
        df["LinkWidthDownshift"] = (
            df["SupportedLinkWidthValue"].notna()
            & df["SupportedLinkWidthValue"].gt(0)
            & df["ActiveLinkWidthValue"].fillna(0).lt(df["SupportedLinkWidthValue"].fillna(0))
        )
        df["LinkSpeedDownshift"] = (
            df["SupportedLinkSpeedValue"].notna()
            & df["SupportedLinkSpeedValue"].gt(0)
            & df["ActiveLinkSpeedValue"].fillna(0).lt(df["SupportedLinkSpeedValue"].fillna(0))
        )
        df["LinkComplianceStatus"] = df.apply(
            lambda row: "Downshift" if row["LinkWidthDownshift"] or row["LinkSpeedDownshift"] else "OK",
            axis=1,
        )
        return df

    def _build_link_downgrade_anomaly(self, df: pd.DataFrame):
        if "LinkWidthDownshift" not in df.columns:
            return None
        mask = df["LinkWidthDownshift"] | df["LinkSpeedDownshift"]
        if not bool(mask.any()):
            return None
        payload = df.loc[mask, IBH_ANOMALY_TBL_KEY + ["Attached To Type"]].copy()
        payload[str(AnomlyType.IBH_LINK_DOWNSHIFT)] = payload["Attached To Type"].apply(self._link_downshift_weight)
        return payload[IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_LINK_DOWNSHIFT)]]

    def _build_credit_watchdog_anomaly(self, df: pd.DataFrame):
        column = "CreditWatchdogTimeout"
        if column not in df.columns:
            return None
        payload = df[IBH_ANOMALY_TBL_KEY + [column]].copy()
        mask = payload[column].fillna(0) > 0
        if not bool(mask.any()):
            return None
        payload = payload.loc[mask]
        payload[str(AnomlyType.IBH_CREDIT_WATCHDOG)] = payload[column].apply(
            lambda value: max(0.1, float(value))
        )
        return payload[IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_CREDIT_WATCHDOG)]]

    def _build_summary(self, df: pd.DataFrame) -> Dict[str, object]:
        summary = {
            "total_ports": int(len(df)),
            "severe_ports": 0,
            "warning_ports": 0,
            "fecn_ports": 0,
            "becn_ports": 0,
            "avg_wait_ratio_pct": 0.0,
            "max_wait_ratio_pct": 0.0,
            "avg_congestion_pct": 0.0,
            "top_waiters": [],
        }
        if df.empty:
            return summary

        def _numeric_series(column: str) -> pd.Series:
            if column in df.columns:
                return pd.to_numeric(df[column], errors="coerce").fillna(0.0)
            return pd.Series(0.0, index=df.index)

        ratio_series = _numeric_series("WaitRatioPct")
        congestion_series = _numeric_series("XmitCongestionPct")
        wait_seconds = _numeric_series("WaitSeconds")

        severe_mask = (ratio_series >= 5.0) | (congestion_series >= 5.0)
        warning_mask = (~severe_mask) & (
            (ratio_series >= 1.0)
            | (congestion_series >= 1.0)
            | (wait_seconds > 0.0)
        )

        summary["severe_ports"] = int(severe_mask.sum())
        summary["warning_ports"] = int(warning_mask.sum())
        summary["avg_wait_ratio_pct"] = float(ratio_series.mean())
        summary["max_wait_ratio_pct"] = float(ratio_series.max())
        summary["avg_congestion_pct"] = float(congestion_series.mean())

        fecn = _numeric_series("FECNCount")
        becn = _numeric_series("BECNCount")
        summary["fecn_ports"] = int((fecn > 0).sum())
        summary["becn_ports"] = int((becn > 0).sum())

        credit = _numeric_series("CreditWatchdogTimeout")
        summary["credit_watchdog_ports"] = int((credit > 0).sum())

        link_down = _numeric_series("LinkDownedCounter") + _numeric_series("LinkDownedCounterExt")
        summary["link_down_ports"] = int((link_down > 0).sum())
        summary["link_down_events"] = float(link_down.sum())

        df_top = df.assign(__ratio=ratio_series).sort_values("__ratio", ascending=False).head(5)
        summary["top_waiters"] = [
            {
                "node_name": row.get("Node Name") or row.get("NodeName") or row.get("NodeGUID"),
                "node_guid": row.get("NodeGUID"),
                "port_number": row.get("PortNumber"),
                "wait_ratio_pct": float(row.get("__ratio", 0.0) or 0.0),
                "wait_seconds": float(row.get("WaitSeconds") or 0.0),
                "xmit_congestion_pct": float(row.get("XmitCongestionPct") or 0.0),
            }
            for _, row in df_top.iterrows()
        ]
        return summary

    def _ports_table(self) -> pd.DataFrame:
        if self._ports_df is not None:
            return self._ports_df
        if not self._inventory.table_exists("PORTS"):
            self._ports_df = pd.DataFrame()
            return self._ports_df
        ports = self._inventory.read_table("PORTS")
        ports.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber"}, inplace=True)
        ports["NodeGUID"] = ports["NodeGUID"].apply(self._remove_redundant_zero)
        self._ports_df = ports
        return self._ports_df

    def _credit_watchdog_table(self) -> pd.DataFrame:
        if self._credit_df is not None:
            return self._credit_df
        if not self._inventory.table_exists(CREDIT_WATCHDOG_TABLE):
            self._credit_df = pd.DataFrame()
            return self._credit_df
        df = self._inventory.read_table(CREDIT_WATCHDOG_TABLE)
        if df.empty:
            self._credit_df = pd.DataFrame()
            return self._credit_df
        df.rename(columns={"NodeGUID": "NodeGUID", "PortNumber": "PortNumber"}, inplace=True)
        df["NodeGUID"] = df["NodeGUID"].apply(self._remove_redundant_zero)
        df["PortNumber"] = pd.to_numeric(df["PortNumber"], errors="coerce")
        df["CreditWatchdogTimeout"] = pd.to_numeric(
            df.get("total_port_credit_watchdog_timeout", 0), errors="coerce"
        ).fillna(0)
        self._credit_df = df[["NodeGUID", "PortNumber", "CreditWatchdogTimeout"]]
        return self._credit_df

    @staticmethod
    def _decode_width(value) -> Tuple[Optional[int], Optional[str]]:
        try:
            code = int(value)
        except (TypeError, ValueError):
            return (None, None)
        for bit, width in WIDTH_PRIORITY:
            if code & bit:
                return (width, f"{width}X")
        return (None, None)

    @staticmethod
    def _decode_speed(value) -> Tuple[Optional[int], Optional[str]]:
        try:
            code = int(value)
        except (TypeError, ValueError):
            return (None, None)
        for bit, (label, priority) in SPEED_PRIORITY:
            if code & bit:
                return (priority, label)
        return (None, None)

    def _find_db_csv(self) -> Path:
        return self._inventory.db_csv

    @staticmethod
    def _decode_port_state(value: object) -> str:
        try:
            code = int(value)
        except (TypeError, ValueError):
            return "Unknown"
        return PORT_STATE_MAP.get(code, str(code))

    @staticmethod
    def _decode_port_phy_state(value: object) -> str:
        try:
            code = int(value)
        except (TypeError, ValueError):
            return "Unknown"
        return PORT_PHY_STATE_MAP.get(code, str(code))

    def _topology_lookup(self) -> TopologyLookup:
        return self._inventory.topology

    def _annotate_neighbor_state(self, df: pd.DataFrame) -> pd.DataFrame:
        if "Attached To GUID" not in df.columns:
            return df
        ports = self._ports_table()
        if ports.empty:
            return df

        # Build neighbor lookup dictionary once (O(n) instead of O(n²))
        neighbor_cols = ports[["NodeGUID", "PortNumber", "PortState", "PortPhyState"]].copy()
        neighbor_cols["NeighborPortState"] = neighbor_cols["PortState"].apply(self._decode_port_state)
        neighbor_cols["NeighborPortPhyState"] = neighbor_cols["PortPhyState"].apply(self._decode_port_phy_state)

        # Create efficient lookup dictionary
        neighbor_map = {}
        for _, row in neighbor_cols.iterrows():
            guid = str(row["NodeGUID"])
            port = row["PortNumber"]
            if guid and pd.notna(port):
                try:
                    neighbor_map[(guid, int(port))] = (row["NeighborPortState"], row["NeighborPortPhyState"])
                except (ValueError, TypeError):
                    continue

        # Vectorized lookup using map
        df = df.copy()

        def lookup_neighbor(row):
            guid = row.get("Attached To GUID")
            port = row.get("Attached To Port")
            if guid is None or pd.isna(port):
                return pd.Series([None, None])
            try:
                result = neighbor_map.get((str(guid), int(port)), (None, None))
                return pd.Series(result)
            except (ValueError, TypeError):
                return pd.Series([None, None])

        df[["NeighborPortState", "NeighborPortPhyState"]] = df.apply(lookup_neighbor, axis=1)
        df["NeighborIsActive"] = df["NeighborPortState"].apply(
            lambda val: isinstance(val, str) and "Active" in val
        )
        return df

    @staticmethod
    def _link_downshift_weight(neighbor_type: object) -> float:
        if neighbor_type is None:
            return 1.0
        text = str(neighbor_type).strip().lower()
        if "switch" in text or "spine" in text:
            return 2.0
        return 1.0
PORT_STATE_MAP = {
    0: "NoChange",
    1: "Down",
    2: "Initialize",
    3: "Armed",
    4: "Active",
}

PORT_PHY_STATE_MAP = {
    0: "Unknown",
    1: "Sleeping",
    2: "Polling",
    3: "Disabled",
    4: "LinkUp",
    5: "LinkUp",
}
