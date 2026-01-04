# NVIDIA InfiniBand 网络健康检查能力总结

## 文档概述

本文档总结了基于 IBDiagnet 工具和 `ib_analysis` 模块的 InfiniBand 网络健康检查能力，用于 NVIDIA 网络健康检查平台。

---

## 一、核心健康检查模块

### 1. BER (Bit Error Rate) 分析 - 误码率检查
**文件**: `backend/ib_analysis/ber.py`

#### 检查内容
- **Raw BER**: 原始误码率
- **Effective BER**: 有效误码率
- **Symbol BER**: 符号误码率

#### 异常检测
- **高 BER 异常** (`IBH_HIGH_SYMBOL_BER`): 严重级别 - CRITICAL
  - 检测超过阈值的误码率
  - 可能导致数据传输错误

- **异常 BER 模式** (`IBH_UNUSUAL_BER`): 警告级别 - WARNING
  - 检测不寻常的误码率模式
  - 可能预示潜在问题

#### 数据来源
- 从 `net_dump_ext` 文件或 `db_csv` 文件的 `PHY_DB16` 表读取
- 支持科学计数法和 log10 格式输出

#### 关键指标
- 计算 log10 值用于排序和可视化
- 合并 PM 计数器（如 SymbolErrorCounter）作为辅助信号

---

### 2. HCA (Host Channel Adapter) 分析 - 主机适配器检查
**文件**: `backend/ib_analysis/hca.py`

#### 检查内容
- **固件版本** (FW): 检测固件版本不一致
- **PSID**: 产品序列号标识
- **设备类型**: HCA/Switch/NVLink 设备识别
- **固件日期**: FW 发布日期
- **运行时间** (Up Time): 设备运行时长

#### 异常检测
- **离群值检测** (`IBH_OUTLIER`): 信息级别 - INFO
  - HCA 设备: 阈值 5% (th=0.05)
  - 交换机设备: 阈值 20% (th=0.2)
  - 检测固件版本、PSID 不一致的设备

#### 关键功能
- 设备类型映射 (HCA_DICT, SWITCH_DICT, NVLINK_DICT)
- 固件版本格式化: `Major.Minor.SubMinor`
- 运行时间转换为可读格式

---

### 3. Cable 分析 - 光缆/光模块检查
**文件**: `backend/ib_analysis/cable.py`

#### 检查内容
- **温度监控**: 光模块温度 (°C)
- **供应商信息**: Vendor, PN (Part Number)
- **固件版本**: ConnectorFW
- **链路速度**: LinkSpeedEn
- **端口状态**: PortPhyState, PortState
- **错误计数器**:
  - `LinkDownedCounter`: 链路断开次数
  - `PortRcvErrorsExt`: 接收错误
  - `LocalLinkIntegrityErrorsExt`: 本地链路完整性错误
  - `PortRcvSwitchRelayErrors`: 交换机中继错误
  - `PortXmitConstraintErrors`: 发送约束错误
  - `PortRcvConstraintErrors`: 接收约束错误

#### 异常检测
1. **红旗异常** (`IBH_RED_FLAG`): 严重级别 - CRITICAL
   - 检测上述错误计数器中的非零值
   - 每个错误类型单独标记

2. **离群值检测** (`IBH_OUTLIER`): 信息级别 - INFO
   - 检测 ConnectorFW, PN, Vendor 不一致

3. **高温异常**: 严重/警告级别
   - **≥80°C**: CRITICAL
   - **70-79°C**: WARNING
   - 权重 = 温度 - 60

#### 关键阈值
- 温度警告: 70°C
- 温度严重: 80°C

---

### 4. Xmit 分析 - 传输/拥塞检查
**文件**: `backend/ib_analysis/xmit.py`

#### 检查内容
- **Xmit Wait**: 传输等待时间 (拥塞指标)
- **Xmit Data**: 实际传输数据量
- **带宽利用率**: 转换为 Gbps

#### 异常检测
1. **高传输等待** (`IBH_HIGH_XMIT_WAIT`): 警告级别 - WARNING
   - 检测过高的传输等待时间
   - 表示网络拥塞

2. **HCA 背压** (`IBH_HCA_BP`): 警告级别 - WARNING
   - 检测 HCA 端的背压问题

3. **Plain 不平衡** (`IBH_PLAIN_UNB`): 信息级别 - INFO
   - 检测同一 Plain 内的流量不平衡
   - 分别检测 wait 和 data

4. **AR 不平衡** (`IBH_AR_UNB`): 信息级别 - INFO
   - 检测自适应路由的不平衡

#### 关键指标
- 计算比率: `xmit_wait / (xmit_data + 1)`
- 支持 NVLink 和普通 IB 网络
- 按 Rack 分组统计

---

### 5. Health Score 计算 - 综合健康评分
**文件**: `backend/ib_analysis/health_score.py`

