"""
分析进度跟踪服务
用于在分析过程中实时更新和查询进度信息
"""
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# 全局进度字典，存储所有正在进行和已完成的分析任务进度
analysis_progress: Dict[str, Dict] = {}


def update_progress(
    task_id: str,
    stage: str,
    progress: int,
    current_service: str = '',
    message: str = ''
) -> None:
    """
    更新分析进度

    Args:
        task_id: 任务ID
        stage: 阶段 ('uploading' | 'analyzing' | 'completed' | 'error')
        progress: 进度百分比 (0-100)
        current_service: 当前正在分析的服务名称
        message: 进度消息
    """
    analysis_progress[task_id] = {
        'stage': stage,
        'progress': min(100, max(0, progress)),  # 确保在 0-100 范围内
        'current_service': current_service,
        'message': message,
        'updated_at': datetime.now().isoformat()
    }

    logger.info(f"Progress updated for {task_id}: {stage} - {progress}% - {message}")


def get_progress(task_id: str) -> Dict:
    """
    获取分析进度

    Args:
        task_id: 任务ID

    Returns:
        进度信息字典
    """
    if task_id not in analysis_progress:
        return {
            'stage': 'unknown',
            'progress': 0,
            'current_service': '',
            'message': '未找到分析任务',
            'updated_at': datetime.now().isoformat()
        }

    return analysis_progress[task_id]


def clear_progress(task_id: str) -> None:
    """
    清除指定任务的进度信息

    Args:
        task_id: 任务ID
    """
    if task_id in analysis_progress:
        del analysis_progress[task_id]
        logger.info(f"Progress cleared for {task_id}")


def cleanup_old_progress(max_age_hours: int = 24) -> int:
    """
    清理超过指定时间的进度记录

    Args:
        max_age_hours: 最大保留时间（小时）

    Returns:
        清理的记录数
    """
    from datetime import timedelta

    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    removed_count = 0

    task_ids_to_remove = []
    for task_id, progress_data in analysis_progress.items():
        try:
            updated_at = datetime.fromisoformat(progress_data['updated_at'])
            if updated_at < cutoff_time:
                task_ids_to_remove.append(task_id)
        except (KeyError, ValueError) as e:
            logger.warning(f"Invalid progress data for {task_id}: {e}")
            task_ids_to_remove.append(task_id)

    for task_id in task_ids_to_remove:
        del analysis_progress[task_id]
        removed_count += 1

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old progress records")

    return removed_count


# 服务名称到中文描述的映射
SERVICE_NAMES = {
    'cable': '电缆数据',
    'ber': 'BER 数据',
    'xmit': '拥塞数据',
    'link_oscillation': '链路振荡数据',
    'hca': 'HCA 设备数据',
    'fan': '风扇数据',
    'histogram': '延迟数据',
    'switch': '交换机数据',
    'routing': '路由数据',
    'qos': 'QoS 数据',
    'sm_info': 'SM 信息',
    'port_hierarchy': '端口层级数据',
    'mlnx_counters': 'Mellanox 计数器',
    'pm_delta': 'PM Delta 数据',
    'vports': '虚拟端口数据',
    'pkey': 'PKey 数据',
    'system_info': '系统信息',
    'extended_port_info': '扩展端口信息',
    'ar_info': 'AR 信息',
    'sharp': 'SHARP 数据',
    'fec_mode': 'FEC 模式',
    'phy_diagnostics': '物理诊断数据',
    'neighbors': '邻居信息',
    'buffer_histogram': '缓冲区直方图',
    'extended_node_info': '扩展节点信息',
    'extended_switch_info': '扩展交换机信息',
    'power_sensors': '电源传感器数据',
    'routing_config': '路由配置',
    'temp_alerts': '温度告警',
    'pci_performance': 'PCIe 性能',
    'per_lane_performance': '每通道性能',
    'n2n_security': 'N2N 安全',
}


def get_service_display_name(service_key: str) -> str:
    """
    获取服务的显示名称

    Args:
        service_key: 服务键名

    Returns:
        中文显示名称
    """
    return SERVICE_NAMES.get(service_key, service_key)
