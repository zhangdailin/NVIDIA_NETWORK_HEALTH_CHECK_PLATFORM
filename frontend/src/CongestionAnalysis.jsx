import { AlertTriangle, XCircle, Clock, Activity, Database } from 'lucide-react'
import DataTable from './DataTable'
import { toNumber, formatCount } from './analysisUtils'

const TABLE_PRIORITY = [
  'Issue',
  'Severity',
  'Node Name',
  'NodeGUID',
  'PortNumber',
  'WaitRatioPct',
  'WaitSeconds',
  'XmitCongestionPct',
  'FECNCount',
  'BECNCount',
  'LinkDownedCounter',
  'LinkDownedCounterExt',
  'CongestionLevel',
]

const analyzeCongestion = (rows = []) => {
  const severeCongestion = []
  const moderateCongestion = []
  const fecnBecnIssues = []
  const linkDownIssues = []

  rows.forEach((row, index) => {
    const nodeName = row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown'
    const nodeGuid = row.NodeGUID || row['Node GUID'] || 'N/A'
    const portNumber = row.PortNumber || row['Port Number'] || 'N/A'
    const waitRatio = toNumber(row.WaitRatioPct)
    const waitSeconds = toNumber(row.WaitSeconds)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const fecnCount = toNumber(row.FECNCount)
    const becnCount = toNumber(row.BECNCount)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)

    const item = {
      nodeName,
      nodeGuid,
      portNumber,
      waitRatio,
      waitSeconds,
      congestionPct,
      fecnCount,
      becnCount,
      linkDowned,
      index,
    }

    if (waitRatio >= 5 || congestionPct >= 5) {
      severeCongestion.push(item)
    } else if (waitRatio >= 1 || congestionPct >= 1) {
      moderateCongestion.push(item)
    }

    if (fecnCount > 0 || becnCount > 0) {
      fecnBecnIssues.push(item)
    }
    if (linkDowned > 0) {
      linkDownIssues.push(item)
    }
  })

  return { severeCongestion, moderateCongestion, fecnBecnIssues, linkDownIssues }
}

