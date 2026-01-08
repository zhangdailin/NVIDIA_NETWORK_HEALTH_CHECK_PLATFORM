# Frontend UI 重构计划

目标：把 AnalysisService 里所有检查项以统一面板/卡片形式呈现，用户可以快速看到“XXX 检查 ✔ / ⚠”或展开详情。

## 1. 信息架构

### 1.1 全局结构
- 顶部保持 Overview，改为“健康检查仪表板”，按检查项列卡片 `Cable/Xmit/BER/...` ，每张卡显示：
  - 状态（OK/警告/错误），依据对应数据集是否存在异常（如 `*_summary`、`*_data` 中的 `IBH Anomaly` 等）
  - 异常数量（warning/critical）
  - 快速入口（点击跳转下方详情区）
- 下方 tab 区按检查类别分组（例如“网络拓扑”“性能/计数器”“安全/配置”等），各组内列出相应 `sections`。

### 1.2 示例分组
| 分组 | 包含检查 |
|------|---------|
| 连线/链路 | Cable, Cable Enhanced, Links |
| 拥塞与带宽 | Xmit, Per-Lane Performance |
| 误码 | BER, BER Advanced |
| 节点与固件 | HCA, System Info |
| 传感器 | Fan, Temperature, Power, Power Sensors, Temp Alerts |
| 路由/拓扑 | Switches, Routing, Routing Config, Port Hierarchy |
| 性能计数器 | MLNX Counters, PM Delta, PCI Performance |
| QoS & N2N | QoS, N2N Security |
| 诊断扩展 | PHY Diagnostics, Extended Port/Node/Switch Info, Buffer Histogram, Neighbors |
| 安全/配置 | PKEY, VPorts, AR Info, SHARP, FEC Mode, Credit Watchdog |

## 2. 数据绑定

1. `analysis_service.py` 已返回每个检查的 `*_data/summary/total_rows`；在前端定义统一映射表 `const checkDefinitions = { cable: { label, dataKey, summaryKey, severityExtractor } }`。
2. Overview 卡片根据该表遍历一次，调 `severityExtractor`（例如检查 summary 中 critical 数、或 data 里 IBH Anomaly）确定状态。
3. Tab 内容：复用 `renderSection(key)` 现有逻辑，但外层按分组渲染，保留搜索/分页等。

## 3. 交互与样式

1. Overview 卡支持筛选：只看异常、按类别过滤。
2. 每个卡片提供“查看详情”按钮 -> 滚动/切换到对应 tab。
3. warning_by_category 单独以“警告分类”组件展示，替换目前只在 Firmware/Pci card 中引用的方式。
4. 支持 Search 全局（GUID/端口），在所有 tab 中筛选。

## 4. 实施步骤

1. **数据映射层**：创建 `checkDefinitions`，封装状态计算方法。
2. **Overview 重构**：新增 `HealthCheckBoard` 组件，读取 definitions 显示卡片。
3. **Tab 分组**：在 `sections` 数组外，定义 `sectionGroups`（group label + [keys]），调整渲染逻辑。
4. **警告分类组件**：改造 `warnings_by_category` 的消费方式，放置在 Overview 或单独 tab。
5. **样式统一**：卡片采用一致的颜色/图标，严重度用红/橙/绿，支持虚拟滚动。

## 5. 后续扩展

- 若后端新增检查，只需在 `checkDefinitions` 中配置即可自动出现在 Overview + Tab。
- 可引入“检查历史”视图，展示不同上传之间的变化（依赖后端历史接口）。
