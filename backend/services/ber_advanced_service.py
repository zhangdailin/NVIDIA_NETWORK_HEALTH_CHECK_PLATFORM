"""BER Advanced service - reads PHY_DB16 (mantissa/exponent format).

This service processes BER data from PHY_DB16 table which stores BER values
as mantissa/exponent integer pairs (field12-17), providing full precision
for extremely small BER values like 1.5e-254.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .ibdiagnet import read_index_table, read_table
from .topology_lookup import TopologyLookup

logger = logging.getLogger(__name__)

# BER thresholds
BER_CRITICAL_THRESHOLD = 1e-12  # 10^-12
BER_WARNING_THRESHOLD = 1e-14   # 10^-14


@dataclass
class BerAdvancedResult:
    """Result from BER Advanced analysis."""
    data: List[Dict[str, object]] = field(default_factory=list)
    anomalies: Optional[pd.DataFrame] = None
    summary: Dict[str, object] = field(default_factory=dict)


class BerAdvancedService:
    """Analyze BER data from PHY_DB16 (mantissa/exponent format)."""

    def __init__(self, dataset_root: Path):
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None
        self._topology: Optional[TopologyLookup] = None

    def run(self) -> BerAdvancedResult:
        """Run BER Advanced analysis using PHY_DB16 (mantissa/exponent format)."""
        # 读取PHY_DB16表 (包含mantissa/exponent格式的BER数据)
        phy_db16_df = self._try_read_table("PHY_DB16")

        if phy_db16_df.empty:
            logger.warning("PHY_DB16 table not found or empty")
            return BerAdvancedResult()

        logger.info(f"PHY_DB16 found! Rows: {len(phy_db16_df)}")

        # 检查是否有field12-17 (mantissa/exponent字段)
        required_fields = ['field12', 'field13', 'field14', 'field15', 'field16', 'field17']
        existing_fields = [f for f in required_fields if f in phy_db16_df.columns]

        if len(existing_fields) != 6:
            logger.error(f"PHY_DB16 missing required fields: {set(required_fields) - set(existing_fields)}")
            return BerAdvancedResult()

        logger.info("All mantissa/exponent fields present in PHY_DB16!")

        # 显示样本数据 (使用正确的列名: PortNum)
        sample_cols = ['NodeGuid', 'PortNum'] + existing_fields
        logger.info(f"Sample data:\n{phy_db16_df[sample_cols].head()}")

        # 处理PHY_DB16数据
        return self._process_phy_db16(phy_db16_df)

    def _process_phy_db16(self, df: pd.DataFrame) -> BerAdvancedResult:
        """Process PHY_DB16 table with mantissa/exponent format (IB-Analysis-Pro style)."""
        topology = self._get_topology()

        # 🆕 合并PM counters (SymbolErrorCounter等)
        df = self._merge_pm_counters(df)

        records = []

        # Statistics
        critical_ber_count = 0
        warning_ber_count = 0
        total_ports = 0
        ber_distribution: Dict[str, int] = defaultdict(int)

        logger.info(f"Processing {len(df)} rows from PHY_DB16")

        for _, row in df.iterrows():
            node_guid = str(row.get("NodeGuid", row.get("GUID", "")))
            port_num = self._safe_int(row.get("PortNum", row.get("PortNumber", 0)))

            # 提取mantissa/exponent pairs (field12-17)
            raw_mantissa = self._safe_int(row.get("field12", 0))
            raw_exponent = self._safe_int(row.get("field13", 0))
            eff_mantissa = self._safe_int(row.get("field14", 0))
            eff_exponent = self._safe_int(row.get("field15", 0))
            sym_mantissa = self._safe_int(row.get("field16", 0))
            sym_exponent = self._safe_int(row.get("field17", 0))

            # 计算BER字符串 (科学计数法) 和 Log10值
            raw_ber_str = self._me_to_sci(raw_mantissa, raw_exponent)
            eff_ber_str = self._me_to_sci(eff_mantissa, eff_exponent)
            sym_ber_str = self._me_to_sci(sym_mantissa, sym_exponent)

            raw_ber_log10 = self._me_to_log10(raw_mantissa, raw_exponent)
            eff_ber_log10 = self._me_to_log10(eff_mantissa, eff_exponent)
            sym_ber_log10 = self._me_to_log10(sym_mantissa, sym_exponent)

            # 🆕 获取SymbolErrorCounter (IB-Analysis-Pro logic)
            sym_err_counter = self._safe_int(row.get('SymbolErrorCounter', 0))
            sym_err_counter_ext = self._safe_int(row.get('SymbolErrorCounterExt', 0))
            total_sym_err = sym_err_counter + sym_err_counter_ext

            # 使用Raw/Effective/Symbol BER和SymbolErrorCounter判断严重程度
            severity = self._classify_ber_severity(
                raw_ber_log10, eff_ber_log10, sym_ber_log10, total_sym_err
            )

            # 分布统计 (基于log10)
            if sym_ber_log10 <= -50.0:
                magnitude = 999 # Perfect
            else:
                magnitude = int(abs(math.floor(sym_ber_log10)))

            if magnitude >= 15 or magnitude == 999:
                ber_distribution["<10^-15 (Normal)"] += 1
            elif magnitude < 9:
                ber_distribution[">=10^-9 (Critical)"] += 1
            elif magnitude <= 12:
                ber_distribution["10^-12 to 10^-9 (High)"] += 1
            elif magnitude < 15:
                ber_distribution["10^-15 to 10^-12 (Elevated)"] += 1
            else:
                ber_distribution["<10^-15 (Normal)"] += 1

            if severity == "critical":
                critical_ber_count += 1
            elif severity == "warning":
                warning_ber_count += 1

            total_ports += 1

            # 🆕 只添加异常端口 (过滤掉normal)
            if severity != "normal":
                # 获取节点名
                node_name = topology.node_label(node_guid) if topology else node_guid

                record = {
                    "NodeGUID": node_guid,
                    "NodeName": node_name,
                    "PortNumber": port_num,
                    "RawBER": raw_ber_str,           # "1.5e-254"
                    "EffectiveBER": eff_ber_str,     # "1.5e-254"
                    "SymbolBER": sym_ber_str,        # "1.5e-254"
                    "RawBERLog10": round(raw_ber_log10, 2) if raw_ber_log10 != 0 else 0,
                    "EffectiveBERLog10": round(eff_ber_log10, 2) if eff_ber_log10 != 0 else 0,
                    "SymbolBERLog10": round(sym_ber_log10, 2) if sym_ber_log10 != 0 else 0,
                    "Severity": severity,
                    "DataSource": "PHY_DB16",
                    "Magnitude": magnitude,  # 添加magnitude用于调试
                }
                records.append(record)

        summary = {
            "total_ports": total_ports,
            "critical_ber_count": critical_ber_count,
            "warning_ber_count": warning_ber_count,
            "healthy_ports": total_ports - critical_ber_count - warning_ber_count,
            "ber_distribution": dict(sorted(ber_distribution.items())),
            "data_source": "PHY_DB16 (mantissa/exponent format)",
        }

        # 按严重程度排序
        records.sort(key=lambda r: (
            0 if r["Severity"] == "critical" else 1 if r["Severity"] == "warning" else 2,
            -r.get("SymbolBERLog10", 0)  # More negative = better
        ))

        logger.info(f"PHY_DB16 processing complete:")
        logger.info(f"  Total ports scanned: {total_ports}")
        logger.info(f"  Critical (magnitude<14): {critical_ber_count}")
        logger.info(f"  Warning: {warning_ber_count}")
        logger.info(f"  Normal (filtered out): {total_ports - critical_ber_count - warning_ber_count}")
        logger.info(f"  Anomalies returned: {len(records)}")

        return BerAdvancedResult(data=records, anomalies=None, summary=summary)

    @staticmethod
    def _me_to_log10(mantissa: int, exponent: int) -> float:
        """Convert mantissa/exponent to log10 value.

        Formula: log10(BER) = log10(mantissa) - exponent
        Example: mantissa=15, exponent=254 → log10(15) - 254 = 1.176 - 254 = -252.824
        """
        if mantissa == 0:
            return -50.0  # Log10(0) should be a very small number, not 0.0
        try:
            return math.log10(abs(mantissa)) - exponent
        except (ValueError, OverflowError):
            return -50.0

    @staticmethod
    def _me_to_sci(mantissa: int, exponent: int) -> str:
        """Convert mantissa/exponent to scientific notation string.

        Example: mantissa=15, exponent=254 → "1.5e-253"
        """
        if mantissa == 0:
            return "0e+00"

        try:
            # Calculate log10 value
            log10_value = math.log10(abs(mantissa)) - exponent

            # Convert to scientific notation
            sci_exponent = int(math.floor(log10_value))      # -253
            sci_mantissa = 10 ** (log10_value - sci_exponent)  # 1.5

            return f"{sci_mantissa:.1f}e{sci_exponent:+03d}"  # "1.5e-253"
        except (ValueError, OverflowError):
            return "0e+00"

    @staticmethod
    def _classify_ber_severity(raw_log: float, eff_log: float, sym_log: float,
                              symbol_err_count: int = 1) -> str:
        """Classify BER severity based on log10 values and SymbolErrorCounter.

        Thresholds:
        - Critical: BER > 1e-12 (log > -12) AND SymbolErrorCounter >= 1
        - Warning: BER > 1e-15 (log > -15) OR Unusual BER relationship
        - Normal: BER <= 1e-15 (log <= -15)
        """
        # Exact zero or extremely healthy
        if sym_log <= -50.0:
            return "normal"

        # Check 1: "Unusual BER" - logical consistency check
        # Normal relationship: Raw BER >= Effective BER >= Symbol BER
        # In Log10 space: Raw Log >= Eff Log >= Sym Log
        if raw_log > -50.0 and eff_log > -50.0:
            # We allow for small floating point errors
            if not (raw_log >= eff_log - 0.01 and eff_log >= sym_log - 0.01):
                return "warning"

        # Check 2: High BER thresholds
        # Critical: BER > 1e-12 AND errors > 0
        if (sym_log > -12.0 or eff_log > -12.0) and (symbol_err_count >= 1):
            return "critical"

        # Warning: BER > 1e-15
        if (sym_log > -15.0 or eff_log > -15.0):
            return "warning"

        return "normal"

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

    def _merge_pm_counters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge PM (Performance Monitor) counters into PHY_DB16 data.

        This adds SymbolErrorCounter and SymbolErrorCounterExt fields which are
        used to validate BER anomalies (following IB-Analysis-Pro logic).
        """
        try:
            # 尝试读取PM表 (PERFQUERY_EXT_ERRORS或类似表)
            pm_df = self._try_read_table("PERFQUERY_EXT_ERRORS")

            if pm_df.empty:
                # 尝试其他可能的PM表名
                pm_df = self._try_read_table("PM")

            if pm_df.empty:
                logger.info("No PM counters table found, BER severity may be less accurate")
                # 添加默认的SymbolErrorCounter列 (假设所有端口都有错误)
                df['SymbolErrorCounter'] = 1
                df['SymbolErrorCounterExt'] = 0
                return df

            logger.info(f"Found PM counters table with {len(pm_df)} rows")

            # 统一列名
            pm_df.rename(columns={
                'NodeGuid': 'NodeGuid',
                'PortNum': 'PortNum'
            }, inplace=True)

            # 选择需要的列
            pm_key = ['NodeGuid', 'PortNum']
            fallback_cols = [
                'SymbolErrorCounter', 'SymbolErrorCounterExt',
                'SyncHeaderErrorCounter', 'PortRcvErrors',
                'PortRcvRemotePhysicalErrors', 'UnknownBlockCounter'
            ]

            available_cols = [c for c in fallback_cols if c in pm_df.columns]
            if not available_cols:
                logger.warning("PM table found but no counter columns available")
                df['SymbolErrorCounter'] = 1
                df['SymbolErrorCounterExt'] = 0
                return df

            pm_subset = pm_df[pm_key + available_cols].copy()

            # 去重 (保留最后一条)
            pm_subset.drop_duplicates(subset=pm_key, keep='last', inplace=True)

            # 合并到PHY_DB16
            df_merged = pd.merge(
                df,
                pm_subset,
                left_on=['NodeGuid', 'PortNum'],
                right_on=['NodeGuid', 'PortNum'],
                how='left'
            )

            # 填充缺失值为0
            for col in available_cols:
                if col in df_merged.columns:
                    df_merged[col] = df_merged[col].fillna(0)

            logger.info(f"Successfully merged PM counters: {available_cols}")
            return df_merged

        except Exception as e:
            logger.warning(f"Failed to merge PM counters: {e}")
            # 添加默认值
            df['SymbolErrorCounter'] = 1
            df['SymbolErrorCounterExt'] = 0
            return df
