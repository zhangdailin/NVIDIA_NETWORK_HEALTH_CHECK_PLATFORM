# IBDiagnet 使用指南

**最后更新**: 2026-01-24
**用途**: 整合 IBDiagnet 工具使用、健康检查、与平台集成的完整指南
**基于**: IBDiagnet User Manual v2.13.0

---

## 目录

1. [工具概述](#工具概述)
2. [核心功能](#核心功能)
3. [健康检查项](#健康检查项)
4. [输出文件说明](#输出文件说明)
5. [与平台集成](#与平台集成)
6. [实战应用](#实战应用)
7. [最佳实践](#最佳实践)

---

## 工具概述

### IBDiagnet 是什么

IBDiagnet 是 NVIDIA 官方的 InfiniBand 网络诊断工具，用于：
- 拓扑发现和验证
- 链路和设备健康检查
- 性能数据采集
- 问题诊断和报告生成

### 运行模式

| 模式 | 说明 | 使用场景 |
|-----|------|---------|
| **本地模式** | 在 IB 网络内节点运行 | 日常监控、实时诊断 |
| **远程模式** | 通过 SM 远程诊断 | 集中管理、自动化巡检 |
| **离线模式** | 分析已保存快照 | 历史分析、问题复现 |

### 基本命令

```bash
# 基础扫描
ibdiagnet

# 带性能监控
ibdiagnet --pm

# 完整健康检查
ibdiagnet --pm_pause_time 60 --extended_speeds --netchecks
```

---

## 核心功能

### 1. 拓扑验证

**检查内容**:
- 节点连接性（所有节点可达）
- 链路完整性（物理连接状态）
- 拓扑一致性（对比预期拓扑）
- 重复 GUID 检测

**输出文件**:
- `ibdiagnet2.topology` - 完整拓扑描述
- `ibdiagnet2.net_dump` - 网络转储
- `ibdiagnet2.lst` - 节点列表

### 2. 链路质量

**物理层检查**:
```
链路速度: SDR/DDR/QDR/FDR/EDR/HDR/NDR
链路宽度: 1x/4x/8x/12x
链路状态: Active/Down/Init/Armed
物理状态: LinkUp/Sleep/Polling/Disabled
```

**BER 监控**:
- **Raw BER**: FEC 纠错前的原始误码率
- **Effective BER**: FEC 纠错后的有效误码率
- **Symbol BER**: 符号级误码率

**阈值**: Symbol BER > 1e-12 为异常

### 3. 性能监控（PM Counters）

#### 流量计数器
```python
PortXmitData     # 发送数据量（4-byte words）
PortRcvData      # 接收数据量
PortXmitPkts     # 发送包数
PortRcvPkts      # 接收包数
```

#### 拥塞计数器
```python
PortXmitWait        # 发送等待时间
PortXmitTimeCong    # 拥塞时间
PortRcvFECN         # 前向拥塞通知
PortRcvBECN         # 后向拥塞通知
```

#### 错误计数器
```python
SymbolErrorCounter              # 符号错误（应为 0）
LinkErrorRecoveryCounter        # 链路恢复次数
LinkDownedCounter               # 链路断开次数
PortRcvErrors                   # 接收错误
LocalLinkIntegrityErrors        # 本地链路完整性错误
ExcessiveBufferOverrunErrors    # 缓冲区溢出
```

### 4. 光模块监控

**监控参数**:
- 温度（°C）
- 电压（V）
- TX/RX 光功率（dBm）
- 偏置电流（mA）

**告警阈值**:
- 温度: 70°C (warning) / 80°C (critical)
- 光功率: 超出厂商规格范围

---

## 健康检查项

### Critical 级别

#### 1. 链路断开
**检测**: `LinkDownedCounter > 0`
**原因**:
- 物理连接松动
- 光模块故障
- 端口配置错误

**处理**:
1. 检查物理连接
2. 更换故障光模块
3. 查看系统日志

#### 2. 高误码率
**检测**: `Symbol BER > 1e-12`
**原因**:
- 光模块老化
- 光纤污染/损坏
- 信号衰减过大

**处理**:
1. 清洁光纤接口
2. 检查光功率
3. 更换光模块/光纤

#### 3. 高温告警
**检测**: `Temperature >= 80°C`
**原因**:
- 散热不良
- 环境温度过高
- 风扇故障

**处理**:
1. 改善机房散热
2. 检查风扇运行
3. 降低负载

#### 4. 符号错误
**检测**: `SymbolErrorCounter > 0`
**影响**: 数据完整性问题
**处理**: 检查链路质量，更换可疑组件

### Warning 级别

#### 1. 拥塞
**检测**: `PortXmitWait` 持续增长
**阈值**:
- 正常: < 1%
- 警告: 1-5%
- 严重: > 5%

**处理**:
1. 分析流量模式
2. 优化路由配置
3. 升级链路带宽

#### 2. 链路恢复
**检测**: `LinkErrorRecoveryCounter > 0`
**原因**: 瞬时信号问题、电源波动

**处理**: 监控频率，检查电源稳定性

---

## 输出文件说明

### 主要输出文件

| 文件 | 格式 | 内容 | 用途 |
|-----|------|------|------|
| `ibdiagnet2.db_csv` | CSV 数据库 | 多表综合数据 | 数据分析 |
| `ibdiagnet2.net_dump` | 二进制 | 网络转储 | 离线分析 |
| `ibdiagnet2.net_dump_ext` | 扩展格式 | 详细信息（BER, PM） | 快速解析 |
| `ibdiagnet2.pm` | CSV | PM 计数器快照 | 性能分析 |
| `ibdiagnet2.topology` | 文本 | 拓扑层次结构 | 可视化 |
| `ibdiagnet2.log` | 日志 | 运行日志 | 故障排查 |

### db_csv 关键表

| 表名 | 内容 | 对应平台模块 |
|-----|------|------------|
| `NODES_INFO` | 节点信息 | hca.py |
| `CABLE_INFO` | 光模块信息 | cable.py |
| `PHY_DB16` | BER 数据 | ber.py |
| `PM_DELTA` | 性能计数器 | xmit.py |
| `PORT_INFO` | 端口状态 | port.py |

---

## 与平台集成

### 数据流

```
IBDiagnet 运行
    ↓
生成 .db_csv / .net_dump_ext
    ↓
上传到平台 (POST /api/upload/ibdiagnet)
    ↓
ib_analysis 模块解析
    ↓
执行健康检查 (brief/ber/cable/xmit/hca)
    ↓
计算健康评分
    ↓
前端展示结果
```

### 健康评分映射

| IBDiagnet 检测项 | 平台评分类别 | 权重 |
|----------------|------------|------|
| BER 超标 | ber | 25% |
| 错误计数器非零 | errors | 25% |
| XmitWait 过高 | congestion | 20% |
| 拓扑异常 | topology | 10% |
| 温度告警 | errors | 计入 25% |
| 固件不一致 | config | 3% |

### 平台功能对照

| IBDiagnet 输出 | 平台模块 | 前端页面 |
|---------------|---------|---------|
| PHY_DB16 | ber.py | BER Analysis |
| CABLE_INFO | cable.py | Cable Health |
| PM_DELTA | xmit.py | Performance |
| NODES_INFO | hca.py | Node Info |

---

## 实战应用

### 日常健康检查脚本

```bash
#!/bin/bash
# daily_health_check.sh

DATE=$(date +%Y%m%d)
OUTPUT_DIR="/var/log/ibdiagnet/$DATE"
mkdir -p $OUTPUT_DIR

# 运行诊断（60秒采样）
ibdiagnet --pm_pause_time 60 -o $OUTPUT_DIR

# 检查错误
if grep -q "ERRORS FOUND" $OUTPUT_DIR/ibdiagnet2.log; then
    echo "Errors detected! Check $OUTPUT_DIR/ibdiagnet2.log"
    # 发送告警
    mail -s "IB Network Errors" admin@example.com < $OUTPUT_DIR/ibdiagnet2.log
fi

# 归档旧日志（保留 30 天）
find /var/log/ibdiagnet -type d -mtime +30 -exec rm -rf {} \;
```

### 性能分析

#### 带宽利用率计算

```python
def calculate_bandwidth_utilization(xmit_data, duration, link_speed):
    """
    xmit_data: PortXmitData 增量 (4-byte words)
    duration: 采样间隔 (秒)
    link_speed: 链路速度 (Gbps)
    """
    data_bytes = xmit_data * 4
    data_gbits = data_bytes * 8 / 1e9
    utilization = (data_gbits / duration) / link_speed * 100
    return utilization

# 示例：100 Gbps HDR 链路
xmit_data = 25_000_000_000  # 25G words
duration = 60
link_speed = 100

util = calculate_bandwidth_utilization(xmit_data, duration, link_speed)
print(f"Bandwidth Utilization: {util:.2f}%")
# 输出: 13.33%
```

#### 拥塞分析

```bash
# 找出 XmitWait 最高的端口
grep PortXmitWait ibdiagnet2.pm | sort -t',' -k3 -n | tail -20

# 负载均衡分析
grep "PortXmitData" ibdiagnet2.pm | grep "switch01" | awk -F',' '{print $2,$3}'
```

### 故障排查

#### 场景 1: 性能下降
**症状**: 应用延迟增加

**排查步骤**:
1. 检查 `PortXmitWait` - 是否拥塞？
2. 检查 `LinkErrorRecoveryCounter` - 链路不稳定？
3. 检查 BER - 信号质量下降？
4. 检查温度 - 过热？

#### 场景 2: 间歇性中断
**症状**: 偶尔通信失败

**排查步骤**:
1. 检查 `LinkDownedCounter` - 记录断开次数
2. 检查 `SymbolErrorCounter` - 物理层问题
3. 检查光模块温度
4. 查看系统日志

---

## 最佳实践

### 监控频率
- **生产环境**: 每 5-15 分钟
- **测试环境**: 每小时
- **故障排查**: 每分钟

### 数据保留
- **原始数据**: 30 天
- **聚合数据**: 1 年
- **告警记录**: 永久

### 告警策略
- **Critical**: 立即通知，自动创建工单
- **Warning**: 每小时汇总通知
- **Info**: 每日报告

### 维护窗口
- 定期固件升级
- 光模块清洁
- 配置审计
- 性能基准测试

---

## 常用阈值参考

| 参数 | 正常范围 | 警告阈值 | 严重阈值 |
|-----|---------|---------|---------|
| 温度 | < 60°C | 70-79°C | ≥ 80°C |
| Symbol BER | 0 | > 0 | > 1e-12 |
| XmitWait 比例 | < 0.1% | 1-5% | > 5% |
| LinkDownedCounter | 0 | > 0 | > 10 |
| SymbolErrorCounter | 0 | > 0 | > 100 |
| 带宽利用率 | < 50% | 50-70% | > 70% |

---

## 平台待补充功能

结合 IBDiagnet 手册，当前平台可增强的检查项：

### 1. 光功率/偏置/电压阈值
**现状**: 只监控温度
**建议**: 引入 TX/RX 功率、偏置电流、供电电压告警

### 2. 拥塞通知计数器
**现状**: 只看 PortXmitWait
**建议**: 检查 FECN/BECN/PortXmitTimeCong

### 3. 拓扑对比
**现状**: 只展示当前拓扑
**建议**: 与期望拓扑或历史基线比较

### 4. 固件合规性
**现状**: 显示 FW 版本但不验证
**建议**: 维护支持矩阵，标记过期固件

### 5. 链路抖动分析
**现状**: 只关注 LinkDownedCounter
**建议**: 评估 LinkErrorRecoveryCounter 等抖动指标

---

## 相关文档

### 已归档文档
以下文档已移至 [ARCHIVE](./ARCHIVE/) 目录：
- ibdiagnet_health_check_guide.md
- ibdiagnet_manual_analysis.md
- ibdiagnet_manual_summary.md
- ib_analysis_pro_comparison.md

### 参考资源
- **IBDiagnet User Manual v2.13.0** (PDF)
- **IB-Analysis-Pro 项目**: 参考实现

---

**文档版本**: 1.0
**基于**: IBDiagnet User Manual v2.13.0
**维护者**: Claude Code Assistant
