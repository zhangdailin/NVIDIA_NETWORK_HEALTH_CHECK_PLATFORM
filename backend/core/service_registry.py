"""
服务注册器 - 依赖注入模式
统一管理所有分析服务的实例化和依赖
"""

from typing import Dict, Type, Any
from pathlib import Path

# 服务接口
class AnalysisServiceInterface:
    """所有分析服务的基类接口"""

    def analyze(self, dataset, **kwargs) -> Dict[str, Any]:
        """分析方法 - 子类必须实现"""
        raise NotImplementedError


class ServiceRegistry:
    """
    服务注册器

    优势：
    - 单例模式，避免重复实例化
    - 延迟加载，按需创建服务
    - 统一的服务生命周期管理
    """

    _instance = None
    _services: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, service_name: str, service_class: Type, *args, **kwargs):
        """注册服务"""
        if service_name not in self._services:
            self._services[service_name] = {
                'class': service_class,
                'args': args,
                'kwargs': kwargs,
                'instance': None
            }

    def get(self, service_name: str) -> Any:
        """获取服务实例（延迟加载）"""
        if service_name not in self._services:
            raise ValueError(f"Service '{service_name}' not registered")

        service_config = self._services[service_name]

        # 延迟实例化
        if service_config['instance'] is None:
            service_config['instance'] = service_config['class'](
                *service_config['args'],
                **service_config['kwargs']
            )

        return service_config['instance']

    def clear(self):
        """清理所有服务实例"""
        self._services.clear()


# 全局注册器实例
registry = ServiceRegistry()


def register_all_services():
    """
    注册所有分析服务
    在应用启动时调用一次
    """
    from services.cable_service import CableService
    from services.ber_service import BerService
    from services.hca_service import HcaService
    from services.fan_service import FanService
    from services.switch_service import SwitchService
    # ... 其他服务导入

    # 注册服务
    registry.register('cable', CableService)
    registry.register('ber', BerService)
    registry.register('hca', HcaService)
    registry.register('fan', FanService)
    registry.register('switch', SwitchService)
    # ... 其他服务注册

    print(f"✅ 已注册 {len(registry._services)} 个分析服务")


def get_service(service_name: str):
    """快捷方法 - 获取服务"""
    return registry.get(service_name)
