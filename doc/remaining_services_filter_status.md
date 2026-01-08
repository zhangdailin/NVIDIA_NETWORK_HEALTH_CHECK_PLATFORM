# 剩余服务过滤状态检查
**日期**: 2026-01-07

---

## 📋 需要检查的服务列表

以下23个服务有Severity字段,需要逐个检查是否已添加过滤:

### ✅ 已完成过滤的服务 (5个):

1. ✅ ber_service.py
2. ✅ ber_advanced_service.py
3. ✅ cable_enhanced_service.py
4. ✅ temperature_service.py
5. ✅ power_service.py

---

### ⏳ 待处理的服务 (18个):

#### 高优先级 (数据量可能很大):

6. ⏳ port_health_service.py - 端口健康 (可能有数万端口)
7. ⏳ mlnx_counters_service.py - Mellanox计数器 (可能有数万端口)
8. ⏳ extended_port_info_service.py - 扩展端口信息

#### 中优先级:

9. ⏳ per_lane_performance_service.py - 每通道性能
10. ⏳ n2n_security_service.py - 节点到节点安全
11. ⏳ pci_performance_service.py - PCIe性能
12. ⏳ temp_alerts_service.py - 温度告警
13. ⏳ power_sensors_service.py - 功率传感器
14. ⏳ credit_watchdog_service.py - Credit watchdog

#### 低优先级 (数据量较小或访问频率低):

15. ⏳ routing_service.py
16. ⏳ routing_config_service.py
17. ⏳ qos_service.py
18. ⏳ neighbors_service.py
19. ⏳ fec_mode_service.py
20. ⏳ extended_switch_info_service.py
21. ⏳ extended_node_info_service.py
22. ⏳ buffer_histogram_service.py
23. ⏳ pm_delta_service.py
24. ⏳ ar_info_service.py

---

## 🎯 优先处理建议

### 立即处理 (数据量大):
- port_health_service.py
- mlnx_counters_service.py
- extended_port_info_service.py

### 可选处理 (根据实际使用情况):
- 其他15个服务可以按需添加

### 批量处理模式:

```python
# 通用过滤模式 (适用于所有服务)
# 在循环构建record后:

record = {
    "NodeGUID": node_guid,
    "NodeName": node_name,
    "Severity": severity,
    # ... 其他字段
}

# 🆕 只添加异常 (过滤掉normal)
if severity != "normal":
    records.append(record)
```

---

## 📝 实施策略

### 策略1: 按需添加 (推荐)
- 优点: 避免过度优化
- 缺点: 需要等用户反馈性能问题

### 策略2: 批量添加
- 优点: 一次性完成所有优化
- 缺点: 可能优化了不需要优化的服务

### 策略3: 创建配置选项
```python
# 环境变量控制
FILTER_NORMAL_DATA = os.getenv("FILTER_NORMAL_DATA", "true").lower() == "true"

if FILTER_NORMAL_DATA and severity != "normal":
    records.append(record)
else:
    records.append(record)
```

---

## 📊 预期效果

假设每个服务平均有1000条数据,其中5%异常:

| 服务类型 | 修改前 | 修改后 | 减少 |
|---------|--------|--------|------|
| 高频大数据 | 10,000条 | 500条 | 95% |
| 中频中数据 | 1,000条 | 50条 | 95% |
| 低频小数据 | 100条 | 5条 | 95% |

**总体**: 预计可减少90-95%的数据传输量

---

**文档更新**: 2026-01-07
**维护者**: Claude Code Assistant
