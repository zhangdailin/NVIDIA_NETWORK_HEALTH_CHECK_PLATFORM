# 服务超时问题全面诊断与修复

## 问题概述

Cable 分析显示"无故障数据"，但后端日志显示找到了 20 个温度警告。经过深入分析，发现是服务超时导致的数据丢失问题。

## 根本原因分析

### 1. 导入顺序问题

**问题代码**（修复前的 `main.py`）：
```python
from api import router, executor  # 第5行：先导入api模块
from dotenv import load_dotenv    # 第11行：后导入dotenv
load_dotenv()                     # 第14行：加载环境变量
```

**导入链**：
```
main.py
  └─> api.py
       └─> analysis_service.py
            └─> 读取 os.getenv("SERVICE_TIMEOUT_SECONDS", "60")
```

**问题**：
- 当 `api` 模块被导入时，`analysis_service.py` 立即执行
- 此时 `load_dotenv()` 还没有被调用
- `os.getenv("SERVICE_TIMEOUT_SECONDS")` 返回 `None`
- 使用默认值 60 秒

### 2. 服务执行流程

**并行启动，按序等待**（`analysis_service.py:236-253`）：

```python
# 1. 所有服务并行启动
for name, log_message, runner in service_specs:
    logger.info(log_message)
    service_futures[name] = loop.run_in_executor(executor, runner, target_dir)

# 2. 按顺序等待每个服务完成
for (name, _, _), future in zip(service_specs, service_futures.values()):
    try:
        result = await asyncio.wait_for(future, timeout=SERVICE_TIMEOUT_SECONDS)
        results.append(result)
    except asyncio.TimeoutError:
        logger.warning(f"Service {name} timed out after {SERVICE_TIMEOUT_SECONDS}s, using empty result")
        results.append(self._get_empty_service_result(name))
```

**Cable 服务的执行时间线**：

| 时间 | 事件 | 说明 |
|------|------|------|
| 00:57:13 | Cable 服务启动 | 并行启动，开始加载数据 |
| 00:58:13 | Cable 超时 (60s) | 等待超时，返回空结果 |
| 00:58:13-17 | Cable 继续运行 | 后台继续执行，最终完成 |
| 00:58:17 | Cable 完成 | 找到 20 条温度警告，但数据已被丢弃 |

### 3. 数据流向

```
Cable Service (超时)
  └─> 返回空结果 EmptyAnalysis()
       └─> cable_rows = []
            └─> payload["cable_issue_rows"] = []
                 └─> 前端收到空数组
                      └─> 显示"无故障数据"
```

## 修复方案

### 修复 1：调整导入顺序

**文件**：`backend/main.py`

**修改前**：
```python
from api import router, executor
from dotenv import load_dotenv
load_dotenv()
```

**修改后**：
```python
from dotenv import load_dotenv
load_dotenv()  # 先加载环境变量
from api import router, executor  # 再导入其他模块
```

**完整代码**（`main.py:1-16`）：
```python
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
from datetime import datetime
from pathlib import Path
import atexit
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing other modules
load_dotenv()

# Import after loading environment variables
from api import router, executor
from middleware import RateLimitMiddleware, RequestIDMiddleware
```

### 修复 2：从环境变量读取超时时间

**文件**：`backend/services/analysis_service.py`

**修改前**：
```python
SERVICE_TIMEOUT_SECONDS: int = 60  # 硬编码
```

**修改后**：
```python
SERVICE_TIMEOUT_SECONDS: int = int(os.getenv("SERVICE_TIMEOUT_SECONDS", "60"))
```

### 修复 3：配置超时时间

**文件**：`backend/.env`

```ini
# Timeout for individual service execution (seconds)
SERVICE_TIMEOUT_SECONDS=180
```

### 修复 4：添加 python-dotenv 依赖

**文件**：`backend/requirements.txt`

```
python-dotenv
```

**安装**：
```bash
cd backend
.venv/Scripts/pip install python-dotenv
```

## 验证修复

### 1. 重启服务器

**重要**：必须完全重启，`--reload` 不会重新读取环境变量。

```bash
# 停止服务器
Ctrl+C

# 重新启动
npm run server
```

### 2. 检查日志

**成功的日志应该显示**：

```
✅ Cable: loaded 43908 rows from CABLE_INFO
✅ Cable: Temperature - valid: 43908, min: 0, max: 71, critical: 0, warning: 20
✅ Cable warning reasons: Temperature warning: 20 ports
✅ Cable: Final severity counts before return: {'normal': 43888, 'warning': 20}
✅ Cable: filtered 43908 rows to 20 issues (critical/warning)
```

