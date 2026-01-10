import { Thermometer, Zap, AlertTriangle, Cable, Database } from 'lucide-react'
import DataTable from './DataTable'
import { toNumber, formatCount, hasAlarmFlag, buildPortKey, SEVERITY_ORDER, SEVERITY_LABEL } from './analysisUtils'

const TABLE_PRIORITY = [
  'IssueSeverity',
  'IssueReason',
  'Severity',
  'Node Name',
  'NodeGUID',
  'PortNumber',
  'Vendor',
  'PN',
  'SN',
  'Temperature (c)',
  'CableComplianceStatus',
  'CableSpeedStatus',
  'TX Bias Alarm and Warning',
  'TX Power Alarm and Warning',
  'RX Power Alarm and Warning',
  'Latched Voltage Alarm and Warning',
  'LengthSMFiber',
  'LengthCopperOrActive',
]

function CableAnalysis({ cableData, summary }) {
  if (!cableData || !Array.isArray(cableData) || cableData.length === 0) {
    return (
      <div className="osc-empty">
        <p>无线缆数据</p>
        <p style={{ margin: 0, color: '#6b7280' }}>
          请确认采集的数据包中包含线缆信息表格。
        </p>
      </div>
    )
  }

  const analyzeData = () => {
    const tempCritical = []
    const tempWarning = []
    const powerAlarms = []
    const complianceIssues = []

    cableData.forEach((row, index) => {
      const temp = toNumber(row['Temperature (c)'] || row.Temperature)
      const nodeName = row['Node Name'] || row.NodeName || 'Unknown'
      const portNumber = row.PortNumber || row['Port Number'] || 'N/A'
      const vendor = row.Vendor || row['Vendor Name'] || 'N/A'
      const partNumber = row.PN || row['Part Number'] || row.PartNumber || 'N/A'

      if (temp >= 80) {
        tempCritical.push({ ...row, temp, nodeName, portNumber, vendor, partNumber, index })
      } else if (temp >= 70) {
        tempWarning.push({ ...row, temp, nodeName, portNumber, vendor, partNumber, index })
      }

      const alarms = []
      if (hasAlarmFlag(row['TX Bias Alarm and Warning'])) alarms.push('TX Bias')
      if (hasAlarmFlag(row['TX Power Alarm and Warning'])) alarms.push('TX Power')
      if (hasAlarmFlag(row['RX Power Alarm and Warning'])) alarms.push('RX Power')
      if (hasAlarmFlag(row['Latched Voltage Alarm and Warning'])) alarms.push('Voltage')
      if (alarms.length > 0) {
        powerAlarms.push({ ...row, alarms, nodeName, portNumber, vendor, partNumber, index })
      }

      const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
      const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
      if ((complianceStatus && complianceStatus !== 'ok') || (speedStatus && speedStatus !== 'ok')) {
        complianceIssues.push({
          ...row,
          complianceStatus,
          speedStatus,
          nodeName,
          portNumber,
          vendor,
          partNumber,
          index,
        })
      }
    })

    return { tempCritical, tempWarning, powerAlarms, complianceIssues }
  }

  const { tempCritical, tempWarning, powerAlarms, complianceIssues } = analyzeData()

  const criticalKeySet = new Set()
  tempCritical.forEach(item => criticalKeySet.add(buildPortKey(item)))
  powerAlarms.forEach(item => criticalKeySet.add(buildPortKey(item)))
  const warningKeySet = new Set()
  tempWarning.forEach(item => {
    const key = buildPortKey(item)
    if (!criticalKeySet.has(key)) {
      warningKeySet.add(key)
    }
  })
  complianceIssues.forEach(item => {
    const key = buildPortKey(item)
    if (!criticalKeySet.has(key)) {
      warningKeySet.add(key)
    }
  })

  const getRowStatus = (row) => {
    const temp = toNumber(row['Temperature (c)'] || row.Temperature)
    if (temp >= 80) return 'critical'
    const alarms = [
      row['TX Bias Alarm and Warning'],
      row['TX Power Alarm and Warning'],
      row['RX Power Alarm and Warning'],
      row['Latched Voltage Alarm and Warning'],
    ]
    if (alarms.some(hasAlarmFlag)) return 'critical'
    if (temp >= 70) return 'warning'
    const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
    const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
    if ((complianceStatus && complianceStatus !== 'ok') || (speedStatus && speedStatus !== 'ok')) {
      return 'warning'
    }
    return 'ok'
  }

  const describeCableIssue = (row) => {
    // 优先使用后端返回的 Severity 字段
    const backendSeverity = String(row.Severity || '').toLowerCase()
    if (backendSeverity === 'critical' || backendSeverity === 'warning') {
      // 生成问题描述
      const temp = toNumber(row['Temperature (c)'] || row.Temperature)
      if (temp >= 80) {
        return { severity: backendSeverity, reason: `温度过高 (${temp.toFixed(1)}°C ≥ 80°C)` }
      }
      const alarmDetails = []
      if (hasAlarmFlag(row['TX Bias Alarm and Warning'])) alarmDetails.push('TX Bias')
      if (hasAlarmFlag(row['TX Power Alarm and Warning'])) alarmDetails.push('TX Power')
      if (hasAlarmFlag(row['RX Power Alarm and Warning'])) alarmDetails.push('RX Power')
      if (hasAlarmFlag(row['Latched Voltage Alarm and Warning'])) alarmDetails.push('Voltage')
      if (alarmDetails.length) {
        return { severity: backendSeverity, reason: `光功率告警: ${alarmDetails.join(', ')}` }
      }
      if (temp >= 70) {
        return { severity: backendSeverity, reason: `温度偏高 (${temp.toFixed(1)}°C ≥ 70°C)` }
      }
      const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
      const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
      if ((complianceStatus && complianceStatus !== 'ok') || (speedStatus && speedStatus !== 'ok')) {
        return {
          severity: backendSeverity,
          reason: `规格/速率不合规: ${row.CableComplianceStatus || 'N/A'} / ${row.CableSpeedStatus || 'N/A'}`,
        }
      }
      // 后端标记为问题但前端未识别具体原因
      return { severity: backendSeverity, reason: backendSeverity === 'critical' ? '严重问题' : '警告问题' }
    }

    // 如果后端未标记，使用前端规则作为后备
    const temp = toNumber(row['Temperature (c)'] || row.Temperature)
    if (temp >= 80) {
      return { severity: 'critical', reason: `温度过高 (${temp.toFixed(1)}°C ≥ 80°C)` }
    }
    const alarmDetails = []
    if (hasAlarmFlag(row['TX Bias Alarm and Warning'])) alarmDetails.push('TX Bias')
    if (hasAlarmFlag(row['TX Power Alarm and Warning'])) alarmDetails.push('TX Power')
    if (hasAlarmFlag(row['RX Power Alarm and Warning'])) alarmDetails.push('RX Power')
    if (hasAlarmFlag(row['Latched Voltage Alarm and Warning'])) alarmDetails.push('Voltage')
    if (alarmDetails.length) {
      return { severity: 'critical', reason: `光功率告警: ${alarmDetails.join(', ')}` }
    }
    if (temp >= 70) {
      return { severity: 'warning', reason: `温度偏高 (${temp.toFixed(1)}°C ≥ 70°C)` }
    }
    const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
    const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
    if ((complianceStatus && complianceStatus !== 'ok') || (speedStatus && speedStatus !== 'ok')) {
      return {
        severity: 'warning',
        reason: `规格/速率不合规: ${row.CableComplianceStatus || 'N/A'} / ${row.CableSpeedStatus || 'N/A'}`,
      }
    }
    return { severity: 'normal', reason: '健康' }
  }

  const totalPorts = summary?.total_cables ?? cableData.length
  const criticalCount = summary?.critical_count ?? criticalKeySet.size
  const warningCount = summary?.warning_count ?? warningKeySet.size
  const healthyCount = summary?.healthy_count ?? Math.max(totalPorts - criticalCount - warningCount, 0)

  const metricCards = [
    {
      key: 'total',
      label: '总端口数',
      value: totalPorts,
      description: '全部检测端口',
      icon: Database,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: criticalCount,
      description: '温度 ≥80°C 或光功率告警',
      icon: Thermometer,
    },
    {
      key: 'warning',
      label: '警告',
      value: warningCount,
      description: '温度 ≥70°C 或规格不合规',
      icon: AlertTriangle,
    },
    {
      key: 'healthy',
      label: '健康端口',
      value: healthyCount,
      description: '无异常端口',
      icon: Cable,
    },
  ]

  const severityChips = [
    {
      key: 'critical',
      label: '严重',
      color: '#b91c1c',
      background: '#fee2e2',
      count: criticalCount,
    },
    {
      key: 'warning',
      label: '警告',
      color: '#92400e',
      background: '#fef3c7',
      count: warningCount,
    },
    {
      key: 'ok',
      label: '健康',
      color: '#166534',
      background: '#d1fae5',
      count: healthyCount,
    },
  ]

  const annotatedRows = cableData
    .map(row => {
      const { severity, reason } = describeCableIssue(row)
      return {
        IssueSeverity: SEVERITY_LABEL[severity] || severity,
        IssueReason: reason,
        ...row,
        __severityOrder: SEVERITY_ORDER[severity] ?? 3,
      }
    })
    .sort((a, b) => (a.__severityOrder ?? 3) - (b.__severityOrder ?? 3))

  const topCriticalRows = annotatedRows.filter(row => row.__severityOrder === 0).slice(0, 10)
  const topWarningRows = annotatedRows.filter(row => row.__severityOrder === 1).slice(0, 10)

  // Debug: 如果没有问题行，显示前10行作为预览
  const hasIssues = topCriticalRows.length > 0 || topWarningRows.length > 0
  const previewRows = hasIssues ? [] : annotatedRows.slice(0, 10)

  return (
    <div className="link-oscillation">
      <div className="osc-metric-grid">
        {metricCards.map(card => {
          const Icon = card.icon
          return (
            <div key={card.key} className="osc-metric-card">
              <div className="osc-metric-top">
                <div className="osc-metric-icon">
                  <Icon size={18} />
                </div>
                <span className="osc-metric-label">{card.label}</span>
              </div>
              <div className="osc-metric-value">{formatCount(card.value)}</div>
              <p className="osc-metric-desc">{card.description}</p>
            </div>
          )
        })}
      </div>

      <div className="osc-chip-row">
        {severityChips.map(chip => (
          <div
            key={chip.key}
            className="osc-chip"
            style={{ background: chip.background, color: chip.color }}
          >
            <div className="osc-chip-label">{chip.label}</div>
            <div className="osc-chip-value">{formatCount(chip.count)}</div>
            <div className="osc-chip-sub">共 {formatCount(chip.count)} 个端口</div>
          </div>
        ))}
      </div>

      {topCriticalRows.length > 0 && (
        <div className="osc-section">
          <div className="osc-section-header">
            <div>
              <h3>严重问题预览 (Top {topCriticalRows.length})</h3>
              <p>温度 ≥80°C 或光功率告警的端口,按严重程度排序。</p>
            </div>
            <span className="osc-section-tag">
              展示 {topCriticalRows.length} / 总计 {formatCount(criticalCount)}
            </span>
          </div>
          <div className="osc-table-wrapper">
            <table className="osc-table">
              <thead>
                <tr>
                  <th>严重度</th>
                  <th>问题描述</th>
                  <th>节点</th>
                  <th>端口</th>
                  <th>温度</th>
                  <th>厂商</th>
                  <th>型号</th>
                </tr>
              </thead>
              <tbody>
                {topCriticalRows.map((row, idx) => (
                  <tr key={`critical-${row.NodeGUID}-${row.PortNumber}-${idx}`}>
                    <td>
                      <span className="osc-severity-dot severity-critical" />
                      {row.IssueSeverity}
                    </td>
                    <td style={{ color: '#dc2626', fontWeight: 'bold' }}>{row.IssueReason}</td>
                    <td>{row['Node Name'] || row.NodeName || 'N/A'}</td>
                    <td>{row.PortNumber || row['Port Number'] || 'N/A'}</td>
                    <td>{toNumber(row['Temperature (c)'] || row.Temperature).toFixed(1)}°C</td>
                    <td>{row.Vendor || row['Vendor Name'] || 'N/A'}</td>
                    <td>{row.PN || row['Part Number'] || row.PartNumber || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {topWarningRows.length > 0 && (
        <div className="osc-section">
          <div className="osc-section-header">
            <div>
              <h3>警告问题预览 (Top {topWarningRows.length})</h3>
              <p>温度偏高或规格不合规的端口,建议持续监控。</p>
            </div>
            <span className="osc-section-tag">
              展示 {topWarningRows.length} / 总计 {formatCount(warningCount)}
            </span>
          </div>
          <div className="osc-table-wrapper">
            <table className="osc-table">
              <thead>
                <tr>
                  <th>严重度</th>
                  <th>问题描述</th>
                  <th>节点</th>
                  <th>端口</th>
                  <th>温度</th>
                  <th>厂商</th>
                  <th>型号</th>
                </tr>
              </thead>
              <tbody>
                {topWarningRows.map((row, idx) => (
                  <tr key={`warning-${row.NodeGUID}-${row.PortNumber}-${idx}`}>
                    <td>
                      <span className="osc-severity-dot severity-warning" />
                      {row.IssueSeverity}
                    </td>
                    <td style={{ color: '#f59e0b', fontWeight: 'bold' }}>{row.IssueReason}</td>
                    <td>{row['Node Name'] || row.NodeName || 'N/A'}</td>
                    <td>{row.PortNumber || row['Port Number'] || 'N/A'}</td>
                    <td>{toNumber(row['Temperature (c)'] || row.Temperature).toFixed(1)}°C</td>
                    <td>{row.Vendor || row['Vendor Name'] || 'N/A'}</td>
                    <td>{row.PN || row['Part Number'] || row.PartNumber || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 如果没有严重/警告问题，显示健康预览 */}
      {previewRows.length > 0 && (
        <div className="osc-section">
          <div className="osc-section-header">
            <div>
              <h3>线缆数据预览 (Top {previewRows.length})</h3>
              <p>所有线缆健康，无异常告警。以下是前 {previewRows.length} 条记录预览。</p>
            </div>
            <span className="osc-section-tag">
              展示 {previewRows.length} / 总计 {formatCount(totalPorts)}
            </span>
          </div>
          <div className="osc-table-wrapper">
            <table className="osc-table">
              <thead>
                <tr>
                  <th>状态</th>
                  <th>节点</th>
                  <th>端口</th>
                  <th>温度</th>
                  <th>厂商</th>
                  <th>型号</th>
                </tr>
              </thead>
              <tbody>
                {previewRows.map((row, idx) => (
                  <tr key={`preview-${row.NodeGUID}-${row.PortNumber}-${idx}`}>
                    <td>
                      <span className="osc-severity-dot severity-ok" />
                      {row.IssueSeverity}
                    </td>
                    <td>{row['Node Name'] || row.NodeName || 'N/A'}</td>
                    <td>{row.PortNumber || row['Port Number'] || 'N/A'}</td>
                    <td>{toNumber(row['Temperature (c)'] || row.Temperature).toFixed(1)}°C</td>
                    <td>{row.Vendor || row['Vendor Name'] || 'N/A'}</td>
                    <td>{row.PN || row['Part Number'] || row.PartNumber || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="osc-section">
        <div className="osc-section-header">
          <div>
            <h3>完整线缆数据表 (可搜索/可排序)</h3>
            <p>包含温度、光功率、规格状态等完整信息, 便于深入分析。</p>
          </div>
          <span className="osc-section-tag">展示 {totalPorts} / 总计 {formatCount(totalPorts)}</span>
        </div>
        <DataTable
          rows={annotatedRows}
          totalRows={summary?.cable_info_rows ?? cableData.length}
          searchPlaceholder="搜索节点名、GUID、端口号、厂商..."
          pageSize={20}
          preferredColumns={TABLE_PRIORITY}
          defaultSortKey="__severityOrder"
        />
      </div>
    </div>
  )
}

export default CableAnalysis
