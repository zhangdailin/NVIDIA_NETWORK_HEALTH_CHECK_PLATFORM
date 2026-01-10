import { AlertTriangle, Activity, Shield, Database } from 'lucide-react'
import DataTable from './DataTable'
import { formatCount, toNumber } from './analysisUtils'

const normalizeValue = (value, fallback = 'N/A') => {
  if (value === null || value === undefined) {
    return fallback
  }
  const str = String(value).trim()
  return str.length ? str : fallback
}

const formatExponent = (exp) => {
  const sign = exp >= 0 ? '+' : '-'
  const absValue = Math.abs(exp)
  return `${sign}${String(absValue).padStart(3, '0')}`
}

const formatBer = (value) => {
  const num = Number(value)
  if (!Number.isFinite(num) || num < 0) {
    return 'N/A'
  }
  if (num === 0) {
    return '0.00E+00'
  }
  const exponent = Math.floor(Math.log10(num))
  const mantissa = num / Math.pow(10, exponent)
  return `${mantissa.toFixed(2)}E${formatExponent(exponent)}`
}

const pickFormattedBer = (directCandidates = [], numericCandidates = [], logCandidates = []) => {
  for (const candidate of directCandidates) {
    if (candidate === null || candidate === undefined) continue
    const text = String(candidate).trim()
    if (text.length && text !== 'nan') {
      return text
    }
  }
  for (const candidate of numericCandidates) {
    const num = Number(candidate)
    if (Number.isFinite(num)) {
      return formatBer(num)
    }
  }
  for (const candidate of logCandidates) {
    const logValue = Number(candidate)
    if (Number.isFinite(logValue)) {
      return formatBer(Math.pow(10, logValue))
    }
  }
  return 'N/A'
}

