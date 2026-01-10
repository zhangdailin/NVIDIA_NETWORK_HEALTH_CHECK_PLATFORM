"""Comprehensive warnings service for parsing all ibdiagnet WARNING tables.

Handles 26+ warning table types:
- Core warnings: FW_CHECK, PCI_DEGRADATION, SYMBOL_BER_CHECK, CABLE_REPORT, etc.
- PHY_DB*_RETRIEVING: Physical layer diagnostic collection failures (16+ tables)
- P_DB*_RETRIEVING: Performance database collection failures
- SHARP_VERIFY_TRAPS_LIDS: SHARP protocol warnings
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)


# Warning table definitions with severity mappings
WARNING_TABLE_CONFIG = {
    # ===== Core Diagnostic Warnings =====
    "WARNINGS_FW_CHECK": {
        "category": "firmware",
        "events": {
            "NODE_WRONG_FW_VERSION": {"severity": "warning", "title": "固件版本不一致"},
            "NODE_FW_MISMATCH": {"severity": "warning", "title": "固件不匹配"},
        },
        "default_severity": "warning",
    },
    "WARNINGS_PCI_DEGRADATION_CHECK": {
        "category": "pci",
        "events": {
            "DEGRADATION": {"severity": "critical", "title": "PCI速度降级"},
            "PCI_SPEED_DOWNGRADE": {"severity": "critical", "title": "PCI速度降级"},
            "PCI_WIDTH_DOWNGRADE": {"severity": "warning", "title": "PCI宽度降级"},
        },
        "default_severity": "critical",
    },
    "WARNINGS_PORTS_COUNTERS_DIFFERENCE_CHECK_(DURING_RUN)": {
        "category": "counters",
        "events": {
            "PM_COUNTER_INCREASED": {"severity": "warning", "title": "端口计数器增长"},
            "ERROR_COUNTER_INCREASED": {"severity": "critical", "title": "错误计数器增长"},
        },
        "default_severity": "warning",
    },
    "WARNINGS_DUPLICATED_NODE_DESCRIPTION_DETECTION": {
        "category": "topology",
        "events": {
            "NODE_DUPLICATED_NODE_DESC": {"severity": "info", "title": "重复节点描述"},
        },
        "default_severity": "info",
    },
    "WARNINGS_CABLE_REPORT": {
        "category": "cable",
        "events": {
            "PRTL_ROUND_TRIP_LATENCY": {"severity": "info", "title": "线缆测量问题"},
            "CABLE_LENGTH_MISMATCH": {"severity": "warning", "title": "线缆长度不匹配"},
            "CABLE_VENDOR_MISMATCH": {"severity": "info", "title": "线缆厂商不匹配"},
            "CABLE_COMPLIANCE_ISSUE": {"severity": "warning", "title": "线缆合规性问题"},
        },
        "default_severity": "info",
    },
    "WARNINGS_SYMBOL_BER_CHECK": {
        "category": "ber",
        "events": {
            "BER_THRESHOLD_EXCEEDED": {"severity": "critical", "title": "BER超过阈值"},
            "BER_NEAR_THRESHOLD": {"severity": "warning", "title": "BER接近阈值"},
            "BER_RS_FEC_EXCESSIVE_ERRORS": {"severity": "critical", "title": "RS-FEC纠错过多"},
            "BER_RS_FEC_HIGH_ERRORS": {"severity": "warning", "title": "RS-FEC纠错偏高"},
            "BER_NO_THRESHOLD_IS_SUPPORTED": {"severity": "info", "title": "不支持BER阈值"},
        },
        "default_severity": "info",
    },
    # ===== SHARP Protocol Warnings =====
    "WARNINGS_SHARP_VERIFY_TRAPS_LIDS": {
        "category": "sharp",
        "events": {
            "TRAP_LID_MISMATCH": {"severity": "warning", "title": "SHARP Trap LID不匹配"},
            "SHARP_CONFIG_ERROR": {"severity": "critical", "title": "SHARP配置错误"},
        },
        "default_severity": "warning",
    },
}

# PHY_DB*_RETRIEVING tables - dynamic configuration for all PHY database collection failures
PHY_DB_RETRIEVING_TABLES = [
    "WARNINGS_PHY_DB4_RETRIEVING",
    "WARNINGS_PHY_DB6_RETRIEVING",
    "WARNINGS_PHY_DB7_RETRIEVING",
    "WARNINGS_PHY_DB18_RETRIEVING",
    "WARNINGS_PHY_DB20_RETRIEVING",
    "WARNINGS_PHY_DB23_RETRIEVING",
    "WARNINGS_PHY_DB27_RETRIEVING",
    "WARNINGS_PHY_DB28_RETRIEVING",
    "WARNINGS_PHY_DB29_RETRIEVING",
    "WARNINGS_PHY_DB30_RETRIEVING",
    "WARNINGS_PHY_DB35_RETRIEVING",
    "WARNINGS_PHY_DB36_RETRIEVING",
    "WARNINGS_PHY_DB37_RETRIEVING",
    "WARNINGS_PHY_DB38_RETRIEVING",
    "WARNINGS_PHY_DB39_RETRIEVING",
    "WARNINGS_PHY_DB110_RETRIEVING",
]

# P_DB*_RETRIEVING tables - performance database collection failures
P_DB_RETRIEVING_TABLES = [
    "WARNINGS_P_DB6_RETRIEVING",
    "WARNINGS_P_DB7_RETRIEVING",
    "WARNINGS_P_DB8_RETRIEVING",
]

# Add dynamic configs for PHY_DB retrieving tables
for phy_table in PHY_DB_RETRIEVING_TABLES:
    db_num = re.search(r"PHY_DB(\d+)", phy_table)
    db_id = db_num.group(1) if db_num else "?"
    WARNING_TABLE_CONFIG[phy_table] = {
        "category": "phy_collection",
        "events": {
            "RETRIEVING_FAILED": {"severity": "warning", "title": f"PHY_DB{db_id}数据采集失败"},
            "TIMEOUT": {"severity": "warning", "title": f"PHY_DB{db_id}采集超时"},
            "NOT_SUPPORTED": {"severity": "info", "title": f"PHY_DB{db_id}不支持"},
        },
        "default_severity": "warning",
    }

# Add dynamic configs for P_DB retrieving tables
for p_table in P_DB_RETRIEVING_TABLES:
    db_num = re.search(r"P_DB(\d+)", p_table)
    db_id = db_num.group(1) if db_num else "?"
    WARNING_TABLE_CONFIG[p_table] = {
        "category": "perf_collection",
        "events": {
            "RETRIEVING_FAILED": {"severity": "warning", "title": f"P_DB{db_id}性能数据采集失败"},
            "TIMEOUT": {"severity": "warning", "title": f"P_DB{db_id}采集超时"},
            "NOT_SUPPORTED": {"severity": "info", "title": f"P_DB{db_id}不支持"},
        },
        "default_severity": "warning",
    }


@dataclass
class WarningItem:
    """Single warning item from ibdiagnet."""
    table_name: str
    category: str
    severity: str
    event_name: str
    title: str
    node_guid: str
    port_guid: str
    port_number: int
    summary: str
    scope: str = "PORT"


@dataclass
class WarningsSummary:
    """Summary of all warnings by category."""
    total_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_event: Dict[str, int] = field(default_factory=dict)


@dataclass
class WarningsAnalysis:
    """Complete warnings analysis result."""
    warnings: List[WarningItem]
    summary: WarningsSummary
    firmware_summary: Optional[Dict] = None
    pci_summary: Optional[Dict] = None
    counters_summary: Optional[Dict] = None


class WarningsService:
    """Parse all WARNING tables from ibdiagnet db_csv."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> WarningsAnalysis:
        """Run the warnings analysis."""
        all_warnings: List[WarningItem] = []

        index_table = self._get_index_table()

        for table_name, config in WARNING_TABLE_CONFIG.items():
            if table_name not in index_table.index:
                continue

            try:
                df = self._read_table(table_name)
                if df.empty:
                    continue

                warnings = self._parse_warning_table(df, table_name, config)
                all_warnings.extend(warnings)
                logger.info(f"Parsed {len(warnings)} warnings from {table_name}")
            except Exception as e:
                logger.warning(f"Failed to parse {table_name}: {e}")

        summary = self._build_summary(all_warnings)
        firmware_summary = self._build_firmware_summary()
        pci_summary = self._build_pci_summary()
        counters_summary = self._build_counters_summary()

        return WarningsAnalysis(
            warnings=all_warnings,
            summary=summary,
            firmware_summary=firmware_summary,
            pci_summary=pci_summary,
            counters_summary=counters_summary,
        )

    def _get_index_table(self) -> pd.DataFrame:
        """Get the index table, cached."""
        if self._index_cache is None:
            db_csv = self._find_db_csv()
            self._index_cache = read_index_table(db_csv)
        return self._index_cache

    def _read_table(self, table_name: str) -> pd.DataFrame:
        """Read a table from db_csv."""
        db_csv = self._find_db_csv()
        return read_table(db_csv, table_name, self._get_index_table())

    def _find_db_csv(self) -> Path:
        """Find the db_csv file."""
        matches = sorted(self.dataset_root.glob("*.db_csv"))
        if not matches:
            raise FileNotFoundError(f"No .db_csv files under {self.dataset_root}")
        return matches[0]

    def _parse_warning_table(
        self, df: pd.DataFrame, table_name: str, config: Dict
    ) -> List[WarningItem]:
        """Parse a warning table into WarningItem list."""
        warnings = []
        category = config["category"]
        events = config.get("events", {})
        default_severity = config.get("default_severity", "info")

        for _, row in df.iterrows():
            event_name = str(row.get("EventName", "UNKNOWN"))
            event_config = events.get(event_name, {})
            severity = event_config.get("severity", default_severity)
            title = event_config.get("title", event_name)

            node_guid = self._normalize_guid(row.get("NodeGUID", ""))
            port_guid = self._normalize_guid(row.get("PortGUID", ""))

            try:
                port_number = int(row.get("PortNumber", 0))
            except (ValueError, TypeError):
                port_number = 0

            summary = str(row.get("Summary", "")).strip('"')
            scope = str(row.get("Scope", "PORT"))

            warnings.append(WarningItem(
                table_name=table_name,
                category=category,
                severity=severity,
                event_name=event_name,
                title=title,
                node_guid=node_guid,
                port_guid=port_guid,
                port_number=port_number,
                summary=summary,
                scope=scope,
            ))

        return warnings

    def _normalize_guid(self, guid: str) -> str:
        """Normalize GUID format."""
        guid = str(guid)
        if guid.startswith("0x"):
            try:
                return hex(int(guid, 16))
            except (ValueError, OverflowError):
                return guid
        return guid

    def _build_summary(self, warnings: List[WarningItem]) -> WarningsSummary:
        """Build summary statistics."""
        summary = WarningsSummary()
        summary.total_count = len(warnings)

        for w in warnings:
            if w.severity == "critical":
                summary.critical_count += 1
            elif w.severity == "warning":
                summary.warning_count += 1
            else:
                summary.info_count += 1

            summary.by_category[w.category] = summary.by_category.get(w.category, 0) + 1
            summary.by_event[w.event_name] = summary.by_event.get(w.event_name, 0) + 1

        return summary

    def _build_firmware_summary(self) -> Optional[Dict]:
        """Build firmware version summary."""
        try:
            index_table = self._get_index_table()
            if "WARNINGS_FW_CHECK" not in index_table.index:
                return None

            df = self._read_table("WARNINGS_FW_CHECK")
            if df.empty:
                return None

            versions = {}
            latest_version = None

            for _, row in df.iterrows():
                summary = str(row.get("Summary", ""))

                # Extract current version
                current_match = re.search(r'has FW version (\S+)', summary)
                if current_match:
                    ver = current_match.group(1)
                    versions[ver] = versions.get(ver, 0) + 1

                # Extract latest version
                if latest_version is None:
                    latest_match = re.search(r'latest FW version[^0-9]*(\S+)', summary)
                    if latest_match:
                        latest_version = latest_match.group(1)

            return {
                "total_affected": len(df),
                "versions": versions,
                "latest_version": latest_version,
                "unique_versions": len(versions),
            }
        except Exception as e:
            logger.warning(f"Failed to build firmware summary: {e}")
            return None

    def _build_pci_summary(self) -> Optional[Dict]:
        """Build PCI degradation summary."""
        try:
            index_table = self._get_index_table()
            if "WARNINGS_PCI_DEGRADATION_CHECK" not in index_table.index:
                return None

            df = self._read_table("WARNINGS_PCI_DEGRADATION_CHECK")
            if df.empty:
                return None

            degradations = []
            for _, row in df.iterrows():
                summary = str(row.get("Summary", ""))
                # Extract speed info
                speed_match = re.search(r'enabled speed is (\S+) active is (\S+)', summary)
                if speed_match:
                    degradations.append({
                        "node_guid": self._normalize_guid(row.get("NodeGUID", "")),
                        "port_number": row.get("PortNumber", 0),
                        "enabled_speed": speed_match.group(1),
                        "active_speed": speed_match.group(2),
                    })

            return {
                "total_affected": len(df),
                "degradations": degradations,
            }
        except Exception as e:
            logger.warning(f"Failed to build PCI summary: {e}")
            return None

    def _build_counters_summary(self) -> Optional[Dict]:
        """Build port counters summary."""
        try:
            index_table = self._get_index_table()
            table_name = "WARNINGS_PORTS_COUNTERS_DIFFERENCE_CHECK_(DURING_RUN)"
            if table_name not in index_table.index:
                return None

            df = self._read_table(table_name)
            if df.empty:
                return None

            counters = {}
            for _, row in df.iterrows():
                summary = str(row.get("Summary", ""))
                # Extract counter name
                counter_match = re.search(r'"(\w+)" increased', summary)
                if counter_match:
                    counter_name = counter_match.group(1)
                    counters[counter_name] = counters.get(counter_name, 0) + 1

            return {
                "total_affected": len(df),
                "counters": counters,
            }
        except Exception as e:
            logger.warning(f"Failed to build counters summary: {e}")
            return None

    def to_dict_list(self) -> List[Dict]:
        """Run analysis and convert to list of dicts for API response."""
        analysis = self.run()
        return [
            {
                "category": w.category,
                "severity": w.severity,
                "event_name": w.event_name,
                "title": w.title,
                "node_guid": w.node_guid,
                "port_number": w.port_number,
                "summary": w.summary,
                "scope": w.scope,
            }
            for w in analysis.warnings
        ]

    def get_summary_dict(self) -> Dict:
        """Get summary as dict for API response."""
        analysis = self.run()
        return {
            "total": analysis.summary.total_count,
            "critical": analysis.summary.critical_count,
            "warning": analysis.summary.warning_count,
            "info": analysis.summary.info_count,
            "by_category": analysis.summary.by_category,
            "by_event": analysis.summary.by_event,
            "firmware": analysis.firmware_summary,
            "pci": analysis.pci_summary,
            "counters": analysis.counters_summary,
        }

    def get_warnings_by_category(self) -> Dict[str, List[Dict]]:
        """Get warnings grouped by category for merging into existing tabs."""
        analysis = self.run()
        grouped: Dict[str, List[Dict]] = {
            "firmware": [],       # -> HCA tab
            "pci": [],            # -> HCA tab
            "counters": [],       # -> Xmit tab
            "topology": [],       # -> Overview
            "cable": [],          # -> Cable tab
            "ber": [],            # -> BER tab
            "sharp": [],          # -> SHARP tab
            "link": [],           # -> Links tab
            "phy_collection": [], # -> PHY Diagnostics tab
            "perf_collection": [],# -> PM Delta tab
        }
        for w in analysis.warnings:
            if w.category in grouped:
                grouped[w.category].append({
                    "severity": w.severity,
                    "event_name": w.event_name,
                    "title": w.title,
                    "node_guid": w.node_guid,
                    "port_number": w.port_number,
                    "summary": w.summary,
                    "scope": w.scope,
                })
        return grouped

    def get_collection_failures_summary(self) -> Dict[str, object]:
        """Get summary of data collection failures (PHY_DB and P_DB retrieving errors)."""
        phy_failures: Dict[str, int] = defaultdict(int)
        perf_failures: Dict[str, int] = defaultdict(int)
        total_phy_ports = 0
        total_perf_ports = 0

        index_table = self._get_index_table()

        # Process PHY_DB retrieving tables
        for table_name in PHY_DB_RETRIEVING_TABLES:
            if table_name not in index_table.index:
                continue
            try:
                df = self._read_table(table_name)
                if not df.empty:
                    db_match = re.search(r"PHY_DB(\d+)", table_name)
                    db_id = f"PHY_DB{db_match.group(1)}" if db_match else table_name
                    phy_failures[db_id] = len(df)
                    total_phy_ports += len(df)
            except Exception as e:
                logger.debug(f"Could not read {table_name}: {e}")

        # Process P_DB retrieving tables
        for table_name in P_DB_RETRIEVING_TABLES:
            if table_name not in index_table.index:
                continue
            try:
                df = self._read_table(table_name)
                if not df.empty:
                    db_match = re.search(r"P_DB(\d+)", table_name)
                    db_id = f"P_DB{db_match.group(1)}" if db_match else table_name
                    perf_failures[db_id] = len(df)
                    total_perf_ports += len(df)
            except Exception as e:
                logger.debug(f"Could not read {table_name}: {e}")

        return {
            "phy_db_failures": dict(sorted(phy_failures.items(), key=lambda x: -x[1])),
            "perf_db_failures": dict(sorted(perf_failures.items(), key=lambda x: -x[1])),
            "total_phy_collection_failures": total_phy_ports,
            "total_perf_collection_failures": total_perf_ports,
            "phy_tables_with_failures": len(phy_failures),
            "perf_tables_with_failures": len(perf_failures),
        }
