# 2026-01-05 工作内容总结

1. **拓扑期望基线校验**
   - 新增 `backend/services/topology_diff_service.py`，支持读取 `config/expected_topology.json`（或 `EXPECTED_TOPOLOGY_FILE` 环境变量）描述的节点/链路基线，比较 ibdiagnet 实际拓扑，找出缺失节点、缺失链路、速率/宽度低于期望的端口，并以 `IBH_ASYM_TOPO`、`IBH_LINK_DOWNSHIFT` 形式输出。
   - `AnalysisService` 自动调用上述服务，将差异合并进 `topology_data` 和健康评分流程，使上传 ibdiagnet 时即可看到偏离基线的拓扑项。

2. **邻居感知链路/端口检查**
   - `TopologyLookup` 现提供 `Node Type`、对端 GUID/Port；`XmitService` 使用这些信息生成 `NeighborPortState/NeighborIsActive`、对端端口号，健康评分只在“邻居 Active/LinkUp”时警告本端端口不活跃，并在对端为 Switch/Spine 时提高 `IBH_LINK_DOWNSHIFT` 权重。
   - `CableService` 合并端口速率解码，新增 `LocalActiveLinkSpeed` 与 `CableSpeedStatus`，检测 HDR SMF 无长度或速率不匹配情形，映射到新的 `IBH_CABLE_MISMATCH`。

3. **延迟直方图与前端展示**
   - 新建 `HistogramService` 解析 `PERFORMANCE_HISTOGRAM_PORTS_DATA`，估算 median/p99 RTT 及尾部占比，超过 5× 或 top bucket ≥20% 即标记 `IBH_UNUSUAL_RTT_NUM`。
   - 前端 `App.jsx` 增加 “Latency” 选项卡，分页展示 histogram 数据并生成告警卡片；同时扩展 Fans 视图、节点/对端列等，配合新的后端字段。

