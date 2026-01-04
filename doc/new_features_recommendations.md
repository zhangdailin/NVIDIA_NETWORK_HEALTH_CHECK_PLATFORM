# 新功能建议清单

基于 **IBDiagnet v2.13.0 官方文档** 与 **当前代码功能** 的对比分析

---

## 📊 分析概述

### 当前已实现的功能
✅ **12个核心操作**: xmit, hca, cable, topo, ber, port, pminfo, cc, brief, nlastic, histogram, tableau
✅ **异常检测**: 12种异常类型，3个严重级别
✅ **健康评分**: 8个类别的综合评分系统
✅ **多种输出格式**: stdout, CSV, JSON, HTML
✅ **性能计数器**: PM_DELTA, PM_INFO 表解析
✅ **拓扑可视化**: HTML 交互式拓扑图

### 文档中发现的新机会
根据 IBDiagnet 官方文档，发现以下可以增强的功能领域。

---

## 🆕 推荐新增功能

### 优先级 1: 高价值功能（立即实施）

#### 1. **历史趋势分析 (Trend Analysis)**
**功能描述**: 对比多次采样数据，分析性能趋势

**IBDiagnet 支持**:
- `--pm_pause_time` 参数支持增量采样
- 可以保存多个时间点的快照

**当前缺失**:
- 没有时间序列数据存储
- 没有趋势可视化
- 没有预测性告警

**实现建议**:
```python
# 新模块: backend/ib_analysis/trend.py
class TrendAnalyzer:
    def __init__(self, snapshots: List[Path]):
        """加载多个时间点的快照"""
        pass

    def analyze_counter_trend(self, counter_name: str):
        """分析特定计数器的趋势"""
        # 计算增长率
        # 检测异常突增
        # 预测未来值
        pass

    def detect_degradation(self):
        """检测性能退化"""
        # BER 逐渐升高
        # 错误计数器持续增长
        # 温度持续上升
        pass

    def generate_trend_report(self):
        """生成趋势报告"""
        # 时间序列图表
        # 变化率统计
        # 告警预测
        pass
```

**价值**:
- 🎯 提前发现潜在问题
- 📈 容量规划依据
- 🔮 预测性维护

**工作量**: 中等（3-5天）

---

#### 2. **拓扑对比验证 (Topology Validation)**
**功能描述**: 对比实际拓扑与预期拓扑文件

**IBDiagnet 支持**:
- `-t topology_file` 参数
- 检测拓扑变化
- 识别缺失/多余的连接

**当前缺失**:
- 没有拓扑对比功能
- 没有拓扑变更检测
- 没有拓扑合规性检查

**实现建议**:
```python
# 扩展: backend/ib_analysis/graph.py
class Graph:
    def compare_topology(self, expected_topology_file: Path):
        """对比实际拓扑与预期拓扑"""
        # 解析预期拓扑文件
        # 对比节点数量
        # 对比连接关系
        # 生成差异报告
        pass

    def detect_topology_changes(self, previous_snapshot: Path):
        """检测拓扑变化"""
        # 新增节点
        # 移除节点
        # 连接变化
        pass

    def validate_topology_rules(self, rules: Dict):
        """验证拓扑规则"""
        # 检查冗余路径
        # 验证层次结构
        # 检查对称性
        pass
```

**价值**:
- ✅ 自动化拓扑验证
- 🔍 快速发现配置错误
- 📋 合规性审计

**工作量**: 中等（3-5天）

---

#### 3. **智能告警系统 (Smart Alerting)**
**功能描述**: 基于规则和机器学习的智能告警

**IBDiagnet 支持**:
- 提供所有原始数据
- 支持自定义阈值

**当前缺失**:
- 告警规则引擎
- 告警优先级排序
- 告警去重和聚合
- 告警通知机制

