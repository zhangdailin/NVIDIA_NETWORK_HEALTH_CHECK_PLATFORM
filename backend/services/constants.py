"""
共享常量定义
用于避免在多个服务中重复定义相同的常量
"""

# 速度优先级（用于 cable_service.py 和 xmit_service.py）
SPEED_PRIORITY = {
    'HDR': 5,
    'EDR': 4,
    'FDR': 3,
    'QDR': 2,
    'DDR': 1,
    'SDR': 0
}

# 宽度优先级
WIDTH_PRIORITY = {
    '12x': 5,
    '8x': 4,
    '4x': 3,
    '2x': 2,
    '1x': 1
}

# 温度阈值（摄氏度）
TEMP_WARNING_THRESHOLD = 70
TEMP_CRITICAL_THRESHOLD = 80

# 严重度级别
SEVERITY_CRITICAL = 'critical'
SEVERITY_WARNING = 'warning'
SEVERITY_INFO = 'info'
SEVERITY_OK = 'ok'
SEVERITY_NORMAL = 'normal'
