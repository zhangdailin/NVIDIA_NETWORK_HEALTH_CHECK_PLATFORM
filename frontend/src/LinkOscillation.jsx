import { Activity, AlertTriangle, ArrowRightLeft, RefreshCw, Shield } from 'lucide-react'
import DataTable from './DataTable'

const ensureArray = (value) => (Array.isArray(value) ? value : [])

const formatCount = (value) => {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  if (Math.abs(num) >= 1000) {
    return num.toLocaleString('en-US', { maximumFractionDigits: 1 })
  }
  return num.toLocaleString('en-US', { maximumFractionDigits: num % 1 === 0 ? 0 : 2 })
}

const toFiniteNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

const resolveLinkDownCount = (row, suffix) => {
  if (!row) return 0
  const total = toFiniteNumber(row[`LinkDownedCounter${suffix}`])
  if (total !== null) return total
  const base = toFiniteNumber(row[`LinkDownedCounterBase${suffix}`])
  const ext = toFiniteNumber(row[`LinkDownedCounterExt${suffix}`])
  if (base !== null || ext !== null) {
    return (base || 0) + (ext || 0)
  }
  return 0
}

const buildPathLabel = (row) => {
  if (!row) return '未知路径'
  const nodeA = row.NodeDesc1 || row.NodeGUID1 || row.NodeGUID || 'Node A'
  const portA = row.PortNum1 ?? row.PortNumber1 ?? row.PortNumber ?? ''
  const nodeB = row.NodeDesc2 || row.NodeGUID2 || 'Node B'
  const portB = row.PortNum2 ?? row.PortNumber2 ?? ''
  const aLabel = portA !== '' ? `${nodeA}:${portA}` : nodeA
  const bLabel = portB !== '' ? `${nodeB}:${portB}` : nodeB
  return `${aLabel} ↔ ${bLabel}`
}

const endpointFromRow = (row, suffix) => {
  if (!row) return null
  const descKey = `NodeDesc${suffix}`
  const nodeName = row[descKey] || row[`NodeName${suffix}`] || row[`Node${suffix}`] || `Node ${suffix}`
  return {
    name: nodeName,
    port: row[`PortNum${suffix}`] ?? row[`PortNumber${suffix}`] ?? null,
    vendor: row[`Vendor${suffix}`] || 'Unknown vendor',
    deviceId: row[`DeviceID${suffix}`],
    lid: row[`LID${suffix}`],
  }
}

