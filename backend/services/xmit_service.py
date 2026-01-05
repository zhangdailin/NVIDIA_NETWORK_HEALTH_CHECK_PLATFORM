"""Xmit (congestion) analysis service."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .ibdiagnet import read_index_table, read_table
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


class XmitService:
    """Computes congestion insights similar to ib_analysis.xmit."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._df: pd.DataFrame | None = None
        self._topology: TopologyLookup | None = None
        self._ports_df: pd.DataFrame | None = None
        self._credit_df: pd.DataFrame | None = None

    def run(self) -> XmitAnalysis:
        df = self._load_dataframe()
        anomalies = self._build_anomalies(df)
        return XmitAnalysis(data=df.to_dict(orient="records"), anomalies=anomalies)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        df = read_table(db_csv, XMIT_TABLE, index_table)
        df["NodeGUID"] = df.apply(self._remove_redundant_zero, axis=1)
        df["PortXmitWaitTotal"] = pd.to_numeric(df.get("PortXmitWaitExt", 0), errors="coerce").fillna(0)
        df["PortXmitDataTotal"] = pd.to_numeric(df.get("PortXmitDataExtended", 0), errors="coerce").fillna(0)
        tick_to_seconds = 4e-9
        duration = self._extract_duration(db_csv)
        df["WaitSeconds"] = df["PortXmitWaitTotal"] * tick_to_seconds
        duration_seconds = float(duration) if duration and float(duration) > 0 else 1.0
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

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    @staticmethod
    def _remove_redundant_zero(row) -> str:
        if isinstance(row, dict) or hasattr(row, "get"):
            guid = str(row.get("NodeGUID", ""))
        else:
            guid = str(row)
        if guid.startswith("0x"):
            return hex(int(guid, 16))
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
        merged = df.merge(
            ports[
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
            ],
            on=["NodeGUID", "PortNumber"],
            how="left",
        )
        credit = self._credit_watchdog_table()
        if not credit.empty:
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

    def _ports_table(self) -> pd.DataFrame:
        if self._ports_df is not None:
            return self._ports_df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        if "PORTS" not in index_table.index:
            self._ports_df = pd.DataFrame()
            return self._ports_df
        ports = read_table(db_csv, "PORTS", index_table)
        ports.rename(columns={"NodeGuid": "NodeGUID", "PortNum": "PortNumber"}, inplace=True)
        ports["NodeGUID"] = ports["NodeGUID"].apply(self._remove_redundant_zero)
        self._ports_df = ports
        return self._ports_df

    def _credit_watchdog_table(self) -> pd.DataFrame:
        if self._credit_df is not None:
            return self._credit_df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        if CREDIT_WATCHDOG_TABLE not in index_table.index:
            self._credit_df = pd.DataFrame()
            return self._credit_df
        df = read_table(db_csv, CREDIT_WATCHDOG_TABLE, index_table)
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
        if self._topology is None:
            self._topology = TopologyLookup(self.dataset_root)
        return self._topology

    def _annotate_neighbor_state(self, df: pd.DataFrame) -> pd.DataFrame:
        if "Attached To GUID" not in df.columns:
            return df
        ports = self._ports_table()
        if ports.empty:
            return df
        neighbor_cols = ports[["NodeGUID", "PortNumber", "PortState", "PortPhyState"]].copy()
        neighbor_cols["NeighborPortState"] = neighbor_cols["PortState"].apply(self._decode_port_state)
        neighbor_cols["NeighborPortPhyState"] = neighbor_cols["PortPhyState"].apply(self._decode_port_phy_state)
        neighbor_cols.rename(columns={"NodeGUID": "NeighborGUID", "PortNumber": "NeighborPort"}, inplace=True)
        neighbor_cols = neighbor_cols[["NeighborGUID", "NeighborPort", "NeighborPortState", "NeighborPortPhyState"]]

        neighbor_map = {
            (str(guid), int(port)): (state, phy)
            for guid, port, state, phy in neighbor_cols.itertuples(index=False, name=None)
            if guid and port is not None
        }

        def lookup(row):
            guid = row.get("Attached To GUID")
            port = row.get("Attached To Port")
            if guid is None or pd.isna(port):
                return (None, None)
            return neighbor_map.get((str(guid), int(port)))

        df = df.copy()
        df[["NeighborPortState", "NeighborPortPhyState"]] = df.apply(
            lambda row: pd.Series(lookup(row)),
            axis=1,
        )
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
