# IBDiagnet User Manual v2.13.0 摘要

> 数据来源：`/test_data/ibdiagnet-infiniband-fabric-diagnostic-tool-user-manual-v2-13-0.pdf`

## 1. 工具定位与运行模式
- **目标**：对 InfiniBand fabric 执行拓扑发现、链路与设备健康检查、性能数据采集及问题报告。
- **运行模式**：
  - *本地*：在 fabric 内的 HCA/交换机节点运行，直接访问 Subnet Manager。
  - *远程*：通过 SM 对远端 fabric 执行诊断，可配合权限受控的 SM 账号。
  - *离线*：加载已有的 `ibdiagnet.db_csv` 或 `net_dump` 快照离线分析。

## 2. 核心诊断能力
1. **拓扑验证**：发现所有 GUID、检查链路状态/宽度/速度、对比预期拓扑、检测重复 GUID。
2. **链路质量与信号完整性**：
   - 监控速率 (SDR ~ NDR)、宽度 (1x/4x/8x/12x)、`PortState`、`PortPhysicalState`。
   - 收集 BER：Raw / Effective / Symbol 三种级别。
3. **性能监控 (PM Counters)**：
   - 流量：`PortXmitData`, `PortRcvData`, `PortXmitPkts`, `PortRcvPkts`。
   - 拥塞：`PortXmitWait`, `PortXmitTimeCong`, `PortRcvFECN/BECN`。
   - 错误：`SymbolErrorCounter`, `LinkDownedCounter`, `PortRcvErrors`, `PortXmitDiscards`, `PortXmit/PortRcvConstraintErrors`, `LocalLinkIntegrityErrors`, `ExcessiveBufferOverrunErrors` 等。
4. **光模块与线缆监控**：温度、电压、TX/RX 光功率、Bias Current、厂商/PN/SN/FW 版本及温度/功率阈值告警。
5. **固件与配置检查**：提取 HCA/交换机 FW 版本、PSID、PN、驱动配置，辅助识别不一致或过期的硬件。

## 3. 输出与文件结构
- `ibdiagnet2.topology`：拓扑全景；`ibdiagnet2.db_csv`/`*.db_csv`：结构化表格结果。
- `ibdiagnet2.net_dump`：二进制 fabric dump，可供二次分析。
- `ibdiagnet2.lst`：节点/端口摘要。
- `ibdiagnet.log` 与 `ibdiagnet.err`：运行日志和异常。
- HTML/CSV 选项：可通过 `--html`, `--csv`, `--out_dir` 指定输出格式和目录。

## 4. 命令行要点
- **基本命令**：`ibdiagnet --pm --netchecks --extended_speeds --top`。
- **范围控制**：`--max_hops`, `--guids_file`, `--skip_unhealthy`。
- **巡检频率**：建议定期采集 (如每日/每周)，并清理计数器 (`--clear_counters`) 以获取增量。
- **安全**：支持 `--use_ssl`, `--user`, `--password` 连接 SM；可通过 `ufm` REST 导出数据再离线分析。

## 5. 指标阈值与健康策略
- **温度**：≥70 °C 告警，≥80 °C 视为严重；需结合风道、灰尘、模块老化处理。
- **BER**：
  - Raw/Effective/Symbol 需保持 ≤1e-12；若 Effective ≪ Raw 说明 FEC 正在补偿，需关注。
  - Symbol BER 异常常由脏连接器、弯折光纤、过长链路造成。
- **拥塞**：`PortXmitWait` >1% 表示轻度拥塞，≥5% 为严重；`NUM RTT`、`MIN/AVG RTT` 配合分析路径不平衡。
- **链路稳定性**：反复出现 `LinkDownedCounter` 或 `LinkErrorRecoveryCounter` 表明物理问题（电缆、模块、端口）。

## 6. 典型工作流
1. **全网扫描**：运行 `ibdiagnet --extended_speeds --pm --netchecks --out_dir <dir>`，保存完整输出。
2. **分类分析**：
   - 拓扑与连通性 → `*.topology`, `*.lst`, `net_dump`。
   - 性能与拥塞 → `pm` 表、`PortXmitWait`, `FECN/BECN`。
   - 光模块 → `ibdiagnet.cable`: 温度/功率/厂商。
   - 错误事件 → `ibdiagnet.err`, `LinkDowned`，并结合 `syslog/SM`。
3. **对照阈值**：依据手册推荐阈值/最佳实践，标记 Critical / Warning / Info。
4. **输出健康报告**：结合拓扑截图、计数器表格、问题列表与整改建议。

## 7. 最佳实践
- 在维护窗口前/后各采集一次，比较差异确认修复效果。
- 对关键链路开启 `--cable_health` 和温度监控，主动替换超阈模块。
- 将 `ibdiagnet` 输出纳入 CI/CD 或自动巡检平台（如当前项目的 FastAPI + React），实现上传解析、健康评分、拓扑上色与知识库联动。
- 长期保留 `db_csv`/`net_dump` 历史，以便回溯问题发生时间与范围。

本摘要可作为 `/doc` 目录下的快读材料，帮助开发者在无需逐页阅读 PDF 的情况下掌握 IBDiagnet 手册的关键要点。

---

## 8. 与当前平台的差距及新增检查建议
结合手册要求与本项目的 `ib_analysis` 模块/前端实现，尚有以下健康检查空缺，可考虑逐步补齐：

1. **光功率 / 偏置 / 电压阈值**
   - *现状*: `CableManager` 仅在 `backend/ib_analysis/cable.py:329` 对温度打分，未利用 `TXBias*`, `TXPower*`, `RXPower*`, `SupplyVoltage*` 等列。
   - *建议*: 参照手册 2.4 节，引入 TX/RX 功率上下限、偏置电流和供电电压告警，写入 `IBH_ANOMALY`，并在 `health_score` 中体现“光模块功率异常”分类。

2. **拥塞通知计数器 (FECN/BECN/PortXmitTimeCong)**
   - *现状*: `xmit` 和 `cc` 模块只看 `PortXmitWait`、RTT，未检查 `PortRcvFECN/BECN`, `PortXmitTimeCong`。
   - *建议*: 依据手册 2.3 节设置阈值（如 `FECN/BECN > 0`, `PortXmitTimeCong%`），在 `xmit.get_anomalies` 或 `cc` 中加入检测，前端 Congestion 卡片展示这类热点。

3. **拓扑对比（Golden Topology）**
   - *现状*: Graph 仅展示现状拓扑与健康着色，没有与期望拓扑或历史基线比较。
   - *建议*: 新增 `topo_diff` 操作，解析手册推荐的 `--top` 文件，对异常节点/速率/连接进行打分，或在 `health_score` 新增“topology_expectation”维度。

4. **固件/PSID 合规性**
   - *现状*: `HcaManager` 输出 FW/PSID，但缺少与推荐列表比对。
   - *建议*: 维护一份支持矩阵（JSON/YAML），运行时标记过期 FW 或混布 PSID，映射到 `config` 类问题。

5. **链路恢复/抖动分析**
   - *现状*: `_check_specific_issues` 只关心 `LinkDownedCounter`，未评估 `LinkErrorRecoveryCounter` 等抖动指标。
   - *建议*: 依据手册 5. 节规则，对“短时间多次恢复”打分，并在前端 Issues 中给出“链路抖动”建议。

这些新增项均可基于现有 `db_csv` 数据完成，优先级可从监控空白程度排序（光功率/电压 > 拥塞通知 > 拓扑对比 > 固件合规 > 抖动分析）。