**实现建议**:
```python
# 新模块: backend/ib_analysis/alerting.py
class AlertRule:
    def __init__(self, name: str, condition: str, severity: str):
        self.name = name
        self.condition = condition  # 例如: "SymbolErrorCounter > 0"
        self.severity = severity
        self.cooldown = 300  # 5分钟冷却期

    def evaluate(self, data: pd.DataFrame) -> List[Alert]:
        """评估规则，返回告警列表"""
        pass

class AlertManager:
    def __init__(self):
        self.rules = []
        self.alert_history = []

    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        pass

    def evaluate_all(self, analysis_result: Dict):
        """评估所有规则"""
        pass

    def deduplicate_alerts(self, alerts: List[Alert]):
        """去重告警"""
        # 同一节点/端口的相同告警只保留一个
        # 聚合相似告警
        pass

    def prioritize_alerts(self, alerts: List[Alert]):
        """告警优先级排序"""
        # CRITICAL > WARNING > INFO
        # 影响范围大的优先
        # 持续时间长的优先
        pass

    def send_notifications(self, alerts: List[Alert]):
        """发送告警通知"""
        # Email
        # Webhook
        # Slack/Teams
        pass
```

**预定义规则示例**:
```python
BUILTIN_RULES = [
    AlertRule("High BER", "Symbol BER > 1e-12", "CRITICAL"),
    AlertRule("Link Down", "LinkDownedCounter > 0", "CRITICAL"),
    AlertRule("High Temperature", "Temperature >= 80", "CRITICAL"),
    AlertRule("Congestion", "PortXmitWait / Duration > 0.05", "WARNING"),
    AlertRule("Firmware Mismatch", "FW version variance > 0", "INFO"),
]
```

**价值**:
- 🚨 实时问题通知
- 🎯 减少告警疲劳
- 🔧 自动化运维

**工作量**: 大（5-7天）

---

#### 4. **性能基准测试 (Baseline & Benchmarking)**
**功能描述**: 建立性能基线，对比当前状态

**IBDiagnet 支持**:
- 完整的性能计数器
- 支持定期采样

**当前缺失**:
- 没有基线存储
- 没有基线对比
- 没有性能评分

**实现建议**:
```python
# 新模块: backend/ib_analysis/baseline.py
class Baseline:
    def __init__(self, name: str, timestamp: datetime):
        self.name = name
        self.timestamp = timestamp
        self.metrics = {}  # 存储各项指标的基线值

    def capture(self, analysis_result: Dict):
        """捕获当前状态作为基线"""
        self.metrics = {
            'avg_ber': ...,
            'max_temperature': ...,
            'avg_xmit_wait': ...,
            'error_rate': ...,
        }

    def save(self, path: Path):
        """保存基线到文件"""
        pass

    @staticmethod
    def load(path: Path) -> 'Baseline':
        """从文件加载基线"""
        pass

class BaselineComparator:
    def compare(self, current: Dict, baseline: Baseline):
        """对比当前状态与基线"""
        deviations = []
        for metric, baseline_value in baseline.metrics.items():
            current_value = current.get(metric)
            deviation = (current_value - baseline_value) / baseline_value
            if abs(deviation) > 0.1:  # 10% 偏差
                deviations.append({
                    'metric': metric,
                    'baseline': baseline_value,
                    'current': current_value,
                    'deviation': deviation
                })
        return deviations

    def generate_report(self, deviations: List[Dict]):
        """生成对比报告"""
        pass
```

**价值**:
- 📊 量化性能变化
- 🎯 快速识别异常
- 📈 性能优化依据

**工作量**: 中等（3-4天）

---

### 优先级 2: 增强型功能（短期实施）

#### 5. **错误根因分析 (Root Cause Analysis)**
**功能描述**: 自动分析错误的根本原因

**实现建议**:
```python
# 新模块: backend/ib_analysis/rca.py
class RootCauseAnalyzer:
    def analyze_link_down(self, node_guid: str, port: int):
        """分析链路断开的根因"""
        # 检查物理层: BER, 温度, 光功率
        # 检查错误计数器: SymbolError, LinkIntegrityError
        # 检查历史: 是否频繁断开
        # 生成可能原因列表（按概率排序）
        pass

    def analyze_high_ber(self, node_guid: str, port: int):
        """分析高 BER 的根因"""
        # 检查光模块温度
        # 检查光功率
        # 检查线缆类型和长度
        # 检查对端设备
        pass

    def analyze_congestion(self, node_guid: str, port: int):
        """分析拥塞的根因"""
        # 检查流量模式
        # 检查路由配置
        # 检查对端设备
        # 检查应用层
        pass
```

**输出示例**:
```
Link Down Root Cause Analysis
Node: switch01, Port: 12

Possible Causes (ranked by probability):
1. [85%] Physical Layer Issue
   - High Symbol BER detected (3.2e-11)
   - Temperature elevated (75°C)
   - Recommendation: Clean fiber connector, check cooling

2. [10%] Cable Fault
   - Cable age: 3 years
   - Recommendation: Replace cable

3. [5%] Configuration Error
   - MTU mismatch detected
   - Recommendation: Verify MTU settings
```