#### 评分系统
- **分数范围**: 0-100
- **等级**: A (90+), B (80-89), C (70-79), D (60-69), F (<60)
- **状态**: Healthy, Warning, Critical

#### 评分类别及权重
```python
CATEGORY_WEIGHTS = {
    "ber": 25,           # 误码率 (最高权重)
    "errors": 25,        # 错误计数 (最高权重)
    "congestion": 20,    # 拥塞
    "topology": 10,      # 拓扑
    "latency": 10,       # 延迟
    "balance": 5,        # 负载均衡
    "config": 3,         # 配置
    "anomaly": 2,        # 其他异常
}
```

#### 严重性乘数
```python
SEVERITY_MULTIPLIERS = {
    Severity.CRITICAL: 3.0,
    Severity.WARNING: 1.5,
    Severity.INFO: 0.5,
}
```

#### 特定检查项
1. **高温检查**:
   - ≥80°C: CRITICAL
   - ≥70°C: WARNING
   - 扣分 = (温度 - 60) × 严重性乘数

2. **链路断开检查**:
   - LinkDownedCounter > 0: CRITICAL
   - 扣分 = 断开次数 × 3.0

3. **端口状态检查**:
   - 非 Active 状态: WARNING
   - 扣分 = 1.0 × 1.5

#### 输出格式
```python
{
    "score": 85,
    "grade": "B",
    "status": "Healthy",
    "total_nodes": 120,
    "total_ports": 480,
    "summary": {
        "critical": 2,
        "warning": 15,
        "info": 8
    },
    "category_scores": {
        "ber": 95,
        "errors": 88,
        "congestion": 75,
        ...
    },
    "issues": [...]
}
```

---

### 6. Brief 分析 - 综合概览
**文件**: `backend/ib_analysis/brief.py`

#### 功能
- 合并所有模块的数据 (Xmit, HCA, Cable, BER, CC, Histogram)
- 提供跨模块的综合视图
- 聚合所有异常检测结果

#### 关键列
```python
COLUMNS_TO_PRINT = [
    'NodeGUID', 'Node Name', 'PortNumber', 'Attached To',
    'Xmit Wait', 'Xmit Data',                    # 传输
    'PortState', 'PortPhyState',                 # 状态
    'LinkDownedCounter', 'LinkErrorRecoveryCounter',  # 错误
    'Vendor', 'PN', 'Temperature (c)',           # 光模块
    'Avg RTT(μs)', 'MAX RTT(μs)', 'MIN RTT(μs)', # 延迟
]
```

---

## 二、异常类型汇总

### 异常类型枚举 (AnomlyType)
基于代码推断的异常类型：

| 异常类型 | 类别 | 严重性 | 说明 |
|---------|------|--------|------|
| `IBH_HIGH_XMIT_WAIT` | congestion | WARNING | 高传输等待 |
| `IBH_HCA_BP` | congestion | WARNING | HCA 背压 |
| `IBH_PLAIN_UNB` | balance | INFO | Plain 不平衡 |
| `IBH_AR_UNB` | balance | INFO | AR 不平衡 |
| `IBH_DRIB_OUTLIER_SW` | anomaly | WARNING | DrIB 离群交换机 |
| `IBH_HIGH_SYMBOL_BER` | ber | CRITICAL | 高符号误码率 |
| `IBH_UNUSUAL_BER` | ber | WARNING | 异常 BER 模式 |
| `IBH_OUTLIER` | config | INFO | 配置离群值 |
| `IBH_RED_FLAG` | errors | CRITICAL | 错误计数器非零 |
| `IBH_UNUSUAL_RTT_NUM` | congestion | INFO | 异常 RTT 数量 |
| `IBH_HIGH_MIN_RTT` | latency | WARNING | 高最小 RTT |
| `IBH_ASYM_TOPO` | topology | WARNING | 非对称拓扑 |

---

## 三、数据输入源

### 1. IBDiagnet 归档文件
- **格式**: `.zip` 或 `.tar.gz`
- **来源**: UFM 的 ibdiagnet 工具输出
- **核心文件**:
  - `*.db_csv`: 包含多个表的 CSV 数据库
  - `net_dump_ext`: 扩展网络转储文件
  - `ibdiagnet.log`: 诊断日志

### 2. UFM CSV 文件
- **格式**: `.csv`
- **来源**: UFM REST API
- **示例命令**:
  ```bash
  curl -s 127.0.0.1:9002/csv/xcset/low_freq_debug > low_freq_debug.csv
  ```

### 3. 关键数据表
从 `db_csv` 文件读取的表：
- `PHY_DB16`: BER 数据
- `NODES_INFO`: HCA/节点信息
- `CABLE_INFO`: 光缆信息
- `PM_DELTA`: 性能计数器增量 (Xmit)

---

## 四、健康检查操作

### 可用操作 (Operations)
基于 CLAUDE.md 文档：

1. **brief**: 综合摘要
   - 合并所有模块数据
   - 显示关键指标和异常

