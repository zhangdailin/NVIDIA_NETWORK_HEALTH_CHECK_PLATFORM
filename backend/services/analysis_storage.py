"""
分析结果存储服务
使用 JSON 文件存储分析结果，支持保存、查询和历史记录
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# 存储目录
STORAGE_DIR = Path("results")
STORAGE_DIR.mkdir(exist_ok=True)


def save_analysis(
    task_id: str,
    analysis_data: Dict,
    file_name: str,
    file_type: str
) -> Dict:
    """
    保存分析结果到 JSON 文件

    Args:
        task_id: 任务ID
        analysis_data: 分析数据
        file_name: 原始文件名
        file_type: 文件类型 ('ibdiagnet' | 'csv')

    Returns:
        保存的记录信息
    """
    record = {
        'task_id': task_id,
        'file_name': file_name,
        'file_type': file_type,
        'created_at': datetime.now().isoformat(),
        'status': 'completed',
        'analysis_data': analysis_data
    }

    file_path = STORAGE_DIR / f"{task_id}.json"

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        logger.info(f"Analysis saved: {task_id} ({file_name})")
        return {
            'task_id': task_id,
            'file_name': file_name,
            'file_type': file_type,
            'created_at': record['created_at'],
            'status': 'completed'
        }
    except Exception as e:
        logger.error(f"Failed to save analysis {task_id}: {e}")
        raise


def get_analysis(task_id: str) -> Optional[Dict]:
    """
    获取分析结果

    Args:
        task_id: 任务ID

    Returns:
        分析记录，如果不存在返回 None
    """
    file_path = STORAGE_DIR / f"{task_id}.json"

    if not file_path.exists():
        logger.warning(f"Analysis not found: {task_id}")
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"Analysis loaded: {task_id}")
        return data
    except Exception as e:
        logger.error(f"Failed to load analysis {task_id}: {e}")
        return None


def get_history(limit: int = 10) -> List[Dict]:
    """
    获取历史分析记录列表

    Args:
        limit: 返回的最大记录数

    Returns:
        历史记录列表，按时间倒序排列
    """
    records = []

    try:
        # 获取所有 JSON 文件，按修改时间排序
        json_files = sorted(
            STORAGE_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for file_path in json_files[:limit]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 只返回摘要信息，不包含完整的 analysis_data
                records.append({
                    'task_id': data.get('task_id', file_path.stem),
                    'file_name': data.get('file_name', 'Unknown'),
                    'file_type': data.get('file_type', 'unknown'),
                    'created_at': data.get('created_at', ''),
                    'status': data.get('status', 'completed')
                })
            except Exception as e:
                logger.warning(f"Failed to read {file_path.name}: {e}")
                continue

        logger.info(f"Loaded {len(records)} history records")
        return records
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return []


def delete_analysis(task_id: str) -> bool:
    """
    删除分析结果

    Args:
        task_id: 任务ID

    Returns:
        是否删除成功
    """
    file_path = STORAGE_DIR / f"{task_id}.json"

    if not file_path.exists():
        logger.warning(f"Analysis not found for deletion: {task_id}")
        return False

    try:
        file_path.unlink()
        logger.info(f"Analysis deleted: {task_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete analysis {task_id}: {e}")
        return False


def cleanup_old_analyses(max_age_days: int = 7) -> int:
    """
    清理超过指定天数的分析结果

    Args:
        max_age_days: 最大保留天数

    Returns:
        清理的文件数
    """
    cutoff_time = datetime.now() - timedelta(days=max_age_days)
    removed_count = 0

    try:
        for file_path in STORAGE_DIR.glob("*.json"):
            try:
                # 检查文件修改时间
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                if file_mtime < cutoff_time:
                    file_path.unlink()
                    removed_count += 1
                    logger.info(f"Cleaned up old analysis: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {file_path.name}: {e}")
                continue

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old analysis files")

        return removed_count
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return 0


def get_storage_stats() -> Dict:
    """
    获取存储统计信息

    Returns:
        存储统计信息
    """
    try:
        json_files = list(STORAGE_DIR.glob("*.json"))
        total_size = sum(f.stat().st_size for f in json_files)

        return {
            'total_analyses': len(json_files),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'storage_dir': str(STORAGE_DIR.absolute())
        }
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        return {
            'total_analyses': 0,
            'total_size_mb': 0,
            'storage_dir': str(STORAGE_DIR.absolute())
        }