**不应该再看到**：
```
❌ Service cable timed out after 60s, using empty result
```

### 3. 前端验证

- Cable 跳线分析应该显示 20 条记录
- 每条记录的 Severity 字段为 "warning"
- Temperature 字段显示 ≥70°C 的温度值

## 其他服务的情况

### Xmit 拥塞分析

**日志**：
```
Xmit congestion distribution: {'normal': 31704}
Xmit: filtered 31704 rows to 0 issues (warning/severe)
```

**分析**：
- 所有 31704 个端口的拥塞级别都是 "normal"
- 没有 "warning" 或 "severe" 级别的端口
- **这是正常的**，不是 bug

**拥塞级别判断标准**：
- `WaitRatioPct <= 1%`: normal
- `1% < WaitRatioPct <= 5%`: warning
- `WaitRatioPct > 5%`: severe

### BER 误码分析

**日志**：
```
BER: filtered 30485 rows to 30480 issues (critical/warning)
```

**分析**：
- 30485 个端口中有 30480 个有误码问题
- **正常显示**，没有超时问题

### 使用 return_only_issues 的服务

只有 **3 个服务** 使用了数据过滤：

1. **CableService** - 过滤 Severity 为 critical/warning 的行
2. **XmitService** - 过滤 CongestionLevel 为 warning/severe 的行
3. **BerService** - 过滤 SymbolBERSeverity 为 critical/warning 的行

其他服务（如 HCA, Fan, Switch 等）返回所有数据，不进行过滤。

## 性能优化建议

### 1. 增加超时时间

根据数据集大小调整超时时间：

| 数据集大小 | 建议超时时间 |
|-----------|-------------|
| < 10,000 行 | 60 秒 |
| 10,000 - 50,000 行 | 120 秒 |
| > 50,000 行 | 180 秒 |

### 2. 优化 Cable 服务性能

**当前瓶颈**：
- 43908 行数据的处理
- 温度、告警、合规性检查
- DataFrame 操作和过滤

**优化方向**：
- 使用向量化操作替代循环
- 减少不必要的数据复制
- 优化 Severity 计算逻辑

### 3. 添加进度反馈

在前端显示分析进度：
```
正在分析 Cable 数据... (60%)
正在分析 Xmit 数据... (80%)
```

### 4. 实现缓存机制

对于相同的数据集，缓存分析结果：
```python
cache_key = f"{dataset_hash}_{service_name}"
if cache_key in cache:
    return cache[cache_key]
```

## 环境变量配置参考

**完整的 `.env` 配置**：

```ini
# ============================================
# Analysis Settings
# ============================================
# Number of parallel workers for analysis
MAX_WORKERS=12

# Only return rows with issues (critical/warning)
RETURN_ONLY_ISSUES=true

# Maximum rows to return for preview (0 = unlimited)
MAX_PREVIEW_ROWS=2000

# Timeout for individual service execution (seconds)
SERVICE_TIMEOUT_SECONDS=180

# ============================================
# Cable Analysis Settings
# ============================================
# Temperature thresholds (Celsius)
CABLE_TEMP_WARNING_THRESHOLD=70
CABLE_TEMP_CRITICAL_THRESHOLD=80

# Maximum cable rows to return
MAX_CABLE_ROWS=2000
```

## 故障排查清单

如果问题仍然存在，请检查：

- [ ] 是否完全重启了服务器（不是 reload）
- [ ] `.env` 文件是否在 `backend/` 目录下
- [ ] `python-dotenv` 是否已安装
- [ ] `load_dotenv()` 是否在导入 `api` 之前调用
- [ ] 环境变量是否正确设置（`SERVICE_TIMEOUT_SECONDS=180`）
- [ ] 浏览器是否清除了缓存（Ctrl+Shift+R）

## 相关文件

- `backend/main.py` - 主程序入口，加载环境变量
- `backend/services/analysis_service.py` - 服务编排和超时控制
- `backend/services/cable_service.py` - Cable 分析服务
- `backend/services/xmit_service.py` - Xmit 分析服务
- `backend/services/ber_service.py` - BER 分析服务
- `backend/.env` - 环境变量配置
- `backend/requirements.txt` - Python 依赖

---

**修复日期**：2026-01-12
**版本**：v1.1.2
**状态**：已修复，待验证