2. **topo**: 网络拓扑可视化
   - 生成 HTML 交互式拓扑图
   - 支持按温度/Xmit 着色

3. **cable**: 光缆分析
   - 温度监控
   - 错误计数器检查
   - 供应商/固件一致性

4. **xmit**: 传输/拥塞分析
   - 带宽利用率
   - 拥塞检测
   - 负载均衡检查

5. **ber**: 误码率分析
   - 三种 BER 类型
   - 高 BER 检测
   - 异常模式识别

6. **hca**: 主机适配器分析
   - 固件版本检查
   - 设备类型识别
   - 运行时间统计

---

## 五、输出格式

### 1. 表格输出
- 使用 `tabulate` 库生成美观的表格
- 支持排序和过滤
- 可限制显示行数

### 2. CSV 导出
- 所有模块支持 CSV 导出
- 包含扩展列
- 适合进一步分析

### 3. JSON 导出
- 结构化数据输出
- 包含元数据
- 适合 API 集成

### 4. HTML 可视化
- 交互式网络拓扑图
- 使用 pyvis 库
- 支持节点/边着色和标签

### 5. 图表输出
- 使用 plotext (终端) 和 matplotlib
- 柱状图、散点图
- 概览统计

---

## 六、关键阈值和参数

### 温度阈值
- **警告**: 70°C
- **严重**: 80°C

### BER 阈值
- 动态计算，基于 log10 值
- 检测高于正常水平的 BER

### Xmit 阈值
- Xmit Wait > 10³: 触发拥塞检查
- 动态比率计算

### 离群值检测
- **HCA**: 5% 阈值
- **Switch**: 20% 阈值

---

## 七、使用建议

### 健康检查流程
1. **上传数据**: IBDiagnet 归档或 UFM CSV
2. **运行 brief 操作**: 获取综合概览
3. **检查异常**: 查看 anomalies 输出
4. **深入分析**: 根据异常类型运行专项操作
   - 高 BER → 运行 `ber` 操作
   - 高温 → 运行 `cable` 操作
   - 拥塞 → 运行 `xmit` 操作
5. **查看拓扑**: 运行 `topo` 操作可视化问题位置
6. **计算健康评分**: 使用 `health_score` 模块获取综合评分

### 优先级排序
1. **CRITICAL 级别**:
   - 高 BER (`IBH_HIGH_SYMBOL_BER`)
   - 错误计数器非零 (`IBH_RED_FLAG`)
   - 高温 (≥80°C)
   - 链路断开

2. **WARNING 级别**:
   - 拥塞 (`IBH_HIGH_XMIT_WAIT`)
   - 异常 BER (`IBH_UNUSUAL_BER`)
   - 中等温度 (70-79°C)

3. **INFO 级别**:
   - 配置不一致 (`IBH_OUTLIER`)
   - 负载不平衡 (`IBH_PLAIN_UNB`, `IBH_AR_UNB`)

---

## 八、技术实现细节

### 性能优化
- **缓存机制**: 预计算节点和连接查找
- **批处理**: 使用 pandas 向量化操作
- **超时保护**: 大数据集处理超时机制

### 数据合并策略
- 使用 `NodeGUID` 和 `PortNumber` 作为主键
- 左连接保留所有端口数据
- 去重处理避免重复记录

### 异常聚合
- 使用 `IBH_ANOMALY_AGG_COL` 列聚合多个异常
- 使用 `IBH_ANOMALY_AGG_WEIGHT` 列计算权重
- 支持多模块异常合并

---

## 九、参考文档

### 官方文档
1. **IBDiagnet User Manual v2.13.0**
   - URL: https://docs.nvidia.com/ibdiagnet-infiniband-fabric-diagnostic-tool-user-manual-v2-13-0.pdf
   - 内容: IBDiagnet 工具使用指南

2. **UFM Enterprise REST API Guide v6.22**
   - URL: https://docs.nvidia.com/networking/display/nvidia-ufm-enterprise-rest-api-guide-v6-22-2.2.pdf
   - 内容: UFM REST API 使用指南

### 代码模块
- `backend/ib_analysis/`: 核心分析模块
- `backend/ib_analysis/anomaly.py`: 异常检测逻辑
- `backend/ib_analysis/health_score.py`: 健康评分计算

---

## 十、总结

NVIDIA InfiniBand 网络健康检查平台提供了全面的网络诊断能力，涵盖：

✅ **物理层**: 误码率、光模块温度、链路状态
✅ **性能层**: 带宽利用率、拥塞检测、延迟分析
✅ **配置层**: 固件版本、设备类型、拓扑一致性
✅ **错误层**: 各类错误计数器、链路断开、完整性错误

通过综合健康评分系统，可以快速评估网络整体状态，并定位具体问题。

---

**文档版本**: 1.0
**生成日期**: 2026-01-03
**作者**: Claude Code (呆哥科技)
