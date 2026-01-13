"""
基础分析服务类
提供所有分析服务的通用功能，避免代码重复
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, Dict, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseAnalysisService(ABC):
    """所有分析服务的基类"""

    def __init__(self, dataset_root: str):
        """
        初始化基础服务

        Args:
            dataset_root: 数据集根目录路径
        """
        self.dataset_root = dataset_root
        self._index_cache: Optional[pd.DataFrame] = None

    def _find_db_csv(self) -> Path:
        """查找 ibdiagnet2.db_csv 文件"""
        from .ibdiagnet_parser import find_db_csv
        return find_db_csv(self.dataset_root)

    def _get_index_table(self) -> pd.DataFrame:
        """
        获取索引表（带缓存）

        Returns:
            索引表 DataFrame
        """
        if self._index_cache is None:
            from .ibdiagnet_parser import read_index_table
            db_csv = self._find_db_csv()
            self._index_cache = read_index_table(db_csv)
        return self._index_cache

    def _read_table(self, table_name: str) -> pd.DataFrame:
        """
        读取指定表格

        Args:
            table_name: 表格名称

        Returns:
            表格数据 DataFrame
        """
        from .ibdiagnet_parser import read_table
        db_csv = self._find_db_csv()
        return read_table(db_csv, table_name)

    def _try_read_table(self, table_name: str) -> pd.DataFrame:
        """
        安全读取表格，失败时返回空 DataFrame

        Args:
            table_name: 表格名称

        Returns:
            表格数据 DataFrame，失败时返回空 DataFrame
        """
        try:
            index_table = self._get_index_table()
            if table_name not in index_table.index:
                logger.debug(f"Table '{table_name}' not found in index")
                return pd.DataFrame()
            return self._read_table(table_name)
        except Exception as e:
            logger.debug(f"Could not read table '{table_name}': {e}")
            return pd.DataFrame()

    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        """
        安全转换为整数

        Args:
            value: 要转换的值
            default: 转换失败时的默认值

        Returns:
            转换后的整数值
        """
        try:
            if pd.isna(value):
                return default
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        """
        安全转换为浮点数

        Args:
            value: 要转换的值
            default: 转换失败时的默认值

        Returns:
            转换后的浮点数值
        """
        try:
            if pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def safe_bool(value: Any, default: bool = False) -> bool:
        """
        安全转换为布尔值

        Args:
            value: 要转换的值
            default: 转换失败时的默认值

        Returns:
            转换后的布尔值
        """
        try:
            if pd.isna(value):
                return default
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', 'yes', '1', 'on')
            return bool(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def normalize_guid(guid: Any) -> str:
        """
        规范化 GUID 格式

        Args:
            guid: GUID 值

        Returns:
            规范化后的 GUID 字符串
        """
        if pd.isna(guid):
            return ''
        guid_str = str(guid).strip()
        if guid_str.startswith('0x'):
            return guid_str
        return f'0x{guid_str}'

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """
        执行分析服务

        子类必须实现此方法

        Returns:
            分析结果字典，通常包含:
            - data: 分析数据列表
            - summary: 摘要信息字典
            - anomalies: 异常数据（可选）
        """
        pass
