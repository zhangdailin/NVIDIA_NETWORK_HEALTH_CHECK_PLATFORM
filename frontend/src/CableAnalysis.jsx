import { useState } from 'react'
import { Thermometer, Zap, AlertTriangle } from 'lucide-react'
import DataTable from './DataTable'

const toNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const hasAlarmFlag = (value) => {
  if (value === null || value === undefined) return false
  const text = String(value).trim()
  if (!text || text.toLowerCase() === 'n/a') return false
  const token = text.split(/\s+/)[0]
  if (!token) return false
  try {
    if (token.toLowerCase().startsWith('0x')) {
      return parseInt(token, 16) !== 0
    }
    const parsed = Number(token)
    return Number.isFinite(parsed) && parsed !== 0
  } catch {
    return false
  }
}

const buildPortKey = (row) => {
  const guid = row.NodeGUID || row.NodeGuid || row['Node GUID'] || row['NodeGUID'] || row['Node Name'] || 'unknown'
  const port = row.PortNumber || row['Port Number'] || row.port || '0'
  return `${guid}:${port}`
}

const TABLE_PRIORITY = [
  'IssueReason',
  'IssueSeverity',
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

const SEVERITY_ORDER = { critical: 0, warning: 1, ok: 2 }
const SEVERITY_LABEL = { critical: '严重', warning: '警告', ok: '正常' }

function CableAnalysis({ cableData, summary }) {
  const [showAllTempWarning, setShowAllTempWarning] = useState(false)
  const [showAllCompliance, setShowAllCompliance] = useState(false)
  if (!cableData || !Array.isArray(cableData) || cableData.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <p>无线缆数据</p>
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
  return { severity: 'ok', reason: '健康' }
}

  const totalPorts = summary?.total_cables ?? cableData.length
  const criticalCount = summary?.critical_count ?? criticalKeySet.size
  const warningCount = summary?.warning_count ?? warningKeySet.size
  const healthyCount = summary?.healthy_count ?? Math.max(totalPorts - criticalCount - warningCount, 0)
  const visibleTempWarnings = showAllTempWarning ? tempWarning : tempWarning.slice(0, 5)
  const visibleCompliance = showAllCompliance ? complianceIssues : complianceIssues.slice(0, 3)
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

  return (
    <div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div style={{
          padding: '16px',
          background: 'white',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>总端口数</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#1f2937' }}>{totalPorts}</div>
        </div>

        <div style={{
          padding: '16px',
          background: criticalCount > 0 ? '#fee2e2' : 'white',
          borderRadius: '8px',
          border: `1px solid ${criticalCount > 0 ? '#dc2626' : '#e5e7eb'}`,
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>严重问题</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: criticalCount > 0 ? '#dc2626' : '#10b981' }}>
            {criticalCount}
          </div>
        </div>

        <div style={{
          padding: '16px',
          background: warningCount > 0 ? '#fef3c7' : 'white',
          borderRadius: '8px',
          border: `1px solid ${warningCount > 0 ? '#f59e0b' : '#e5e7eb'}`,
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>警告</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: warningCount > 0 ? '#f59e0b' : '#10b981' }}>
            {warningCount}
          </div>
        </div>

        <div style={{
          padding: '16px',
          background: 'white',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>健康端口</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#10b981' }}>
            {healthyCount}
          </div>
        </div>
      </div>

      {tempCritical.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#dc2626',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Thermometer size={20} />
            🆘 温度严重过高 ({tempCritical.length}个端口)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {tempCritical.map((item, idx) => (
              <div key={idx} style={{
                padding: '12px 16px',
                background: '#fee2e2',
                borderRadius: '6px',
                border: '1px solid #dc2626',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem'
              }}>
                <div>
                  <strong>节点:</strong> {item.nodeName}
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', fontFamily: 'monospace' }}>
                    {item.NodeGUID || 'N/A'}
                  </div>
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>温度:</strong>{' '}
                  <span style={{ color: '#dc2626', fontWeight: 'bold' }}>{item.temp.toFixed(1)}°C</span>
                  <span style={{ color: '#6b7280' }}> (临界: 80°C)</span>
                </div>
                <div><strong>厂商:</strong> {item.vendor}</div>
                <div><strong>型号:</strong> {item.partNumber}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {powerAlarms.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#dc2626',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Zap size={20} />
            🆘 光功率告警 ({powerAlarms.length}个端口)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {powerAlarms.map((item, idx) => (
              <div key={idx} style={{
                padding: '12px 16px',
                background: '#fee2e2',
                borderRadius: '6px',
                border: '1px solid #dc2626',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem'
              }}>
                <div>
                  <strong>节点:</strong> {item.nodeName}
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', fontFamily: 'monospace' }}>
                    {item.NodeGUID || 'N/A'}
                  </div>
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>告警类型:</strong>{' '}
                  <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
                    {item.alarms.join(', ')}
                  </span>
                </div>
                <div><strong>厂商:</strong> {item.vendor}</div>
                <div><strong>型号:</strong> {item.partNumber}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tempWarning.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#f59e0b',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle size={20} />
            ⚠️ 温度偏高 ({tempWarning.length}个端口)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {visibleTempWarnings.map((item, idx) => (
              <div key={`${item.nodeName}-${item.portNumber}-${idx}`} style={{
                padding: '12px 16px',
                background: '#fef3c7',
                borderRadius: '6px',
                border: '1px solid #f59e0b',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem'
              }}>
                <div>
                  <strong>节点:</strong> {item.nodeName}
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>温度:</strong>{' '}
                  <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>{item.temp.toFixed(1)}°C</span>
                  <span style={{ color: '#6b7280' }}> (警告: 70°C)</span>
                </div>
                <div><strong>厂商:</strong> {item.vendor}</div>
              </div>
            ))}
          </div>
          {tempWarning.length > 5 && (
            <button
              type="button"
              onClick={() => setShowAllTempWarning(value => !value)}
              style={{
                marginTop: '12px',
                border: 'none',
                background: 'transparent',
                color: '#2563eb',
                cursor: 'pointer',
              }}
            >
              {showAllTempWarning ? '收起部分端口' : `展开剩余 ${tempWarning.length - 5} 个端口`}
            </button>
          )}
        </div>
      )}

      {complianceIssues.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#f59e0b',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle size={20} />
            ⚠️ 线缆规格问题 ({complianceIssues.length}条)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {visibleCompliance.map((item, idx) => (
              <div key={`${item.nodeName}-${item.portNumber}-${idx}`} style={{
                padding: '12px 16px',
                background: '#fef3c7',
                borderRadius: '6px',
                border: '1px solid #f59e0b',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem'
              }}>
                <div>
                  <strong>节点:</strong> {item.nodeName}
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>规格状态:</strong>{' '}
                  <span style={{ color: '#f59e0b' }}>{item.complianceStatus || 'N/A'}</span>
                </div>
                <div>
                  <strong>速度状态:</strong>{' '}
                  <span style={{ color: '#f59e0b' }}>{item.speedStatus || 'N/A'}</span>
                </div>
              </div>
            ))}
            {complianceIssues.length > 3 && (
              <button
                type="button"
                onClick={() => setShowAllCompliance(value => !value)}
                style={{
                  marginTop: '12px',
                  border: 'none',
                  background: 'transparent',
                  color: '#2563eb',
                  cursor: 'pointer',
                }}
              >
                {showAllCompliance ? '收起部分条目' : `展开剩余 ${complianceIssues.length - 3} 条`}
              </button>
            )}
          </div>
        </div>
      )}

      <div style={{ marginTop: '32px' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#1f2937' }}>
          📋 完整线缆数据表 (可搜索/可排序)
        </h3>
        <DataTable
          rows={annotatedRows}
          totalRows={summary?.cable_info_rows ?? cableData.length}
          searchPlaceholder="搜索节点名、GUID、端口号、厂商..."
          pageSize={20}
          preferredColumns={TABLE_PRIORITY}
        />
      </div>
    </div>
  )
}

export default CableAnalysis
