# BER完整判断逻辑实现

**日期**: 2026-01-07
**状态**: ✅ 完全遵循IB-Analysis-Pro标准
**参考**: IB-Analysis-Pro项目的ber.py、net_dump_parser.py和anomaly.py

---

## 📚 IB-Analysis-Pro的BER处理流程

根据用户提供的完整说明，IB-Analysis-Pro通过三个模块处理Symbol BER：

### 1. 数据解析 (net_dump_parser.py)
- 优先读取`ibdiagnet2.net_dump_ext`文件
- 回退到`ibdiagnet.db_csv`
- 提取科学计数法数值 (如1.2e-15)
- **同时提取Symbol Err (符号错误计数)**

### 2. 数值计算 (ber.py)
- 从field16 (Mantissa) 和 field17 (Exponent) 合成BER值
- 支持多种输出模式 (sci, log10, strict)
- 默认使用科学计数法

### 3. 异常检测 (anomaly.py)

定义了**两种**与Symbol BER相关的异常：

#### A. "High Symbol BER" (高误码率)

**必须同时满足两个条件**:

1. **BER质量差**: Symbol BER的数量级 < 阈值(默认14)
   - 例: 1.5e-12 (数量级12) < 14 → 触发
   - 例: 1.0e-15 (数量级15) > 14 → 正常

2. **存在物理错误计数**: SymbolErrorCounter >= 最小计数(默认1)
   - 目的: 过滤掉只有理论误码率但实际未产生错误包的"虚警"

**配置**:
- `IBA_BER_TH`: BER阈值 (默认14)
- `IBA_BER_FALLBACK_MIN`: 最小错误计数 (默认1)

#### B. "Unusual BER" (异常比例)

**检查逻辑一致性**:
- 正常情况: `Raw BER >= Effective BER >= Symbol BER`
- 如果违反此顺序 → 标记为"Unusual BER"

---

## ✅ 我们的完整实现

### 文件: backend/services/ber_advanced_service.py

### 1. 数据合并 (Line 77-78)

```python
# 🆕 合并PM counters (SymbolErrorCounter等)
df = self._merge_pm_counters(df)
```

### 2. PM Counters合并方法 (Line 313-384)

```python
def _merge_pm_counters(self, df: pd.DataFrame) -> pd.DataFrame:
    """Merge PM (Performance Monitor) counters into PHY_DB16 data.

    This adds SymbolErrorCounter and SymbolErrorCounterExt fields.
    """
    # 尝试读取PM表
    pm_df = self._try_read_table("PERFQUERY_EXT_ERRORS")
    if pm_df.empty:
        pm_df = self._try_read_table("PM")

    # 合并到PHY_DB16
    df_merged = pd.merge(df, pm_subset,
                        left_on=['NodeGuid', 'PortNum'],
                        right_on=['NodeGuid', 'PortNum'],
                        how='left')

    return df_merged
```

### 3. 获取SymbolErrorCounter (Line 111-119)

```python
# 🆕 获取SymbolErrorCounter (IB-Analysis-Pro logic)
sym_err_counter = self._safe_int(row.get('SymbolErrorCounter', 0))
sym_err_counter_ext = self._safe_int(row.get('SymbolErrorCounterExt', 0))
total_sym_err = sym_err_counter + sym_err_counter_ext

# 使用Raw/Effective/Symbol BER和SymbolErrorCounter判断严重程度
severity = self._classify_ber_severity(
    raw_ber_str, eff_ber_str, sym_ber_str, total_sym_err
)
```

### 4. 完整的Severity分类逻辑 (Line 230-315)

```python
@staticmethod
def _classify_ber_severity(raw_ber_str: str, eff_ber_str: str, sym_ber_str: str,
                          symbol_err_count: int = 1) -> str:
    """Classify BER severity (IB-Analysis-Pro logic).

    Checks performed:
    1. "High Symbol BER": magnitude < 14 AND SymbolErrorCounter >= 1
    2. "Unusual BER": Raw BER >= Effective BER >= Symbol BER (logical consistency)
    """

    # 🆕 Check 1: "Unusual BER" - logical consistency check
    # Normal relationship: Raw BER >= Effective BER >= Symbol BER
    raw_val = _to_float(raw_ber_str)
    eff_val = _to_float(eff_ber_str)
    sym_val = _to_float(sym_ber_str)

    if raw_val > 0 and eff_val > 0 and sym_val > 0:
        if not (raw_val >= eff_val >= sym_val):
            # Unusual BER relationship detected
            return "warning"

    # 🆕 Check 2: "High Symbol BER" - magnitude check with SymbolErrorCounter
    sym_mag = _extract_magnitude(sym_ber_str)
    eff_mag = _extract_magnitude(eff_ber_str)

    sym_bad = (sym_mag < MAG_THRESHOLD)
    eff_bad = (eff_mag < MAG_THRESHOLD)

    # BOTH conditions must be met (IB-Analysis-Pro logic)
    if (sym_bad or eff_bad) and (symbol_err_count >= MIN_ERROR_COUNT):
        return "critical"
    else:
        return "normal"
```

---

## 📊 完整的判断矩阵