const extractSymbolBer = (row) => {
  return pickFormattedBer(
    [row['Symbol BER'], row.SymbolBER, row.symbolBer],
    [row.SymbolBERValue],
    [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
  )
}

const mergeRows = (berData, berAdvancedData) => {
  const combined = []
  if (Array.isArray(berData)) {
    combined.push(...berData.map(row => ({ ...row })))
  }
  if (Array.isArray(berAdvancedData)) {
    berAdvancedData.forEach(row => {
      const guid = row.NodeGUID || row['Node GUID']
      const port = row.PortNumber || row['Port Number']
      const existingIndex = combined.findIndex(
        item => (item.NodeGUID || item['Node GUID']) === guid && (item.PortNumber || item['Port Number']) === port
      )
      if (existingIndex === -1) {
        combined.push({ ...row })
      } else {
        combined[existingIndex] = { ...combined[existingIndex], ...row }
      }
    })
  }
  return combined
}

const buildDisplayRows = (rows) => rows.map((row, index) => {
  const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
  const hasSymbolErrors = toNumber(row['Symbol Err'] ?? row.SymbolErr ?? row.symbolErr) > 0
  const fallbackAnomaly = ['critical', 'warning'].includes(severity) && hasSymbolErrors ? 'High Symbol BER' : ''

  return {
    id: `${row.NodeGUID || row['Node GUID'] || index}-${row.PortNumber || row['Port Number'] || ''}`,
    nodeGuid: normalizeValue(row.NodeGUID || row['Node GUID'], 'N/A'),
    lid: normalizeValue(row.LID || row['LID'], 'N/A'),
    peerLid: normalizeValue(row['Peer LID'] || row.PeerLID || row.ConnLID || row['Conn LID (#)'], 'N/A'),
    portNumber: normalizeValue(row.PortNumber || row['Port Number'], 'N/A'),
    nodeName: normalizeValue(row['Node Name'] || row.NodeName, 'N/A'),
    attachedTo: normalizeValue(row['Attached To'] || row.AttachedTo, 'N/A'),
    rawBer: pickFormattedBer(
      [row['Raw BER'], row.RawBER, row.rawBer],
      [row.RawBERValue],
      [row['Log10 Raw BER']]
    ),
    effectiveBer: pickFormattedBer(
      [row['Effective BER'], row.EffectiveBER, row.effectiveBer],
      [row.EffectiveBERValue],
      [row['Log10 Effective BER']]
    ),
    symbolBer: pickFormattedBer(
      [row['Symbol BER'], row.SymbolBER, row.symbolBer],
      [row.SymbolBERValue],
      [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
    ),
    ibhAnomaly: normalizeValue(row['IBH Anomaly'] || row.IBHAnomaly || fallbackAnomaly, ''),
    symbolErr: formatCount(row['Symbol Err'] ?? row.SymbolErr),
    effectiveErr: formatCount(row['Effective Err'] ?? row.EffectiveErr),
    hasSymbolErrors,
    severity,
  }
})

function BERAnalysis({ berData = [], berAdvancedData = [], showOnlyProblematic = false }) {
  const merged = mergeRows(berData, berAdvancedData)
  const displayRows = buildDisplayRows(merged)
  const problemRows = displayRows.filter(row => row.hasSymbolErrors && !!row.ibhAnomaly)

  const criticalPorts = displayRows.filter(row => row.severity === 'critical').length
  const warningPorts = displayRows.filter(row => row.severity === 'warning').length
  const totalPorts = displayRows.length
  const problemCount = problemRows.length

  if (displayRows.length === 0) {
    return (
      <div className="osc-empty">
        <p>未检测到 BER 测试数据。</p>
        <p style={{ margin: 0, color: '#6b7280' }}>
          请确认采集的数据包中包含 BER 相关表格。
        </p>
      </div>
    )
  }

  const metricCards = [
    {
      key: 'total',
      label: '总端口数',
      value: totalPorts,
      description: '全部检测端口',
      icon: Database,
    },
    {
      key: 'problem',
      label: '异常端口',
      value: problemCount,
      description: 'Symbol Error > 0 的端口',
      icon: AlertTriangle,
    },
    {
      key: 'critical',
      label: '严重 BER 问题',
      value: criticalPorts,
      description: 'BER 超过严重阈值',
      icon: Shield,
    },
    {
      key: 'warning',
      label: '警告 BER 问题',
      value: warningPorts,
      description: 'BER 超过警告阈值',
      icon: Activity,
    },
  ]

  const severityChips = [
    {
      key: 'critical',
      label: '严重',
      color: '#b91c1c',
      background: '#fee2e2',
      count: criticalPorts,
    },
    {
      key: 'warning',
      label: '警告',
      color: '#92400e',
      background: '#fef3c7',
      count: warningPorts,
    },
    {
      key: 'info',
      label: '正常/其他',
      color: '#0f172a',
      background: 'var(--bg-tertiary)',
      count: totalPorts - criticalPorts - warningPorts,
    },
  ]

  const topProblems = problemRows.slice(0, 10)
  const topCriticalRows = displayRows.filter(row => row.severity === 'critical').slice(0, 10)
  const topWarningRows = displayRows.filter(row => row.severity === 'warning').slice(0, 10)

  const tableRows = displayRows.map(row => ({
    'Node GUID': row.nodeGuid,
    LID: row.lid,
    'Peer LID': row.peerLid,
    'Port Number': row.portNumber,
    'Node Name': row.nodeName,
    'Attached To': row.attachedTo,
    'Raw BER': row.rawBer,
    'Effective BER': row.effectiveBer,
    'Symbol BER': row.symbolBer,
    'IBH Anomaly': row.ibhAnomaly && row.hasSymbolErrors ? row.ibhAnomaly : '—',
    'Symbol Err': row.symbolErr,
    'Effective Err': row.effectiveErr,
    Severity: row.severity || 'info',
  }))

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
              <h3>严重 BER 问题预览 (Top {topCriticalRows.length})</h3>
              <p>BER 超过严重阈值的端口,按严重程度排序,需立即处理。</p>
            </div>
            <span className="osc-section-tag">
              展示 {topCriticalRows.length} / 总计 {formatCount(criticalPorts)}
            </span>
          </div>
          <div className="osc-table-wrapper">
            <table className="osc-table">
              <thead>
                <tr>
                  <th>严重度</th>
                  <th>Node Name</th>
                  <th>Port</th>
                  <th>Symbol BER</th>
                  <th>Symbol Err</th>
                  <th>IBH Anomaly</th>
                </tr>
              </thead>
              <tbody>
                {topCriticalRows.map((row, idx) => (
                  <tr key={`critical-${row.id}-${idx}`}>
                    <td>
                      <span className="osc-severity-dot severity-critical" />
                      严重
                    </td>
                    <td>{row.nodeName}</td>
                    <td>{row.portNumber}</td>
                    <td style={{ fontFamily: 'monospace', color: '#dc2626', fontWeight: 'bold' }}>{row.symbolBer}</td>
                    <td style={{ fontFamily: 'monospace', fontWeight: 'bold' }}>{row.symbolErr}</td>
                    <td style={{ color: '#dc2626' }}>{row.ibhAnomaly || '—'}</td>
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
              <h3>警告 BER 问题预览 (Top {topWarningRows.length})</h3>
              <p>BER 超过警告阈值的端口,建议持续监控。</p>
            </div>
            <span className="osc-section-tag">
              展示 {topWarningRows.length} / 总计 {formatCount(warningPorts)}
            </span>
          </div>
          <div className="osc-table-wrapper">
            <table className="osc-table">
              <thead>
                <tr>
                  <th>严重度</th>
                  <th>Node Name</th>
                  <th>Port</th>
                  <th>Symbol BER</th>
                  <th>Raw BER</th>
                  <th>Effective BER</th>
                </tr>
              </thead>
              <tbody>
                {topWarningRows.map((row, idx) => (
                  <tr key={`warning-${row.id}-${idx}`}>
                    <td>
                      <span className="osc-severity-dot severity-warning" />
                      警告
                    </td>
                    <td>{row.nodeName}</td>
                    <td>{row.portNumber}</td>
                    <td style={{ fontFamily: 'monospace', color: '#f59e0b' }}>{row.symbolBer}</td>
                    <td style={{ fontFamily: 'monospace' }}>{row.rawBer}</td>
                    <td style={{ fontFamily: 'monospace' }}>{row.effectiveBer}</td>
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
            <h3>完整 BER 数据表 (可搜索/排序)</h3>
            <p>展示格式与原始 CSV 一致,便于核对离线样例。</p>
          </div>
          <span className="osc-section-tag">
            展示 {totalPorts} / 总计 {formatCount(totalPorts)}
          </span>
        </div>
        <DataTable
          rows={tableRows}
          totalRows={totalPorts}
          searchPlaceholder="搜索 NodeGUID、端口、节点或 IBH Anomaly..."
          pageSize={20}
          preferredColumns={[
            'Severity',
            'Node Name',
            'Port Number',
            'Symbol BER',
            'Symbol Err',
            'IBH Anomaly',
            'Raw BER',
            'Effective BER',
            'Node GUID',
            'LID',
          ]}
          defaultSortKey="Symbol Err"
        />
      </div>
    </div>
  )
}

export default BERAnalysis