**价值**:
- 🔍 快速定位问题
- 💡 提供修复建议
- ⏱️ 减少故障排查时间

**工作量**: 大（5-7天）

---

#### 6. **配置审计 (Configuration Audit)**
**功能描述**: 检查配置一致性和最佳实践

**IBDiagnet 数据**:
- MTU, VL, PKey 等配置信息
- 固件版本
- 设备类型

**实现建议**:
```python
# 新模块: backend/ib_analysis/config_audit.py
class ConfigAuditor:
    def audit_mtu(self):
        """审计 MTU 配置"""
        # 检查 MTU 一致性
        # 检查是否符合最佳实践（通常 4096）
        pass

    def audit_firmware(self):
        """审计固件版本"""
        # 检查版本一致性
        # 检查是否有已知漏洞
        # 检查是否为推荐版本
        pass

    def audit_vl_configuration(self):
        """审计虚拟通道配置"""
        # 检查 VL 分配
        # 检查 SL2VL 映射
        pass

    def audit_qos(self):
        """审计 QoS 配置"""
        # 检查优先级设置
        # 检查流量整形
        pass

    def generate_audit_report(self):
        """生成审计报告"""
        return {
            'compliant': True/False,
            'issues': [...],
            'recommendations': [...]
        }
```

**价值**:
- ✅ 自动化配置检查
- 📋 合规性验证
- 🔧 配置优化建议

**工作量**: 中等（4-5天）

---

#### 7. **光模块生命周期管理 (Optics Lifecycle)**
**功能描述**: 跟踪光模块健康状态和寿命

**IBDiagnet 数据**:
- 温度历史
- 光功率
- 运行时间
- 错误计数

**实现建议**:
```python
# 新模块: backend/ib_analysis/optics_lifecycle.py
class OpticsLifecycleManager:
    def calculate_health_score(self, cable_data: Dict):
        """计算光模块健康评分"""
        score = 100
        # 温度: 每超过 60°C 扣 5 分
        # 错误计数: 每个错误扣 10 分
        # 运行时间: 超过 3 年扣 5 分
        return score

    def predict_failure(self, historical_data: List[Dict]):
        """预测光模块故障"""
        # 温度趋势上升
        # BER 逐渐增加
        # 光功率衰减
        # 返回预计剩余寿命
        pass

    def recommend_replacement(self):
        """推荐更换的光模块"""
        # 健康评分 < 50
        # 预计剩余寿命 < 30 天
        # 频繁出现错误
        pass

    def generate_maintenance_plan(self):
        """生成维护计划"""
        return {
            'immediate': [...],  # 立即更换
            'within_week': [...],  # 一周内更换
            'within_month': [...],  # 一月内更换
        }
```

**价值**:
- 🔮 预测性维护
- 💰 降低故障成本
- 📅 优化维护计划

**工作量**: 中等（4-5天）

---

#### 8. **网络拓扑优化建议 (Topology Optimization)**
**功能描述**: 分析拓扑并提供优化建议

**实现建议**:
```python
# 扩展: backend/ib_analysis/graph.py
class TopologyOptimizer:
    def analyze_bottlenecks(self):
        """分析网络瓶颈"""
        # 识别高负载链路
        # 识别单点故障
        # 识别过度订阅
        pass

    def suggest_load_balancing(self):
        """建议负载均衡优化"""
        # 分析流量分布
        # 建议路由调整
        # 建议增加链路
        pass

    def suggest_redundancy(self):
        """建议冗余优化"""
        # 识别无冗余路径
        # 建议增加冗余链路
        pass

    def calculate_bisection_bandwidth(self):
        """计算对分带宽"""
        # 评估网络容量
        pass
```

**价值**:
- 📈 提升网络性能
- 🛡️ 增强可靠性
- 💡 优化投资决策

**工作量**: 大（6-8天）

---

### 优先级 3: 高级功能（长期规划）

#### 9. **机器学习异常检测 (ML-based Anomaly Detection)**
**功能描述**: 使用机器学习自动发现异常模式

**当前状态**:
- 已使用 `IsolationForest` 进行离群值检测
- 基于规则的异常检测