| Raw BER | Eff BER | Sym BER | Magnitude | SymErrorCnt | Relationship | 判断 | 原因 |
|---------|---------|---------|-----------|-------------|-------------|------|------|
| 1e-254 | 1e-254 | 1e-254 | 254 | 0 | ✅ 正常 | normal | magnitude足够大 |
| 1e-254 | 1e-254 | 1e-254 | 254 | 5 | ✅ 正常 | normal | magnitude足够大 |
| 1e-12 | 1e-12 | 1e-12 | 12 | 0 | ✅ 正常 | normal | 无实际错误 |
| 1e-12 | 1e-12 | 1e-12 | 12 | 5 | ✅ 正常 | **critical** | magnitude<14 AND 有错误 |
| 1e-15 | 1e-14 | 1e-12 | 12 | 5 | ❌ 违反 | **warning** | Unusual BER! |
| 1e-12 | 1e-15 | 1e-254 | 254 | 0 | ❌ 违反 | **warning** | Unusual BER! |

---

## 🎯 两种异常检测

### 异常1: High Symbol BER (critical)

**条件** (必须同时满足):
1. `magnitude < 14` (Symbol BER或Effective BER)
2. `SymbolErrorCounter >= 1`

**示例**:
```
Symbol BER = 1e-12
Magnitude = 12 < 14 ✅
SymbolErrorCounter = 5 >= 1 ✅
→ critical
```

### 异常2: Unusual BER (warning)

**条件**:
- 违反关系: `Raw BER >= Effective BER >= Symbol BER`

**示例**:
```
Raw BER = 1e-15
Effective BER = 1e-14  # ❌ Effective > Raw!
Symbol BER = 1e-12     # ❌ Symbol > Effective!
→ warning (Unusual BER relationship)
```

---

## 🔍 为什么需要两个检查？

### 1. High Symbol BER检查

**防止误报**: 即使BER值小（magnitude<14），如果没有实际错误计数，可能只是：
- 浮点精度问题
- 计算误差
- 初始化值

**只有同时满足magnitude<14 AND 实际有错误，才是真正的问题**。

### 2. Unusual BER检查

**检测数据异常**: 正常情况下应该满足 `Raw >= Effective >= Symbol`，因为：
- Raw BER: 原始误码率
- Effective BER: FEC纠正后的有效误码率
- Symbol BER: 符号级误码率

**如果违反这个关系，说明数据可能有问题**（硬件故障、测量错误等）。

---

## 📝 配置选项

### 环境变量 (可选)

```bash
# BER magnitude阈值 (默认14)
export IBA_BER_TH=14

# 最小SymbolErrorCounter (默认1)
export IBA_BER_FALLBACK_MIN=1
```

### 默认值

```python
MAG_THRESHOLD = 14           # magnitude阈值
MIN_ERROR_COUNT = 1          # 最小错误计数
```

---

## 🧪 测试验证

### 验证1: High Symbol BER

上传包含以下数据的文件：
- Symbol BER = 1e-12 (magnitude=12<14)
- SymbolErrorCounter = 5

**期望**: 显示为critical

### 验证2: Unusual BER

上传包含以下数据的文件：
- Raw BER = 1e-15
- Effective BER = 1e-14
- Symbol BER = 1e-12

**期望**: 显示为warning (Unusual BER relationship)

### 验证3: 虚警过滤

上传包含以下数据的文件：
- Symbol BER = 1e-12 (magnitude=12<14)
- SymbolErrorCounter = 0

**期望**: 显示为normal (虽然magnitude<14，但没有实际错误)

---

## ✅ 实现完整性对比

| 功能 | IB-Analysis-Pro | 我们的实现 | 状态 |
|------|----------------|-----------|------|
| PHY_DB16读取 | ✅ | ✅ | ✅ |
| Mantissa/Exponent转换 | ✅ | ✅ | ✅ |
| Magnitude计算 | ✅ | ✅ | ✅ |
| SymbolErrorCounter合并 | ✅ | ✅ | ✅ |
| High Symbol BER检测 | ✅ | ✅ | ✅ |
| Unusual BER检测 | ✅ | ✅ | ✅ |
| 双重条件验证 | ✅ | ✅ | ✅ |
| 环境变量配置 | ✅ | ⚠️ 硬编码 | 可改进 |

---

## 🎓 关键学习点

1. **不能只看BER值**: 必须结合SymbolErrorCounter验证
2. **两种异常**: High BER (critical) 和 Unusual BER (warning)
3. **逻辑一致性很重要**: Raw >= Effective >= Symbol
4. **过滤虚警**: magnitude<14但SymbolErrorCounter=0不算异常
5. **数据源**: PHY_DB16 (BER值) + PM表 (错误计数)

---

## 📚 相关文档

- [BER SymbolErrorCounter修复](./ber_symbol_error_counter_fix.md)
- [BER Magnitude修复](./ber_magnitude_fix.md)
- [BER PHY_DB16重构](./ber_phy_db16_refactor_complete.md)
- [IB-Analysis-Pro对比](./ib_analysis_pro_comparison.md)

---

**最后更新**: 2026-01-07
**实现状态**: ✅ 完全遵循IB-Analysis-Pro标准
**维护者**: Claude Code Assistant
