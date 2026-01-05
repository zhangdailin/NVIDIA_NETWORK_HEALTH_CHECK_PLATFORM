# 近期工作总结

1. **前端构建修复**
   - `frontend/src/App.jsx` 改为内联 `export default function App()`，并清理尾部多余的 `export` 语句，解决 `vite build` 阶段的 “Unexpected export” 异常。
   - 同时删除残留的非 ASCII 文本（比如温度显示中的 `°`），保持代码库统一编码。

2. **光模块温度数据稳定性**
   - `backend/ib_analysis/cable.py` 的 `temperature_stoi` 现在会安全地处理空字符串、`NA`、带引号的值，避免在解析缺失温度时抛出 `IndexError`。

3. **健康得分增强**
   - 在 `backend/ib_analysis/health_score.py` 中新增链路恢复计数器（`LinkErrorRecoveryCounter`/`Ext`）检测，结合严重度映射到新的知识库解释（`LINK_RECOVERY`），前端 Issues 列表能够提示链路抖动风险。

4. **拥塞控制异常扩展**
   - `backend/ib_analysis/cc.py` 引入 FECN/BECN 以及 `PortXmitTimeCong` 的异常构建，复用与 `xmit` 模块相同的权重计算逻辑，使 CC 报表也能输出这些拥塞告警。

5. **固件 / PSID 合规检查**
   - 新增 `backend/ib_analysis/core/references/fw_matrix.json` 以声明合规 PSID、最低固件版本。
   - `backend/ib_analysis/hca.py` 加载该矩阵，为每个节点标注 `PSID Compliant`、`FW Compliant`、`Recommended FW` 等字段，并生成新的异常枚举 `IBH_PSID_UNSUPPORTED` / `IBH_FW_OUTDATED`。
   - 对应地更新 `backend/ib_analysis/anomaly.py`、`health_score.py`、`core/explanations.py`，确保健康得分与前端知识库能识别这些配置类问题。

6. **构建与验证**
   - 运行 `npm run build` 验证前端修复。
   - 使用 `python -m compileall backend/ib_analysis/hca.py` 检查 HcaManager 的语法正确性。

7. **待办方向**
   - 扩展 `/upload/ibdiagnet` 以支持只有 `net_dump` 的离线数据源。
   - 在 `core/operations` 中实现拓扑基线对比操作。
   - 为固件/PSID 合规加入单元测试和示例数据，确保矩阵调整后的回归可测。

8. **原生 services 替换旧版 `ib_analysis`**
   - 在 `backend/services/` 内实现 `CableService`、`XmitService`、`BerService`、`HcaService`、`BriefService`、`TopologyService` 等模块，由新的 `AnalysisService` 统一编排，FastAPI 入口不再导入 `ib_analysis`，上传流程直接消费解析后的 `*.db_csv`。
   - `AnalysisService` 负责运行多线程分析、构建简报、计算健康分、生成拓扑，同时提供统一的 `IbdiagnetDataset` 缓存，避免重复解析。
   - 为了返回稳定的 JSON，`AnalysisService` 现对整个响应做递归清洗，自动把 `NaN`/`inf`/`pd.NA` 转成 `null`，并把 numpy 数值降级为原生 `int/float`，解决了 `ValueError: Out of range float values are not JSON compliant: nan` 以及前端收到空白数据的问题。

9. **运行状态验证**
   - 使用 `python - <<'PY' ...` 直接调用 `AnalysisService.analyze_ibdiagnet`，基于样例数据 `uploads/d80e2907-0bd7-47bf-a251-e061c0c1bae7` 验证 `cable/xmit/hca/data` 均有数万行记录，`health.issues` 可用，拓扑 HTML 正常生成。
   - 通过 `npm run dev` / `vite` 本地启动，确认前端能够消费新的 `health`、`cable_data`、`xmit_data` 等字段。

10. **前端大表渲染优化**
   - `frontend/src/App.jsx` 的 `renderJsonTable` 仅预览首 500 行数据，并在表格下方提示“Showing first 500 of N rows for preview”，避免一次性渲染数万行导致页面空白或浏览器挂起。

11. **分析结果预览限流**
   - `backend/services/analysis_service.py` 增加 `MAX_PREVIEW_ROWS=2000`，API 仅返回每张表的 2000 行以内预览，并附带 `*_total_rows` 与 `preview_row_limit` 元数据，确保响应体不会造成浏览器内存溢出。
   - `renderJsonTable` 读取上述元数据并提示“Showing first X of Y rows”，如果服务器做了预览限流也会显示限制数；用户若需完整数据，可直接下载上传目录中的 `ibdiagnet2` 输出。

12. **BER 兼容性补强**
   - `backend/services/ber_service.py` 在缺少 `PM_BER` 时会回退到 `EFF_BER` 或 `WARNINGS_SYMBOL_BER_CHECK`，并把 BER 告警事件（如 `BER_NO_THRESHOLD_IS_SUPPORTED`）转换成统一的 `SymbolBERSeverity` 列，因此前端不再出现 “Bit Error Rate ... No data available”。

13. **前端数据分页**
   - 新增 `PaginatedTable` 组件（`frontend/src/App.jsx`），每个数据表分页展示 100 行，并在底部提供页码、上一页/下一页按钮以及 preview 限制说明，避免一次性渲染 2000 行仍导致页面笨重。
   - CSV 预览同样复用分页组件，保持一致的交互体验。

