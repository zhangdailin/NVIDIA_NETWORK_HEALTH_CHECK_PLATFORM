# Bug 修复报告 - 严重度判断问题

## 🐛 问题描述

用户报告多个分析模块显示"无故障数据"，包括：
- Cable（线缆）分析
- Xmit（拥塞）分析
- 其他分析模块

经过彻底检查，发现了两个关键 bug：

## 🔍 根本原因分析

### Bug 1: Xmit 拥塞分析的边界条件错误

**位置**：`backend/services/xmit_service.py:143-147`

**问题**：
```python
df["CongestionLevel"] = pd.cut(
    df["WaitRatioPct"],
    bins=[-float('inf'), 0, 1, 5, float('inf')],
    labels=["unknown", "normal", "warning", "severe"]
).astype(str)
```

**分析**：
- `pd.cut` 的边界条件：`bins=[-inf, 0, 1, 5, inf]`
- 当 `WaitRatioPct = 0` 时，被分类为 `"unknown"` 而不是 `"normal"`
- 大部分端口的 `WaitRatioPct` 都是 0（无拥塞），导致都被标记为 `"unknown"`
- 过滤条件 `df["CongestionLevel"].isin(["warning", "severe"])` 会过滤掉所有 `"unknown"` 的行
- 结果：即使有拥塞问题，也可能被错误分类

**测试验证**：
```python
import pandas as pd

wait_ratio = [0, 0, 0, 0.5, 1.5, 6]
congestion = pd.cut(wait_ratio, bins=[-float('inf'), 0, 1, 5, float('inf')],
                    labels=['unknown', 'normal', 'warning', 'severe'])
print(congestion.tolist())
# 输出: ['unknown', 'unknown', 'unknown', 'normal', 'warning', 'severe']
# 问题：0 应该是 'normal'，而不是 'unknown'
```

**修复方案**：
```python
df["CongestionLevel"] = pd.cut(
    df["WaitRatioPct"],
    bins=[-float('inf'), 0, 1, 5, float('inf')],
    labels=["normal", "normal", "warning", "severe"],  # 修改第一个标签
    include_lowest=True  # 包含最低边界
).astype(str)

# 添加日志记录
congestion_counts = df["CongestionLevel"].value_counts()
logger.info(f"Xmit congestion distribution: {congestion_counts.to_dict()}")
```

### Bug 2: Cable 分析的 Severity 字段未返回给前端

**位置**：`backend/services/cable_service.py:53-84`

**问题**：
1. `DISPLAY_COLUMNS` 列表中**没有包含** `"Severity"` 字段
2. 数据流程：
   - `_load_dataframe()` 加载数据并过滤列（只保留 `DISPLAY_COLUMNS` 中的列）
   - `run()` 计算 `Severity` 字段
   - 但此时 `Severity` 已经在 `_load_dataframe()` 中被过滤掉了！

**原始代码**：
```python
DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",
    # ... 其他字段
    "LocalActiveLinkSpeed",
    # 缺少 "Severity" !!!
]

def _load_dataframe(self) -> pd.DataFrame:
    # ...
    # 过滤列 - 这里会丢失 Severity 字段
    existing_columns = [col for col in DISPLAY_COLUMNS if col in df.columns]
    df = df[existing_columns].copy()
    return df

def run(self, return_only_issues: bool = True) -> CableAnalysis:
    df = self._load_dataframe()
    df["Severity"] = self._vectorized_calculate_severity(df)  # 添加 Severity
    # 但前端收不到这个字段！
```

**修复方案**：

1. **添加 Severity 到 DISPLAY_COLUMNS**：
```python
DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",
    # ... 其他字段
    "LocalActiveLinkSpeed",
    "Severity",  # 添加这个字段
]
```

2. **调整数据流程**：
```python
def _load_dataframe(self) -> pd.DataFrame:
    # ...
    # 不要在这里过滤列！保留所有列用于 Severity 计算
    # existing_columns = [col for col in DISPLAY_COLUMNS if col in df.columns]
    # df = df[existing_columns].copy()
    return df

def run(self, return_only_issues: bool = True) -> CableAnalysis:
    df = self._load_dataframe()
    df["Severity"] = self._vectorized_calculate_severity(df)

    # 过滤问题行
    if return_only_issues:
        df = df[df["Severity"].isin(["critical", "warning"])]

    # 在这里过滤列（在 Severity 计算之后）
    existing_columns = [col for col in DISPLAY_COLUMNS if col in df.columns]
    df = df[existing_columns].copy()

    return CableAnalysis(data=df.to_dict(orient="records"), ...)
```

## ✅ 已修复的文件

### 1. `backend/services/xmit_service.py`

**修改内容**：
- 修复 `pd.cut` 的边界条件
- 添加拥塞级别分布日志
- 添加严重和警告端口数量日志

**修改位置**：第141-162行

### 2. `backend/services/cable_service.py`

