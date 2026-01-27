"""阈值配置管理器

支持：
- 从YAML文件加载配置
- 环境变量控制配置路径
- 配置文件损坏时降级到硬编码默认值
- 点号路径访问配置值
"""

from pathlib import Path
from typing import Any, Dict, Optional
import yaml
import logging
import os

logger = logging.getLogger(__name__)


class ThresholdConfig:
    """全局阈值配置管理器（单例模式）"""

    _instance: Optional['ThresholdConfig'] = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置文件"""
        # 1. 尝试从环境变量读取自定义配置路径
        config_path = os.getenv("THRESHOLD_CONFIG_PATH")

        # 2. 如果未设置,使用默认配置
        if not config_path:
            config_path = Path(__file__).parent / "default_thresholds.yaml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}, 使用硬编码默认值")
            self._config = self._get_hardcoded_defaults()
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"成功加载配置文件: {config_path}")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}, 使用硬编码默认值")
            self._config = self._get_hardcoded_defaults()

    def _get_hardcoded_defaults(self) -> Dict[str, Any]:
        """硬编码默认值(向后兼容)"""
        return {
            "health_score": {
                "category_weights": {
                    "ber": 25, "errors": 25, "congestion": 20,
                    "latency": 10, "balance": 5, "config": 13, "anomaly": 2
                },
                "severity_multipliers": {"critical": 3.0, "warning": 1.5, "info": 0.5},
                "grade_boundaries": {"A": 90, "B": 80, "C": 70, "D": 60}
            },
            "temperature": {"warning": 70, "critical": 80, "margin_percentage": 10},
            "link_health": {
                "link_down": {"threshold": 0},
                "link_recovery": {"warning": 3, "critical": 10}
            },
            "cable": {
                "temperature": {"warning": 70, "critical": 80},
                "length_limits": {
                    "fiber": {"hdr": 1000, "fdr": 2000},
                    "copper": {"enabled": False, "hdr": 5, "fdr": 3}
                },
                "max_display_rows": 2000
            }
        }

    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置值,支持点号路径访问

        示例:
            config.get("temperature.warning")  # 返回70
            config.get("health_score.category_weights.ber")  # 返回25
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def reload(self):
        """重新加载配置文件"""
        self._load_config()
        logger.info("配置已重新加载")


# 全局配置实例
threshold_config = ThresholdConfig()