14. **字段精简与拓扑标注**
    - `CableService`、`XmitService`、`BerService`、`HcaService` 通过新的 `TopologyLookup` 读取 `NODES`/`LINKS` 表，为每个端口注入 `Node Name` 与 `Attached To`，从而让分析简报恢复“节点名/对端”列。
    - 同时为各数据集定义白名单列，只输出手册提到的指标（温度、电压、光功率告警、`PortXmitWait`/FECN/BECN、固件合规等），避免 UI 被 100+ 个恒定为零的列淹没。

15. **链路速率/宽度合规检查**
    - `XmitService` 现在会加载 `PORTS` 表，将 `LinkWidthActv/Sup` 与 `LinkSpeedActv/Sup` 解码成人类可读的 `ActiveLinkWidth/Speed`，并且比较支持 vs. 实际值，只要端口被强制降速或窄化就标记 `LinkComplianceStatus=Downshift`。
    - 新增 `AnomlyType.IBH_LINK_DOWNSHIFT`，写入健康分“Topology”类别，前端 Analysis Brief 也会显示 `Active/Supported` 列，帮助定位速率不匹配的链路。

16. **Credit Watchdog 监控**
    - 在 `XmitService` 中解析 `CREDIT_WATCHDOG_TIMEOUT_COUNTERS`，聚合 `total_port_credit_watchdog_timeout` 并传回 `CreditWatchdogTimeout` 列。非零会触发新的 `IBH_CREDIT_WATCHDOG` 异常（计入 “congestion”），提示存在严重的缓冲区/信用耗尽问题。
17. **端口状态审计**
    - `XmitService` 额外从 `PORTS` 表回填 `PortState`/`PortPhyState` 并解码为文本（Active/LinkUp 等），Analysis Brief 再次展示端口状态。
    - `health_score` 对这些字段早有检查，如今有了真实数据，非 Active/LinkUp 的端口会被自动识别为拓扑问题。

18. **拓扑重复检测**
    - 新增 `TopologyChecker` 读取 `NODES` 表，若发现重复 GUID 或重复 NodeDesc，会生成 `topology_data` 并以 `IBH_DUPLICATE_GUID` / `IBH_DUPLICATE_DESC` 的形式打分，让健康报告暴露命名冲突；文档中提到的“唯一 GUID/Node 名称”要求因此得以落地。
19. **线缆长度/介质合规**
    - `CableService` 提供 `LengthSMFiber/LengthCopperOrActive/TypeDesc/SupportedSpeedDesc`，并依据手册阈值（例如 HDR 被动铜线 ≤5m）标注 `CableComplianceStatus`，方便在前端快速筛出过长或介质不匹配的链路。

20. **风扇/机箱健康检查**
    - 打通新的 `FanService`（`backend/services/fan_service.py`），合并 `FANS_SPEED/FANS_THRESHOLDS/FANS_ALERT` 表并注入 `Node Name`/`SensorIndex`，同步生成 `FanStatus` 与 `FanAlert` 偏差。
    - `AnalysisService` 现在会并行运行风扇服务，收集各模块的 anomaly DataFrame，统一折叠为 `IBH Anomaly` 记录，再交由 `health_score` 扣分。新增 `fan_data`/`fan_total_rows` 字段，并把 `IBH_FAN_FAILURE` 计入 Errors 类别。
    - 前端 `App.jsx` 增加 “Fans” 选项卡和 `buildFanInsights` 卡片（每页 100 行分页），突出最低转速报警的机箱；上传结果可直接查看偏离阈值的传感器及推荐措施。

21. **链路/端口/延迟规范化**
    - `TopologyLookup` 现在会注入 `Node Type`、对端 GUID/Port 与类型，`XmitService` 基于这些字段输出 `NeighborPortState/NeighborIsActive` 并在对端为 Spine/Switch 时提升 `IBH_LINK_DOWNSHIFT` 权重；`health_score` 也只在“邻居仍为 Active/LinkUp”时警告本端端口，减少误报。
    - `CableService` 合并端口速率解码，比较 `LocalActiveLinkSpeed` 与 `SupportedSpeedDesc`，并在速率不匹配或 HDR+ SMF 缺失长度时生成 `CableSpeedStatus`，统一映射到新的 `IBH_CABLE_MISMATCH`。
    - 新增 `HistogramService`（`backend/services/histogram_service.py`）读取 `PERFORMANCE_HISTOGRAM_*`，估算 median/p99 RTT 与尾部占比，将重尾端口打标为 `IBH_UNUSUAL_RTT_NUM`；前端提供 “Latency” 选项卡分页展示这些直方图指标。

22. **期望拓扑对比**
    - `TopologyDiffService`（`backend/services/topology_diff_service.py`）支持加载 `config/expected_topology.json` 或 `EXPECTED_TOPOLOGY_FILE` 指定的基线，校验缺失节点、缺失链路及速率/宽度低于期望的端口。文件格式示例：

      ```json
      {
        "nodes": [{"guid": "0xabc", "name": "Leaf-01"}],
        "links": [
          {"src_guid": "0xabc", "src_port": 1, "dst_guid": "0xdef", "dst_port": 10, "min_speed": "HDR", "min_width": "8X"}
        ]
      }
      ```

    - `AnalysisService` 自动附加这些差异到 `topology_data`，并以 `IBH_ASYM_TOPO`/`IBH_LINK_DOWNSHIFT` 形式计入健康得分；只要在配置目录维护节点/链路 JSON，上传 ibdiagnet 即可一键定位偏离基线的拓扑。

> 本文档记录在 `/doc/work_summary.md`，无需另行上传其他文件。