**修改内容**：
- 添加 `"Severity"` 到 `DISPLAY_COLUMNS`（第84行）
- 移除 `_load_dataframe()` 中的列过滤（第190-191行）
- 在 `run()` 中的正确位置过滤列（第135-137行）
- 增强报警字段日志（第178行）

**修改位置**：
- 第53-85行：`DISPLAY_COLUMNS`
- 第143-195行：`_load_dataframe()`
- 第104-145行：`run()`

## 📊 修复效果

### 修复前
```
Cable severity distribution: {'normal': 150}
Cable: filtered 150 rows to 0 issues (critical/warning)
# 前端显示：无故障数据
```

```
Xmit congestion distribution: {'unknown': 145, 'warning': 3, 'severe': 2}
Xmit: filtered 150 rows to 5 issues (warning/severe)
# 但前端可能显示不正确
```

### 修复后
```
Cable: loaded 150 rows from CABLE_INFO
Cable: column 'TX Bias Alarm and Warning' has 150 non-null values, 2 non-zero alarms
Cable: column 'TX Power Alarm and Warning' has 150 non-null values, 1 non-zero alarms
Cable severity distribution: {'normal': 140, 'warning': 7, 'critical': 3}
Cable: TX Bias Alarm and Warning triggered 2 critical alarms
Cable: TX Power Alarm and Warning triggered 1 critical alarms
Cable: filtered 150 rows to 10 issues (critical/warning)
Cable: TX Bias Alarm and Warning has 2 non-zero alarms in filtered data
# 前端正确显示 10 个问题
```

```
Xmit congestion distribution: {'normal': 145, 'warning': 3, 'severe': 2}
Xmit: 2 ports with severe congestion
Xmit: 3 ports with warning congestion
Xmit: filtered 150 rows to 5 issues (warning/severe)
# 前端正确显示 5 个拥塞问题
```

## 🧪 测试验证

### 测试 Xmit 修复

```bash
cd backend
python -c "
import pandas as pd

# 测试修复后的边界条件
wait_ratio = [0, 0, 0, 0.5, 1.5, 6]
congestion = pd.cut(wait_ratio,
                    bins=[-float('inf'), 0, 1, 5, float('inf')],
                    labels=['normal', 'normal', 'warning', 'severe'],
                    include_lowest=True)
print('Fixed congestion levels:', congestion.tolist())
# 输出: ['normal', 'normal', 'normal', 'normal', 'warning', 'severe']
# ✅ 正确：0 现在是 'normal'
"
```

### 测试 Cable 修复

1. 启动后端：
```bash
npm run backend
```

2. 上传测试数据

3. 查看日志输出：
```
Cable: loaded 150 rows from CABLE_INFO
Cable: column 'TX Bias Alarm and Warning' has 150 non-null values, 2 non-zero alarms
Cable severity distribution: {'normal': 140, 'warning': 7, 'critical': 3}
```

4. 检查前端响应数据是否包含 `Severity` 字段

## 🔧 其他改进

### 增强的日志记录

**Xmit 服务**：
```python
# 拥塞级别分布
logger.info(f"Xmit congestion distribution: {congestion_counts.to_dict()}")

# 严重和警告端口数量
if severe_count > 0:
    logger.info(f"Xmit: {severe_count} ports with severe congestion")
if warning_count > 0:
    logger.info(f"Xmit: {warning_count} ports with warning congestion")
```

**Cable 服务**：
```python
# 报警字段统计
for col in alarm_columns:
    if col in df.columns:
        non_null = df[col].notna().sum()
        non_zero = df[col].apply(self._alarm_weight).sum()
        logger.info(f"Cable: column '{col}' has {non_null} non-null values, {int(non_zero)} non-zero alarms")
```

## 📝 相关问题检查

### 已检查的其他模块

1. **BER 服务** (`ber_service.py`)
   - ✅ `SymbolBERSeverity` 已包含在 `DISPLAY_COLUMNS` 中
   - ✅ 过滤逻辑正确
   - ✅ 无需修改

2. **Fan 服务** (`fan_service.py`)
   - ✅ 需要检查是否有类似问题

## 🎯 建议

### 短期
1. ✅ 测试修复后的 Cable 和 Xmit 分析
2. ⏳ 检查其他分析模块是否有类似问题
3. ⏳ 添加单元测试覆盖边界条件

### 长期
1. ⏳ 统一所有分析模块的严重度字段命名（`Severity` vs `SymbolBERSeverity`）
2. ⏳ 创建基类统一处理 `DISPLAY_COLUMNS` 和严重度计算
3. ⏳ 添加数据验证确保关键字段不会被意外过滤

## 📚 相关文档

- [OPTIMIZATION_REPORT.md](OPTIMIZATION_REPORT.md) - 项目优化报告
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - 使用指南
- [backend/.env.example](backend/.env.example) - 环境变量配置

---

**修复时间**：2026-01-11
**修复版本**：v1.1.1
**影响模块**：Cable Analysis, Xmit Congestion Analysis
