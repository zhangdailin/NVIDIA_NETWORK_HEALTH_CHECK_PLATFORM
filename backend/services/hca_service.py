"""HCA inventory and compliance service."""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

from .anomalies import AnomlyType, IBH_ANOMALY_TBL_KEY
from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

HCA_TABLE = "NODES_INFO"


class HcaService:
    """Loads host adapters and evaluates firmware/PSID compliance."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._df: pd.DataFrame | None = None
        self.fw_matrix = self._load_fw_matrix()
        self._topology: TopologyLookup | None = None

    def run(self) -> List[Dict[str, object]]:
        df = self._load_dataframe()
        return df.to_dict(orient="records")

    def build_anomalies(self) -> pd.DataFrame:
        df = self._load_dataframe()
        frames = [
            self._build_flag_anomaly(df, "PSID_Compliant", AnomlyType.IBH_PSID_UNSUPPORTED),
            self._build_version_anomaly(df, "FW_Compliant", "FW_Lag", AnomlyType.IBH_FW_OUTDATED),
        ]
        frames = [frame for frame in frames if frame is not None]
        if not frames:
            return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)
        out = frames[0]
        for extra in frames[1:]:
            out = pd.merge(out, extra, on=IBH_ANOMALY_TBL_KEY, how="outer")
        return out.fillna(0)

    def _load_dataframe(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        db_csv = self._find_db_csv()
        index_table = read_index_table(db_csv)
        df = read_table(db_csv, HCA_TABLE, index_table)
        df["NodeGUID"] = df.apply(self._remove_redundant_zero, axis=1)
        df["Device Type"] = df.apply(self._device_type, axis=1)
        df["FW Date"] = (
            df["FWInfo_Year"].astype(str).str[2:]
            + "/"
            + df["FWInfo_Month"].astype(str).str[2:]
            + "/"
            + df["FWInfo_Day"].astype(str).str[2:]
        )
        df["FWInfo_Extended_Major"] = df["FWInfo_Extended_Major"].apply(lambda x: int(x, 16))
        df["FWInfo_Extended_Minor"] = df["FWInfo_Extended_Minor"].apply(lambda x: int(x, 16))
        df["FWInfo_Extended_SubMinor"] = df["FWInfo_Extended_SubMinor"].apply(lambda x: int(x, 16))
        df["Up Time"] = df["HWInfo_UpTime"].apply(lambda x: str(timedelta(seconds=int(x, 16))))
        df["FW"] = (
            df["FWInfo_Extended_Major"].astype(str)
            + "."
            + df["FWInfo_Extended_Minor"].astype(str)
            + "."
            + df["FWInfo_Extended_SubMinor"].astype(str).str.zfill(4)
        )
        compliance = df.apply(lambda row: pd.Series(self._evaluate_fw_policy(row)), axis=1)
        df["PSID_Compliant"] = compliance["psid_ok"]
        df["FW_Compliant"] = compliance["fw_ok"]
        df["RecommendedFW"] = compliance["recommended_fw"]
        df["PolicyNotes"] = compliance["notes"]
        df["FW_Lag"] = compliance["fw_lag"]
        df = self._topology_lookup().annotate_nodes(df, guid_col="NodeGUID")
        display_columns = [
            "NodeGUID",
            "Node Name",
            "Device Type",
            "FW",
            "FW Date",
            "FWInfo_PSID",
            "HWInfo_UpTime",
            "PSID_Compliant",
            "FW_Compliant",
            "RecommendedFW",
            "PolicyNotes",
        ]
        existing = [col for col in display_columns if col in df.columns]
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
        guid = str(row.get("NodeGUID", ""))
        if guid.startswith("0x"):
            return hex(int(guid, 16))
        return guid

    @staticmethod
    def _device_type(row):
        return str(row.get("HWInfo_DeviceID", "NA"))

    def _load_fw_matrix(self):
        matrix_path = self.dataset_root / "fw_matrix.json"
        if not matrix_path.exists():
            matrix_path = Path("backend/services/references/fw_matrix.json")
        if not matrix_path.exists():
            return {}
        try:
            data = json.loads(matrix_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read firmware policy file: %s", exc)
            return {}
        entries = data.get("policies", data)
        policies = {}
        for entry in entries:
            dev_type = (entry.get("device_type") or "*").strip().lower() or "*"
            policies[dev_type] = {
                "allowed_psids": entry.get("allowed_psids") or [],
                "min_fw": entry.get("min_fw") or "",
                "notes": entry.get("notes", ""),
            }
        return policies

    def _evaluate_fw_policy(self, row):
        device_type = str(row.get("Device Type", "")).strip().lower()
        psid = str(row.get("FWInfo_PSID", "")).strip().upper()
        policy = self.fw_matrix.get(device_type) or self.fw_matrix.get("*")
        if not policy:
            return {"psid_ok": True, "fw_ok": True, "recommended_fw": "", "notes": "", "fw_lag": 0.0}
        allowed_psids = [p.strip().upper() for p in policy.get("allowed_psids") or []]
        psid_ok = True if not allowed_psids else (psid in allowed_psids)
        recommended_fw = policy.get("min_fw", "")
        fw_ok = True
        lag = 0.0
        if recommended_fw:
            fw_ok = self._compare_versions(str(row.get("FW", "0.0.0")), recommended_fw) >= 0
            if not fw_ok:
                lag = max(0.1, float(self._version_score(recommended_fw) - self._version_score(str(row.get("FW", "0.0.0")))))
        return {
            "psid_ok": psid_ok,
            "fw_ok": fw_ok,
            "recommended_fw": recommended_fw,
            "notes": policy.get("notes", ""),
            "fw_lag": lag,
        }

    @staticmethod
    def _version_score(version: str) -> int:
        parts = str(version).split(".")
        major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        return major * 1_000_000 + minor * 1_000 + patch

    @classmethod
    def _compare_versions(cls, lhs: str, rhs: str) -> int:
        left = cls._version_score(lhs)
        right = cls._version_score(rhs)
        if left == right:
            return 0
        return 1 if left > right else -1

    def _build_flag_anomaly(self, df: pd.DataFrame, column: str, anomaly: AnomlyType):
        if column not in df.columns:
            return None
        mask = ~df[column].fillna(True)
        if not mask.any():
            return None
        flagged = df.loc[mask, IBH_ANOMALY_TBL_KEY].copy()
        flagged[str(anomaly)] = 1.0
        return flagged

    def _build_version_anomaly(self, df: pd.DataFrame, status_column: str, lag_column: str, anomaly: AnomlyType):
        if status_column not in df.columns or lag_column not in df.columns:
            return None
        mask = ~df[status_column].fillna(True)
        if not mask.any():
            return None
        flagged = df.loc[mask, IBH_ANOMALY_TBL_KEY + [lag_column]].copy()
        flagged[str(anomaly)] = flagged[lag_column].apply(
            lambda value: max(0.1, float(value) if pd.notna(value) else 0.1)
        )
        return flagged[IBH_ANOMALY_TBL_KEY + [str(anomaly)]]

    def _topology_lookup(self) -> TopologyLookup:
        if self._topology is None:
            self._topology = TopologyLookup(self.dataset_root)
        return self._topology