function CongestionAnalysis({ xmitData, summary }) {
  if (!xmitData || !Array.isArray(xmitData) || xmitData.length === 0) {
    return (
      <div className="osc-empty">
        <p>无拥塞数据</p>
        <p style={{ margin: 0, color: '#6b7280' }}>
          请确认采集的数据包中包含 Xmit 相关表格。
        </p>
      </div>
    )
  }

  const { severeCongestion, moderateCongestion, fecnBecnIssues, linkDownIssues } = analyzeCongestion(xmitData)

  const getRowStatus = (row) => {
    const waitRatio = toNumber(row.WaitRatioPct)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)

    if (waitRatio >= 5 || congestionPct >= 5 || linkDowned > 10) return 'critical'
    if (waitRatio >= 1 || congestionPct >= 1 || linkDowned > 0) return 'warning'
    return 'ok'
  }

  const buildIssueDetail = (row, status) => {
    const waitRatio = toNumber(row.WaitRatioPct)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)
    const fecn = toNumber(row.FECNCount)
    const becn = toNumber(row.BECNCount)
    const reasons = []

    if (waitRatio >= 5) {
      reasons.push(`等待比例 ${waitRatio.toFixed(2)}% ≥ 5%`)
    } else if (waitRatio >= 1) {
      reasons.push(`等待比例 ${waitRatio.toFixed(2)}% ≥ 1%`)
    }
    if (congestionPct >= 5) {
      reasons.push(`XmitTimeCong ${congestionPct.toFixed(2)}% ≥ 5%`)
    } else if (congestionPct >= 1) {
      reasons.push(`XmitTimeCong ${congestionPct.toFixed(2)}% ≥ 1%`)
    }
    if (linkDowned > 10) {
      reasons.push(`链路断开 ${linkDowned} 次`)
    } else if (linkDowned > 0) {
      reasons.push(`链路断开 ${linkDowned} 次`)
    }
    if (fecn > 0 || becn > 0) {
      reasons.push(`FECN/BECN ${fecn}/${becn}`)
    }

    if (!reasons.length) {
      reasons.push(status === 'ok' ? '无异常' : '存在轻微波动')
    }

    const severityWeight = status === 'critical' ? 3 : status === 'warning' ? 2 : 1
    const priority = severityWeight * 1_000_000 + waitRatio * 1_000 + congestionPct * 100 + linkDowned
    return { issue: reasons.join(' / '), priority }
  }

  const severityLabel = {
    critical: '严重',
    warning: '警告',
    ok: '正常',
  }

  const tableRows = xmitData.map(row => {
    const status = getRowStatus(row)
    const detail = buildIssueDetail(row, status)
    return {
      ...row,
      Severity: severityLabel[status] || '正常',
      Issue: detail.issue,
      __priority: detail.priority,
      __status: status,
    }
  })

  const topCriticalRows = tableRows.filter(row => row.__status === 'critical').slice(0, 10)
  const topWarningRows = tableRows.filter(row => row.__status === 'warning').slice(0, 10)

  const totalPorts = summary?.total_ports ?? xmitData.length
  const criticalCount = summary?.severe_ports ?? severeCongestion.length
  const warningCount = summary?.warning_ports ?? moderateCongestion.length
  const healthyCount = Math.max(totalPorts - criticalCount - warningCount, 0)

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
      label: '严重拥塞',
      value: criticalCount,
      description: '等待比例 ≥5% 需立即优化',
      icon: XCircle,
    },
    {
      key: 'warning',
      label: '中度拥塞',
      value: warningCount,
      description: '等待比例 1-5% 需持续监控',
      icon: AlertTriangle,
    },
    {
      key: 'healthy',
      label: '健康端口',
      value: healthyCount,
      description: '无拥塞问题',
      icon: Activity,
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
              <h3>严重拥塞预览 (Top {topCriticalRows.length})</h3>
              <p>等待比例 ≥5% 的端口,按优先级排序,需立即优化路由或增加带宽。</p>
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
                  <th>等待比例</th>
                  <th>XmitTimeCong</th>
                </tr>
              </thead>
              <tbody>
                {topCriticalRows.map((row, idx) => (
                  <tr key={`critical-${row.NodeGUID}-${row.PortNumber}-${idx}`}>
                    <td>
                      <span className="osc-severity-dot severity-critical" />
                      {row.Severity}
                    </td>
                    <td style={{ color: '#dc2626', fontWeight: 'bold' }}>{row.Issue}</td>
                    <td>{row['Node Name'] || row.NodeName || 'N/A'}</td>
                    <td>{row.PortNumber || 'N/A'}</td>
                    <td>{toNumber(row.WaitRatioPct).toFixed(2)}%</td>
                    <td>{toNumber(row.XmitCongestionPct).toFixed(2)}%</td>
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
              <h3>中度拥塞预览 (Top {topWarningRows.length})</h3>
              <p>等待比例 1-5% 的端口,建议持续监控并适度优化。</p>
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
                  <th>等待比例</th>
                  <th>等待时间</th>
                </tr>
              </thead>
              <tbody>
                {topWarningRows.map((row, idx) => (
                  <tr key={`warning-${row.NodeGUID}-${row.PortNumber}-${idx}`}>
                    <td>
                      <span className="osc-severity-dot severity-warning" />
                      {row.Severity}
                    </td>
                    <td style={{ color: '#f59e0b', fontWeight: 'bold' }}>{row.Issue}</td>
                    <td>{row['Node Name'] || row.NodeName || 'N/A'}</td>
                    <td>{row.PortNumber || 'N/A'}</td>
                    <td>{toNumber(row.WaitRatioPct).toFixed(2)}%</td>
                    <td>{toNumber(row.WaitSeconds).toFixed(2)}秒</td>
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
            <h3>完整拥塞数据表 (可搜索/可排序)</h3>
            <p>包含等待时间、XmitTimeCong、FECN/BECN 等完整信息。</p>
          </div>
          <span className="osc-section-tag">展示 {totalPorts} / 总计 {formatCount(totalPorts)}</span>
        </div>
        <DataTable
          rows={tableRows}
          hiddenColumns={['__priority']}
          totalRows={summary?.total_ports ?? xmitData.length}
          searchPlaceholder="搜索节点名、GUID、端口号..."
          pageSize={20}
          preferredColumns={TABLE_PRIORITY}
          defaultSortKey="__priority"
        />
      </div>
    </div>
  )
}

export default CongestionAnalysis