**增强建议**:
```python
# 扩展: backend/ib_analysis/anomaly.py
class MLAnomalyDetector:
    def __init__(self):
        self.models = {
            'ber': IsolationForest(),
            'temperature': IsolationForest(),
            'xmit': IsolationForest(),
        }

    def train(self, historical_data: List[Dict]):
        """训练模型"""
        # 使用历史正常数据训练
        pass

    def detect_anomalies(self, current_data: Dict):
        """检测异常"""
        # 使用训练好的模型
        # 返回异常评分
        pass

    def explain_anomaly(self, anomaly: Dict):
        """解释异常"""
        # 使用 SHAP 或 LIME
        # 返回特征重要性
        pass
```

**价值**:
- 🤖 自动发现未知问题
- 🎯 减少误报
- 📊 持续学习优化

**工作量**: 大（7-10天）

---

#### 10. **网络性能模拟 (Network Simulation)**
**功能描述**: 模拟配置变更的影响

**实现建议**:
```python
# 新模块: backend/ib_analysis/simulator.py
class NetworkSimulator:
    def __init__(self, topology: Graph):
        self.topology = topology

    def simulate_link_failure(self, node_guid: str, port: int):
        """模拟链路故障"""
        # 计算影响范围
        # 计算流量重路由
        # 评估性能影响
        pass

    def simulate_bandwidth_upgrade(self, links: List[Tuple]):
        """模拟带宽升级"""
        # 计算性能提升
        # 评估投资回报
        pass

    def simulate_traffic_pattern(self, pattern: Dict):
        """模拟流量模式"""
        # 预测拥塞点
        # 评估容量
        pass
```

**价值**:
- 🔮 预测变更影响
- 💰 优化投资决策
- 🧪 无风险测试

**工作量**: 非常大（10-15天）

---

#### 11. **自动化报告生成 (Automated Reporting)**
**功能描述**: 生成专业的健康检查报告

**实现建议**:
```python
# 新模块: backend/ib_analysis/reporting.py
class ReportGenerator:
    def generate_executive_summary(self, analysis_result: Dict):
        """生成执行摘要"""
        # 健康评分
        # 关键问题
        # 趋势分析
        pass

    def generate_detailed_report(self, analysis_result: Dict):
        """生成详细报告"""
        # 所有模块的分析结果
        # 图表和可视化
        # 建议和行动项
        pass

    def export_to_pdf(self, report: Dict, output_path: Path):
        """导出为 PDF"""
        # 使用 reportlab 或 weasyprint
        pass

    def export_to_word(self, report: Dict, output_path: Path):
        """导出为 Word"""
        # 使用 python-docx
        pass
```

**报告模板**:
```
NVIDIA InfiniBand Network Health Report
========================================

Executive Summary
-----------------
Overall Health Score: 85/100 (B)
Status: Healthy with Minor Issues

Critical Issues: 0
Warnings: 3
Info: 5

Key Findings
------------
1. High temperature detected on 3 optical modules
2. Firmware version mismatch on 5 switches
3. Congestion detected on 2 links

Detailed Analysis
-----------------
[各模块详细分析]

Recommendations
---------------
1. [优先级 1] Replace overheating optical modules
2. [优先级 2] Upgrade firmware to v1.2.3
3. [优先级 3] Optimize routing to reduce congestion

Appendix
--------
[原始数据、图表等]
```

**价值**:
- 📄 专业报告输出
- 👔 适合管理层汇报
- 📊 数据可视化

**工作量**: 中等（4-6天）

---

#### 12. **实时监控仪表板 (Real-time Dashboard)**
**功能描述**: Web 实时监控界面

**实现建议**:
```python
# 新模块: backend/ib_analysis/realtime.py
class RealtimeMonitor:
    def __init__(self):
        self.websocket_server = None
        self.update_interval = 60  # 秒

    def start_monitoring(self, ib_dir: Path):
        """启动实时监控"""
        while True:
            # 运行 ibdiagnet
            # 解析结果
            # 推送到前端
            time.sleep(self.update_interval)

    def push_update(self, data: Dict):
        """推送更新到前端"""
        # 通过 WebSocket 推送
        pass
```

**前端功能**:
- 实时健康评分
- 实时告警列表
- 实时性能图表
- 拓扑热力图

**价值**:
- 👀 实时可见性
- ⚡ 快速响应
- 📊 动态可视化

