"""Extended Port Info service for bandwidth utilization and FEC mode analysis.

Uses tables:
- EXTENDED_PORT_INFO: Comprehensive port capabilities and status
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


@dataclass
class ExtendedPortInfoResult:
    """Result from Extended Port Info analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class ExtendedPortInfoService:
    """Analyze extended port information including BW utilization and FEC modes."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> ExtendedPortInfoResult:
        """Run Extended Port Info analysis."""
        ext_df = self._try_read_table("EXTENDED_PORT_INFO")

        if ext_df.empty:
            return ExtendedPortInfoResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        unhealthy_count = 0
        bw_util_enabled = 0
        fec_modes: Dict[str, int] = defaultdict(int)
        retrans_enabled = 0

        for _, row in ext_df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            port_num = self._safe_int(row.get("PortNum"))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # Key metrics
            unhealthy_reason = self._safe_int(row.get("UnhealthyReason", 0))
            bw_util = self._safe_float(row.get("BwUtilization", 0))
            bw_util_en = self._safe_int(row.get("BwUtilEn", 0))
            min_bw_util = self._safe_float(row.get("MinBwUtilization", 0))
            retrans_mode = self._safe_int(row.get("RetransMode", 0))

            # FEC modes
            fec_active = self._parse_hex(row.get("FECModeActive", "0"))
            hdr_fec_sup = self._parse_hex(row.get("HDRFECModeSupported", "0"))
            hdr_fec_en = self._parse_hex(row.get("HDRFECModeEnabled", "0"))
            ndr_fec_sup = self._parse_hex(row.get("NDRFECModeSupported", "0"))
            ndr_fec_en = self._parse_hex(row.get("NDRFECModeEnabled", "0"))

            # Link speed
            link_speed_active = str(row.get("LinkSpeedActive", ""))
            link_speed_supported = str(row.get("LinkSpeedSupported", ""))

            # Track statistics
            if unhealthy_reason > 0:
                unhealthy_count += 1
            if bw_util_en > 0:
                bw_util_enabled += 1
            if retrans_mode > 0:
                retrans_enabled += 1

            # Determine FEC mode string
            fec_mode_str = self._fec_mode_to_string(fec_active)
            fec_modes[fec_mode_str] += 1

            # Determine severity
            severity = "normal"
            issues = []

            if unhealthy_reason > 0:
                severity = "critical"
                issues.append(f"Unhealthy reason: 0x{unhealthy_reason:x}")

            if bw_util_en and bw_util < min_bw_util * 0.5:
                if severity == "normal":
                    severity = "warning"
                issues.append(f"Low BW utilization: {bw_util:.1f}%")

            # Check FEC mismatch (supported but not enabled)
            if hdr_fec_sup and not hdr_fec_en:
                if severity == "normal":
                    severity = "info"
                issues.append("HDR FEC supported but not enabled")

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "UnhealthyReason": unhealthy_reason,
                "BwUtilization": round(bw_util, 2),
                "BwUtilEnabled": bw_util_en > 0,
                "MinBwUtilization": round(min_bw_util, 2),
                "RetransMode": retrans_mode,
                "FECModeActive": fec_mode_str,
                "LinkSpeedActive": link_speed_active,
                "LinkSpeedSupported": link_speed_supported,
                "HDRFECSupported": hdr_fec_sup > 0,
                "NDRFECSupported": ndr_fec_sup > 0,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = self._build_summary(records, ext_df, unhealthy_count, bw_util_enabled, fec_modes, retrans_enabled)

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("UnhealthyReason", 0)
        ))

        return ExtendedPortInfoResult(data=records[:2000], anomalies=None, summary=summary)

    def _fec_mode_to_string(self, fec_code: int) -> str:
        """Convert FEC mode code to string."""
        if fec_code == 0:
            return "No FEC"
        elif fec_code == 1:
            return "FireCode FEC"
        elif fec_code == 2:
            return "RS-FEC (528, 514)"
        elif fec_code == 4:
            return "RS-FEC (544, 514)"
        elif fec_code == 14:
            return "RS-FEC Interleaved"
        else:
            return f"FEC Mode {fec_code}"

    def _build_summary(
        self,
        records: List[Dict],
        raw_df: pd.DataFrame,
        unhealthy_count: int,
        bw_util_enabled: int,
        fec_modes: Dict[str, int],
        retrans_enabled: int,
    ) -> Dict[str, object]:
        """Build summary statistics."""
        if not records:
            return {"total_ports": 0}

        critical_count = sum(1 for r in records if r.get("Severity") == "critical")
        warning_count = sum(1 for r in records if r.get("Severity") == "warning")

        return {
            "total_ports": len(raw_df),
            "unhealthy_ports": unhealthy_count,
            "bw_util_enabled_ports": bw_util_enabled,
            "retrans_enabled_ports": retrans_enabled,
            "fec_mode_distribution": dict(sorted(fec_modes.items(), key=lambda x: -x[1])[:5]),
            "critical_count": critical_count,
            "warning_count": warning_count,
        }

    def _try_read_table(self, table_name: str) -> pd.DataFrame:
        try:
            index_table = self._get_index_table()
            if table_name not in index_table.index:
                return pd.DataFrame()
            return self._read_table(table_name)
        except Exception as e:
            logger.debug(f"Could not read {table_name}: {e}")
            return pd.DataFrame()

    def _get_index_table(self) -> pd.DataFrame:
        if self._index_cache is None:
            db_csv = self._find_db_csv()
            self._index_cache = read_index_table(db_csv)
        return self._index_cache

    def _read_table(self, table_name: str) -> pd.DataFrame:
        db_csv = self._find_db_csv()
        return read_table(db_csv, table_name, self._get_index_table())

    def _find_db_csv(self) -> Path:
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    def _get_topology(self) -> Optional[TopologyLookup]:
        if self._topology is None:
            try:
                self._topology = TopologyLookup(self.dataset_root)
            except Exception as e:
                logger.debug(f"Could not load topology: {e}")
        return self._topology

    @staticmethod
    def _safe_int(value: object) -> int:
        try:
            if pd.isna(value):
                return 0
            return int(float(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: object) -> float:
        try:
            if pd.isna(value):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_hex(value: object) -> int:
        try:
            if pd.isna(value):
                return 0
            if isinstance(value, (int, float)):
                return int(value)
            s = str(value).strip()
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(float(s))
        except (TypeError, ValueError):
            return 0
