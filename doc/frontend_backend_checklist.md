# Frontend vs Backend Checks

## Backend 流水线（AnalysisService）

- Cable Service（链路/跳线告警）
- Xmit Service（拥塞/发送等待）
- BER Service、BER Advanced Service（原始/PHY_DB16）
- HCA Service（固件/驱动） + Firmware
- Fan / Temperature / Power（传感器、风扇）
- Switch / Routing / Routing Config（拓扑与路由）
- Port Health / Port Hierarchy / Links（端口健康、层级、连线）
- QoS / SM Info / PKEY / VPorts
- MLNX Counters / PM Delta（性能计数器、delta）
- Extended Port / Node / Switch Info
- AR Info / SHARP / FEC Mode / PHY Diagnostics
- Neighbors / Buffer Histogram
- Power Sensors / Temp Alerts / Credit Watchdog
- PCI Performance
- Cable Enhanced（额外光缆检查）
- Per-Lane Performance
- N2N Security
- Topology Checker（独立生成 issue rows）
- Warnings Service（ibdiagnet warnings 汇总）

> 以上每个 `_run_*` 方法都会向返回 payload 中写入 `*_data`, `*_summary`, `*_total_rows` 等字段。

## 前端标签（App.jsx）

- Overview（汇总卡片）  
- Cable、Xmit、BER、BER Adv、Cable Enh、Per-Lane、HCA、Latency、Fan、Temperature、Power  
- Switches、Routing、Port Health、Links、QoS、SM Info、Port Hierarchy  
- MLNX Counters、PM Delta、VPorts、PKEY、System Info  
- Extended Port / Node / Switch Info、AR Info、SHARP、FEC Mode、PHY Diagnostics  
- Neighbors、Buffer Histogram、Power Sensors、Routing Config、Temp Alerts、Credit Watchdog、PCI Performance  
- N2N Security

> 上述标签均在 `sections` 数组中定义，通过 `renderSection()` 显示。若需新增展示，只要后端 payload 中存在 `foo_data` / `foo_summary`，即可在该列表中添加 `key: 'foo'` 的 entry。

## 缺失/待补充

- 后端还有 **WarningsService**（`warnings_by_category`，已在 Firmware/Pci warning 卡片中使用）与 **BriefService** 输出；Overview 目前只展示少量卡片，如果需要更全面的“检查项看板”，可以引入新的组件，逐项显示 “Cable 检查 ✅/⚠️” 等摘要。
- `analysis_service` 还会返回 `system_info`, `neighbors`, `ar_info` 等数据，确保对应 tabs 已通过 props 接入（现有 `sections` 已包含全部 key）。
