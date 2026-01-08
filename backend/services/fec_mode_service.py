"""FEC Mode service for Forward Error Correction analysis.

Uses tables:
- FEC_MODE: FEC support and configuration per port/speed
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
class FecModeResult:
    """Result from FEC Mode analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class FecModeService:
    """Analyze FEC mode configuration and support across all speeds."""

    # FEC mode descriptions
    FEC_MODES = {
        0: "No FEC",
        1: "FireCode FEC",
        2: "RS-FEC (528,514)",
        4: "RS-FEC (544,514)",
        6: "RS-FEC (544,514) + Interleave",
        14: "RS-FEC Interleaved 272",
    }

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> FecModeResult:
        """Run FEC Mode analysis."""
        fec_df = self._try_read_table("FEC_MODE")

        if fec_df.empty:
            return FecModeResult()

        topology = self._get_topology()
        records = []

        # Track statistics
        fec_active_distribution: Dict[str, int] = defaultdict(int)
        speed_fec_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        mismatch_count = 0

        for _, row in fec_df.iterrows():
            node_guid = str(row.get("NodeGuid", ""))
            port_num = self._safe_int(row.get("PortNum"))

            # Get node name
            node_name = topology.node_label(node_guid) if topology else node_guid

            # FEC active mode
            fec_active = self._safe_int(row.get("FECActv", 0))
            fec_active_str = self.FEC_MODES.get(fec_active, f"Unknown ({fec_active})")
            fec_active_distribution[fec_active_str] += 1

            # Per-speed FEC support and enablement
            fdr10_sup = self._parse_hex(row.get("FDR10FECSup", "0"))
            fdr10_en = self._parse_hex(row.get("FDR10FECEn", "0"))
            edr_sup = self._parse_hex(row.get("EDRFECSup", "0"))
            edr_en = self._parse_hex(row.get("EDRFECEn", "0"))
            edr20_sup = self._parse_hex(row.get("EDR20FECSup", "0"))
            edr20_en = self._parse_hex(row.get("EDR20FECEn", "0"))
            hdr_sup = self._parse_hex(row.get("HDRFECSup", "0"))
            hdr_en = self._parse_hex(row.get("HDRFECEn", "0"))
            ndr_sup = self._parse_hex(row.get("NDRFECSup", "0"))
            ndr_en = self._parse_hex(row.get("NDRFECEn", "0"))

            # Detect mismatches (supported but not enabled)
            issues = []
            severity = "normal"

            if hdr_sup and not hdr_en:
                issues.append("HDR FEC: supported but not enabled")
            if ndr_sup and not ndr_en:
                issues.append("NDR FEC: supported but not enabled")
            if edr_sup and not edr_en:
                issues.append("EDR FEC: supported but not enabled")

            # Detect no FEC on high-speed links
            if fec_active == 0 and (hdr_sup or ndr_sup):
                issues.append("No FEC active on high-speed capable port")
                severity = "warning"
                mismatch_count += 1

            if issues and severity == "normal":
                severity = "info"

            record = {
                "NodeGUID": node_guid,
                "NodeName": node_name,
                "PortNumber": port_num,
                "FECActive": fec_active_str,
                "FECActiveCode": fec_active,
                "FDR10Supported": fdr10_sup > 0,
                "FDR10Enabled": fdr10_en > 0,
                "EDRSupported": edr_sup > 0,
                "EDREnabled": edr_en > 0,
                "EDR20Supported": edr20_sup > 0,
                "EDR20Enabled": edr20_en > 0,
                "HDRSupported": hdr_sup > 0,
                "HDREnabled": hdr_en > 0,
                "NDRSupported": ndr_sup > 0,
                "NDREnabled": ndr_en > 0,
                "Severity": severity,
                "Issues": "; ".join(issues) if issues else "",
            }
            records.append(record)

        # Build summary
        summary = {
            "total_ports": len(fec_df),
            "fec_active_distribution": dict(sorted(fec_active_distribution.items(), key=lambda x: -x[1])),
            "ports_without_fec": fec_active_distribution.get("No FEC", 0),
            "ports_with_rs_fec": sum(v for k, v in fec_active_distribution.items() if "RS-FEC" in k),
            "mismatch_count": mismatch_count,
            "hdr_capable_ports": sum(1 for r in records if r.get("HDRSupported")),
            "ndr_capable_ports": sum(1 for r in records if r.get("NDRSupported")),
        }

        # Sort by severity
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            r.get("NodeName", "")
        ))

        return FecModeResult(data=records[:2000], anomalies=None, summary=summary)

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