function LinkOscillation({ paths, summary }) {
  const rows = ensureArray(paths)
  const previewSeverity = rows.reduce(
    (acc, row) => {
      const severity = String(row?.Severity || '').toLowerCase()
      if (severity === 'critical') acc.critical += 1
      else if (severity === 'warning') acc.warning += 1
      else acc.info += 1
      return acc
    },
    { critical: 0, warning: 0, info: 0 }
  )

  const stats = {
    totalPaths: Number.isFinite(summary?.total_paths) ? summary.total_paths : rows.length,
    previewRows: Number.isFinite(summary?.preview_rows) ? summary.preview_rows : rows.length,
    criticalPaths: Number.isFinite(summary?.critical_paths) ? summary.critical_paths : previewSeverity.critical,
    warningPaths: Number.isFinite(summary?.warning_paths) ? summary.warning_paths : previewSeverity.warning,
    maxLinkFlaps: Number.isFinite(summary?.max_link_flaps)
      ? summary.max_link_flaps
      : Number(rows[0]?.TotalLinkFlaps) || 0,
  }

  const metricCards = [
    {
      key: 'total',
      label: '检测到的路径',
      value: stats.totalPaths,
      description: 'LinkDownedCounter > 0 的唯一端到端路径',
      icon: Activity,
    },
    {
      key: 'preview',
      label: '前端预览行数',
      value: stats.previewRows,
      description: '最多展示 200 条高频震荡路径',
      icon: RefreshCw,
    },
    {
      key: 'critical',
      label: '严重链路 (≥100 次)',
      value: stats.criticalPaths,
      description: '持续抖动，需要优先处理',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '告警链路 (20-99 次)',
      value: stats.warningPaths,
      description: '存在频繁 flap 迹象',
      icon: Shield,
    },
  ]

  const severityChips = [
    {
      key: 'critical',
      label: '严重',
      color: '#b91c1c',
      background: '#fee2e2',
      total: stats.criticalPaths,
      preview: previewSeverity.critical,
    },
    {
      key: 'warning',
      label: '警告',
      color: '#92400e',
      background: '#fef3c7',
      total: stats.warningPaths,
      preview: previewSeverity.warning,
    },
    {
      key: 'info',
      label: '信息/其他',
      color: '#0f172a',
      background: '#e2e8f0',
      total: previewSeverity.info,
      preview: previewSeverity.info,
    },
  ]

  const topRow = rows[0]
  const highlightedPath = topRow
    ? {
        endpoints: [endpointFromRow(topRow, 1), endpointFromRow(topRow, 2)],
        totalFlaps: Number(topRow.TotalLinkFlaps) || stats.maxLinkFlaps,
      }
    : summary?.top_path
      ? {
          endpoints: [
            { name: summary.top_path.node_a || 'Node A' },
            { name: summary.top_path.node_b || 'Node B' },
          ],
          totalFlaps: Number(summary.top_path.total_flaps) || stats.maxLinkFlaps,
        }
      : null

  const previewRows = rows.slice(0, 10)
  const tableRows = rows.map(row => {
    const node1LinkDown = resolveLinkDownCount(row, 1)
    const node2LinkDown = resolveLinkDownCount(row, 2)
    return {
      Path: buildPathLabel(row),
      Node1LinkDown: node1LinkDown,
      Node2LinkDown: node2LinkDown,
      ...row,
    }
  })

  if (!rows.length) {
    return (
      <div className="link-oscillation">
        <div className="osc-empty">
          <p>未在 PM_INFO 中检测到 LinkDownedCounter 抖动路径。</p>
          <p style={{ margin: 0, color: '#6b7280' }}>
            请确认采集的 ibdiagnet 包中包含 PM_INFO 表，或等待下次运行。
          </p>
        </div>
      </div>
    )
  }

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
            <div className="osc-chip-value">{formatCount(chip.total)}</div>
            <div className="osc-chip-sub">
              {chip.key !== 'info' && chip.total !== chip.preview
                ? `预览 ${formatCount(chip.preview)} / 总计 ${formatCount(chip.total)}`
                : `预览 ${formatCount(chip.preview)}`}
            </div>
          </div>
        ))}
      </div>

      {highlightedPath && (
        <div className="osc-top-path">
          <div className="osc-top-path-header">
            <div>
              <h3>抖动最严重的路径</h3>
              <p>按 TotalLinkFlaps 排序的首条路径，优先排查下列两端节点。</p>
            </div>
            <div className="osc-top-path-total">
              累计 {formatCount(highlightedPath.totalFlaps)} 次 LinkDown
            </div>
          </div>
          <div className="osc-endpoints">
            {highlightedPath.endpoints?.[0] && (
              <div className="osc-endpoint">
                <div className="osc-endpoint-name">{highlightedPath.endpoints[0].name}</div>
                <div className="osc-endpoint-meta">
                  端口 {highlightedPath.endpoints[0].port ?? '未知'} · LID{' '}
                  {highlightedPath.endpoints[0].lid ?? 'N/A'}
                </div>
                <div className="osc-endpoint-meta">{highlightedPath.endpoints[0].vendor}</div>
              </div>
            )}
            <ArrowRightLeft className="osc-endpoint-arrow" size={20} />
            {highlightedPath.endpoints?.[1] && (
              <div className="osc-endpoint">
                <div className="osc-endpoint-name">{highlightedPath.endpoints[1].name}</div>
                <div className="osc-endpoint-meta">
                  端口 {highlightedPath.endpoints[1].port ?? '未知'} · LID{' '}
                  {highlightedPath.endpoints[1].lid ?? 'N/A'}
                </div>
                <div className="osc-endpoint-meta">{highlightedPath.endpoints[1].vendor}</div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="osc-section">
        <div className="osc-section-header">
          <div>
            <h3>Top 路径预览</h3>
            <p>按 TotalLinkFlaps 排序的前 10 条路径，帮助快速定位震荡热点。</p>
          </div>
          <span className="osc-section-tag">
            展示 {previewRows.length} / {rows.length} (总计 {formatCount(stats.totalPaths)})
          </span>
        </div>
        <div className="osc-table-wrapper">
          <table className="osc-table">
            <thead>
              <tr>
                <th>严重度</th>
                <th>Path</th>
                <th>节点 1 LinkDown</th>
                <th>节点 2 LinkDown</th>
                <th>Total Link Flaps</th>
              </tr>
            </thead>
            <tbody>
              {previewRows.map((row, idx) => {
                const severity = String(row.Severity || 'info').toLowerCase()
                const node1LinkDown = resolveLinkDownCount(row, 1)
                const node2LinkDown = resolveLinkDownCount(row, 2)
                return (
                  <tr key={`${row.NodeDesc1}-${row.NodeDesc2}-${idx}`}>
                    <td>
                      <span className={`osc-severity-dot severity-${severity}`} />
                      {severity || 'info'}
                    </td>
                    <td>{buildPathLabel(row)}</td>
                    <td>{formatCount(node1LinkDown)}</td>
                    <td>{formatCount(node2LinkDown)}</td>
                    <td>{formatCount(row.TotalLinkFlaps)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="osc-section">
        <div className="osc-section-header">
          <div>
            <h3>完整路径表 (可搜索/排序)</h3>
            <p>需要进一步分析时，可使用下方表格过滤节点、端口或 Vendor。</p>
          </div>
        </div>
        <DataTable
          rows={tableRows}
          totalRows={stats.previewRows}
          preferredColumns={[
            'Severity',
            'TotalLinkFlaps',
            'Path',
            'Node1LinkDown',
            'Node2LinkDown',
            'LinkDownedCounter1',
            'LinkDownedCounter2',
            'NodeDesc1',
            'PortNum1',
            'NodeDesc2',
            'PortNum2',
            'LinkDownedCounterBase1',
            'LinkDownedCounterBase2',
            'LinkDownedCounterExt1',
            'LinkDownedCounterExt2',
          ]}
          defaultSortKey="TotalLinkFlaps"
          searchPlaceholder="搜索节点、端口或 Vendor..."
        />
      </div>
    </div>
  )
}

export default LinkOscillation
