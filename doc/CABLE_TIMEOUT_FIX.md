# Cable 超时问题修复说明

## 问题描述

Cable 分析显示"无故障数据"，但后端日志显示找到了 20 个温度警告（≥70°C）。

## 根本原因

1. **Cable 服务超时**：Cable 服务需要约 60 秒才能完成分析，但默认超时时间只有 60 秒
2. **超时返回空结果**：当 cable 服务超时时，系统返回空结果给前端
3. **后台继续运行**：即使超时，cable 服务仍在后台继续运行并最终完成，但这些数据已被丢弃
4. **环境变量未加载**：后端没有加载 `.env` 文件，所以无法读取配置的超时时间

## 已修复的问题

### 1. 添加 python-dotenv 支持

**文件：** `backend/requirements.txt`
```diff
# FastAPI backend
fastapi
uvicorn
python-multipart
+python-dotenv
pandas
```

**文件：** `backend/main.py`
```python
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
```

### 2. 从环境变量读取超时时间

**文件：** `backend/services/analysis_service.py`
```python
# 修改前
SERVICE_TIMEOUT_SECONDS: int = 60

# 修改后
SERVICE_TIMEOUT_SECONDS: int = int(os.getenv("SERVICE_TIMEOUT_SECONDS", "60"))
```

### 3. 配置超时时间

**文件：** `backend/.env`
```ini
# Timeout for individual service execution (seconds)
SERVICE_TIMEOUT_SECONDS=180
```

### 4. 删除 BER Advanced 模块

**文件：** `frontend/src/healthCheckDefinitions.js`
- 从 BER 分组中移除 `ber_advanced`
- 删除 `ber_advanced` 的完整定义

## 如何应用修复

### 步骤 1：停止当前服务器

按 `Ctrl+C` 停止正在运行的服务器。

### 步骤 2：重新启动服务器

```bash
npm run server
```

**重要：** 必须完全重启服务器，因为：
- Uvicorn 的 `--reload` 只重新加载 Python 代码
- **不会重新读取环境变量**
- 必须完全重启才能加载 `.env` 文件中的新配置

### 步骤 3：重新上传文件

1. 在浏览器中硬刷新（Ctrl+Shift+R）清除缓存
2. 重新上传 IBDiagnet 文件进行分析
3. Cable 服务现在有 180 秒的超时时间，足够完成分析

## 验证修复

### 后端日志应该显示：

```
2026-01-12 XX:XX:XX - services.cable_service - INFO - Cable: Temperature - valid: 43908, min: 0, max: 71, critical: 0, warning: 20
2026-01-12 XX:XX:XX - services.cable_service - INFO - Cable warning reasons: Temperature warning: 20 ports
2026-01-12 XX:XX:XX - services.cable_service - INFO - Cable: Final severity counts before return: {'normal': 43888, 'warning': 20}
2026-01-12 XX:XX:XX - services.cable_service - INFO - Cable: filtered 43908 rows to 20 issues (critical/warning)
```

**不应该再看到：**
```
Service cable timed out after 60s, using empty result
```

### 前端应该显示：

- Cable 跳线分析显示 20 条温度警告记录
- 每条记录的 Severity 字段为 "warning"
- Temperature 字段显示 ≥70°C 的温度值

## 技术细节

### 服务执行流程

1. **并行启动**：所有分析服务同时启动（第236-239行）
2. **按序等待**：按照 `service_specs` 顺序等待每个服务完成（第243行）
3. **超时处理**：如果服务在 `SERVICE_TIMEOUT_SECONDS` 内未完成，返回空结果（第247-249行）
4. **Cable 是第一个**：Cable 服务在列表中排第一，所以最先被等待

### 为什么需要 180 秒

根据日志分析：
- Cable 服务加载数据：~1 秒
- 严重性计算：~4 秒
- 数据过滤和处理：~5 秒
- 总计：约 10 秒（正常情况）

但在某些情况下（大数据集、系统负载高），可能需要更长时间：
- 43908 行数据的处理
- 温度、告警、合规性检查
- DataFrame 操作和过滤

180 秒的超时提供了足够的缓冲时间。

## 相关文件

- `backend/.env` - 环境变量配置
- `backend/main.py` - 加载环境变量
- `backend/services/analysis_service.py` - 服务超时逻辑
- `backend/services/cable_service.py` - Cable 分析服务
- `frontend/src/healthCheckDefinitions.js` - 前端健康检查定义

## 后续优化建议

1. **优化 Cable 服务性能**：减少处理时间
2. **添加进度反馈**：显示分析进度给用户
3. **可配置超时**：允许用户根据数据集大小调整超时时间
4. **缓存机制**：缓存已分析的数据，避免重复分析

---

**修复日期：** 2026-01-12
**版本：** v1.1.2
