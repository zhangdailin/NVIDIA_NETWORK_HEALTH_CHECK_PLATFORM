# 前后端字段名映射修复总结

## 修复日期
2026-01-07

## 问题描述
前端分析组件和后端服务返回的数据字段名不一致，导致数据显示不正确。

## 已修复的组件

### 1. BERAnalysis.jsx ✅
**问题**: 后端有两个BER数据源，字段名不统一
- `ber_service.py` 返回: `SymbolBERSeverity`, `Node Name` (带空格)
- `ber_advanced_service.py` 返回: `Severity`, `NodeName` (无空格)

**修复内容**:
```javascript
// 严重程度字段
row.SymbolBERSeverity || row.Severity

// 节点名称
row['Node Name'] || row.NodeName

// BER Log10值
row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10

// BER值
row.EffectiveBER || row['Effective BER']
row.RawBER || row['Raw BER']

// FEC计数器
row.FECCorrectedCW || row.FECCorrected || row.FECCorrectedBlocks
row.FECUncorrectedCW || row.FECUncorrected || row.FECUncorrectableBlocks

// 事件/问题
row.EventName || row.Issues
```

**文件位置**: [BERAnalysis.jsx](../frontend/src/BERAnalysis.jsx)

---

### 2. CableAnalysis.jsx ✅
**问题**: 后端返回 `PN` 和 `SN`，前端期待 `Part Number` 和 `Serial Number`

**修复内容**:
```javascript
// 节点名称
row['Node Name'] || row.NodeName

// 部件号 - 后端返回'PN'
row.PN || row['Part Number'] || row.PartNumber

// 序列号 - 后端返回'SN'
row.SN || row['Serial Number'] || row.SerialNumber

// 长度字段
row.LengthCopperOrActive || row.LengthSMFiber || row.Length

// 厂商
row.Vendor || row['Vendor Name']

// 线缆类型
row.TypeDesc || row['Cable Type']

// 供电电压
row.SupplyVoltageReporting || row['Supply Voltage Reporting']
```

**后端字段** (`cable_service.py` DISPLAY_COLUMNS):
- `PN` (不是 `Part Number`)
- `SN` (不是 `Serial Number`)
- `Node Name` (带空格)
- `Temperature (c)` (带空格和括号)

**文件位置**: [CableAnalysis.jsx](../frontend/src/CableAnalysis.jsx)

---

### 3. CongestionAnalysis.jsx ✅
**问题**: 发现3处NodeName字段映射遗漏

**修复内容**:
```javascript
// Line 35: 分析函数中
const nodeName = row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown'

// Line 88: 搜索过滤中
String(row['Node Name'] || row.NodeName || '').toLowerCase().includes(term)

// Line 408: 表格渲染中
{row['Node Name'] || row.NodeName || 'N/A'}

// 其他字段都已正确:
row.NodeGUID || row['Node GUID']  // 正确
row.PortNumber || row['Port Number']  // 正确
row.LinkDownedCounter || row.LinkDownedCounterExt  // 正确
```

**文件位置**: [CongestionAnalysis.jsx](../frontend/src/CongestionAnalysis.jsx)

---

### 4. FaultSummary.jsx ✅
**问题**: 多处字段映射不完整，未支持多种字段名变体

**修复内容**:

#### 线缆问题部分:
```javascript
// 节点名称 - 所有位置
row['Node Name'] || row.NodeName

// 部件号和序列号
row.PN || row['Part Number'] || row.PartNumber
row.SN || row['Serial Number'] || row.SerialNumber

// 线缆详情
row.TypeDesc || row['Cable Type']
row.LengthCopperOrActive || row.LengthSMFiber || row.Length
row.SupplyVoltageReporting || row['Supply Voltage Reporting']
```

#### BER问题部分:
```javascript
// 支持两种严重程度字段
row.SymbolBERSeverity || row.Severity

// 支持三种BER Log10值
row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10

// BER值
row.EffectiveBER || row['Effective BER']
row.RawBER || row['Raw BER']

// 事件/问题
row.EventName || row.Issues
```

#### 其他问题部分:
```javascript
// 节点GUID - 所有位置
row.NodeGUID || row['Node GUID']

// 端口号 - 所有位置
row.PortNumber || row['Port Number']

// 固件版本
row.FW_Version || row.FirmwareVersion

// 部件号
row.PartNumber || row.PN

// 温度
row.Temperature || row.TemperatureReading
```