**工作量**: 非常大（15-20天，包含前端）

---

## 📋 功能优先级矩阵

| 功能 | 价值 | 工作量 | 优先级 | 建议时间 |
|-----|------|--------|--------|---------|
| 历史趋势分析 | 高 | 中 | P1 | 立即 |
| 拓扑对比验证 | 高 | 中 | P1 | 立即 |
| 智能告警系统 | 高 | 大 | P1 | 立即 |
| 性能基准测试 | 高 | 中 | P1 | 立即 |
| 错误根因分析 | 中 | 大 | P2 | 1-2周 |
| 配置审计 | 中 | 中 | P2 | 1-2周 |
| 光模块生命周期 | 中 | 中 | P2 | 1-2周 |
| 拓扑优化建议 | 中 | 大 | P2 | 2-3周 |
| ML 异常检测 | 中 | 大 | P3 | 1-2月 |
| 网络性能模拟 | 低 | 非常大 | P3 | 2-3月 |
| 自动化报告 | 中 | 中 | P3 | 1-2月 |
| 实时监控仪表板 | 高 | 非常大 | P3 | 2-3月 |

---

## 🎯 快速实施路线图

### 第一阶段（1-2周）
1. ✅ 历史趋势分析
2. ✅ 拓扑对比验证
3. ✅ 性能基准测试

### 第二阶段（3-4周）
4. ✅ 智能告警系统
5. ✅ 配置审计
6. ✅ 光模块生命周期

### 第三阶段（5-8周）
7. ✅ 错误根因分析
8. ✅ 拓扑优化建议
9. ✅ 自动化报告

### 第四阶段（9-12周）
10. ✅ ML 异常检测
11. ✅ 实时监控仪表板

---

## 💡 实施建议

### 技术栈建议
- **趋势分析**: pandas, matplotlib, prophet (时间序列预测)
- **告警系统**: APScheduler (定时任务), smtplib (邮件), requests (Webhook)
- **机器学习**: scikit-learn, xgboost, shap (可解释性)
- **报告生成**: reportlab (PDF), python-docx (Word), jinja2 (模板)
- **实时监控**: FastAPI WebSocket, Redis (缓存), Celery (任务队列)

### 数据存储建议
- **时间序列数据**: InfluxDB 或 TimescaleDB
- **基线数据**: JSON 文件或 SQLite
- **告警历史**: PostgreSQL
- **配置数据**: YAML 文件

### API 设计建议
```python
# 新增 API 端点
POST /api/trend/analyze          # 趋势分析
POST /api/topology/validate      # 拓扑验证
POST /api/baseline/create        # 创建基线
POST /api/baseline/compare       # 对比基线
POST /api/alerts/rules           # 管理告警规则
GET  /api/alerts/active          # 获取活动告警
POST /api/rca/analyze            # 根因分析
GET  /api/audit/config           # 配置审计
GET  /api/optics/lifecycle       # 光模块生命周期
POST /api/report/generate        # 生成报告
WS   /api/realtime/monitor       # 实时监控 WebSocket
```

---

## 📊 投资回报分析

### 高 ROI 功能
1. **智能告警系统**: 减少 50% 的故障响应时间
2. **历史趋势分析**: 提前 1-2 周发现问题
3. **错误根因分析**: 减少 70% 的故障排查时间
4. **光模块生命周期**: 降低 30% 的意外故障

### 中 ROI 功能
5. **拓扑对比验证**: 减少配置错误
6. **配置审计**: 提升合规性
7. **性能基准测试**: 量化性能变化

### 长期 ROI 功能
8. **ML 异常检测**: 持续优化检测能力
9. **实时监控仪表板**: 提升运维效率
10. **网络性能模拟**: 优化投资决策

---

## 🚀 总结

基于 IBDiagnet 官方文档和当前代码分析，我们识别出 **12 个高价值的新功能**。建议优先实施以下 4 个功能：

1. 🔥 **历史趋势分析** - 预测性维护的基础
2. 🔥 **智能告警系统** - 自动化运维的核心
3. 🔥 **拓扑对比验证** - 配置管理的关键
4. 🔥 **性能基准测试** - 性能优化的依据

这些功能将显著提升平台的实用价值，从被动检测转向主动预防，从人工分析转向智能诊断。

---

**文档版本**: 1.0
**创建日期**: 2026-01-03
**作者**: Claude Code (呆哥科技)