**文件位置**: [FaultSummary.jsx](../frontend/src/FaultSummary.jsx)

---

### 5. App.jsx ✅
**问题**: Insight builder函数中字段映射不完整

**修复内容**:

#### buildBerInsights (lines 292-315):
```javascript
// 支持三种BER Log10字段名
const log10 = toNumber(row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10)
// 支持两种严重程度字段
const severity = row.SymbolBERSeverity || row.Severity || 'info'
// 节点和端口映射
title: `${row['Node Name'] || row.NodeName || row.NodeGUID || 'Node'} - Port ${row.PortNumber || row['Port Number'] || 'N/A'}`
```

#### buildCongestionInsights (line 108):
```javascript
title: `${row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown'} - Port ${row.PortNumber || row['Port Number'] || 'N/A'}`
```

#### buildCableInsights (line 344):
```javascript
title: `${vendor} - ${row['Node Name'] || row.NodeName || 'Port'} ${row.PortNumber || row['Port Number'] || 'N/A'}`
```

#### buildFanInsights (line 385):
```javascript
const node = row['Node Name'] || row.NodeName || row.NodeGUID || 'Chassis'
```

#### buildLatencyInsights (line 436):
```javascript
title: `${row['Node Name'] || row.NodeName || row.NodeGUID || 'Node'} - Port ${row.PortNumber || row['Port Number'] || 'N/A'}`
```

**文件位置**: [App.jsx](../frontend/src/App.jsx)

---

## 后端服务字段名参考

### BER服务
#### ber_service.py (基础BER)
```python
DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",  # 带空格
    "Attached To",
    "PortNumber",
    "EventName",
    "Summary",
    "SymbolBERSeverity",  # 不是Severity
]
```

计算字段:
- `SymbolBERLog10Value`
- `SymbolBERValue`
- `SymbolBERThreshold`
- `Raw BER`, `Effective BER`, `Symbol BER` (带空格)

#### ber_advanced_service.py (高级BER)
```python
返回字段:
- NodeGUID
- NodeName  # 无空格
- PortNumber
- NumLanes
- RawBER, EffectiveBER  # 无空格
- RawBERLog10, EffectiveBERLog10
- WorstLaneBER, WorstLaneBERLog10
- FECCorrectedCW, FECUncorrectedCW  # CW = Codewords
- SymbolErrors, LinkErrors
- AvgSNR_dB, MinEyeHeightMV
- Severity  # 不是SymbolBERSeverity
- Issues
```

### 线缆服务
#### cable_service.py
```python
DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",  # 带空格
    "Attached To",
    "Node Type",
    "Attached To Type",
    "PortNumber",
    "Vendor",
    "PN",  # 不是Part Number
    "SN",  # 不是Serial Number
    "Temperature (c)",  # 带空格和括号
    "SupplyVoltageReporting",
    "TX Bias Alarm and Warning",
    "TX Power Alarm and Warning",
    "RX Power Alarm and Warning",
    "Latched Voltage Alarm and Warning",
    # ... 温度和电压告警字段
    "LengthSMFiber",
    "LengthCopperOrActive",
    "TypeDesc",
    "SupportedSpeedDesc",
    "CableComplianceStatus",
    "CableSpeedStatus",
    "LocalActiveLinkSpeed",
]
```

### 拥塞服务
#### xmit_service.py
```python
DISPLAY_COLUMNS = [
    "NodeGUID",
    "Node Name",  # 带空格
    "Node Type",
    "Attached To",
    "Attached To Type",
    "PortNumber",
    "Attached To Port",
    "PortState",
    "PortPhyState",
    "NeighborPortState",
    "NeighborPortPhyState",
    "NeighborIsActive",
    "CongestionLevel",
    "WaitSeconds",
    "WaitRatioPct",
    "XmitCongestionPct",
    "FECNCount",
    "BECNCount",
    "PortXmitData",
    "PortRcvData",
    "PortXmitPkts",
    "PortRcvPkts",
    "PortXmitWait",
    "PortXmitWaitTotal",
    "PortXmitDataTotal",
    "PortRcvDataExtended",
    "PortXmitDataExtended",
    "LinkDownedCounter",
    "LinkErrorRecoveryCounter",
    # ... 更多性能计数器
]
```

---

## 字段命名模式总结

### 后端字段命名规则
1. **基本字段**: 通常是驼峰命名 `NodeGUID`, `PortNumber`
2. **描述性字段**: 使用空格 `Node Name`, `Attached To`
3. **单位字段**: 包含单位和括号 `Temperature (c)`
4. **缩写字段**: `PN` (Part Number), `SN` (Serial Number)
5. **告警字段**: 完整描述 `TX Bias Alarm and Warning`

### 前端兼容策略
所有前端组件应该支持**多种字段名变体**:

```javascript
// 通用模式
const fieldValue = row.CamelCase || row['Space Separated'] || row.alternative || 'N/A'

// 示例
const nodeName = row['Node Name'] || row.NodeName || 'Unknown'
const portNumber = row.PortNumber || row['Port Number'] || 'N/A'
const partNumber = row.PN || row['Part Number'] || row.PartNumber || 'N/A'
```

---

## 测试建议

### 1. BER分析
- 上传包含BER数据的IBDiagnet文件
- 验证"严重超标"、"BER偏高"、"健康端口"统计数字
- 检查Symbol BER Log10值显示
- 确认FEC纠正/不可纠正块计数显示

### 2. 线缆分析
- 上传包含光模块数据的文件
- 验证温度显示
- 检查型号(PN)和序列号(SN)是否正确显示
- 确认长度字段(LengthCopperOrActive/LengthSMFiber)

### 3. 拥塞分析
- 上传包含PM_DELTA数据的文件
- 验证WaitRatioPct, XmitCongestionPct显示
- 检查LinkDownedCounter统计

---

## 防止未来问题的建议

### 后端改进
1. **统一字段命名**: 在所有服务中使用一致的字段名
   - `NodeName` vs `Node Name` → 统一为一种
   - `PN`/`SN` → 改为 `PartNumber`/`SerialNumber`

2. **字段名映射层**: 在API层添加字段名标准化
   ```python
   def standardize_field_names(data):
       return {
           "nodeName": row.get("Node Name") or row.get("NodeName"),
           "partNumber": row.get("PN") or row.get("Part Number"),
           # ...
       }
   ```

3. **API文档**: 为每个endpoint记录返回的字段名

### 前端改进
1. **类型定义**: 使用TypeScript定义数据接口
2. **数据转换层**: 创建统一的数据标准化函数
3. **字段常量**: 定义字段名常量避免硬编码

### 示例 - 数据标准化工具函数
```javascript
// utils/dataMapper.js
export const standardizeNodeData = (row) => ({
  nodeName: row['Node Name'] || row.NodeName || 'Unknown',
  nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
  portNumber: row.PortNumber || row['Port Number'] || 'N/A',
})

export const standardizeCableData = (row) => ({
  ...standardizeNodeData(row),
  partNumber: row.PN || row['Part Number'] || row.PartNumber || 'N/A',
  serialNumber: row.SN || row['Serial Number'] || row.SerialNumber || 'N/A',
  temperature: row['Temperature (c)'] || row.Temperature || 0,
})

export const standardizeBERData = (row) => ({
  ...standardizeNodeData(row),
  severity: row.SymbolBERSeverity || row.Severity || 'unknown',
  log10Value: row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10 || 0,
  effectiveBER: row.EffectiveBER || row['Effective BER'] || 'N/A',
  rawBER: row.RawBER || row['Raw BER'] || 'N/A',
})
```

---

## 修复文件清单

✅ [frontend/src/BERAnalysis.jsx](../frontend/src/BERAnalysis.jsx) - 7个字段映射修复
✅ [frontend/src/CableAnalysis.jsx](../frontend/src/CableAnalysis.jsx) - 6个字段映射修复
✅ [frontend/src/CongestionAnalysis.jsx](../frontend/src/CongestionAnalysis.jsx) - 3个字段映射修复
✅ [frontend/src/FaultSummary.jsx](../frontend/src/FaultSummary.jsx) - 12+个字段映射修复
✅ [frontend/src/App.jsx](../frontend/src/App.jsx) - 超时配置已更新 + 5个insight builder函数修复

---

## 相关文档

- [后端超时配置说明](../.backend-timeout-config.md)
- [IBDiagnet 手册分析](./ibdiagnet_manual_analysis.md)
- [故障汇总功能说明](./故障汇总功能说明.md)

---

## 总结

所有已知的字段名不匹配问题已修复。前端组件现在能够正确处理来自不同后端服务的多种字段名变体，确保数据显示的准确性和完整性。
