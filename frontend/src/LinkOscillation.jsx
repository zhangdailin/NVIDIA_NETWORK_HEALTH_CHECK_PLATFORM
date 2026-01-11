import { Activity, AlertTriangle, ArrowRightLeft, RefreshCw, Shield } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray, toFiniteNumber, formatCount } from './analysisUtils'

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

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row?.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 根据 LinkDownedCounter 总数判断
    const totalFlaps = Number(row.TotalLinkFlaps) || 0
    if (totalFlaps >= 100) return 'critical'
    if (totalFlaps >= 20) return 'warning'
    return 'info'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const totalFlaps = Number(row.TotalLinkFlaps) || 0
    const node1LinkDown = resolveLinkDownCount(row, 1)
    const node2LinkDown = resolveLinkDownCount(row, 2)

    if (totalFlaps >= 100) {
      return `严重链路震荡 (${formatCount(totalFlaps)} 次)`
    }
    if (totalFlaps >= 20) {
      return `链路震荡 (${formatCount(totalFlaps)} 次)`
    }
    if (totalFlaps > 0) {
      return `链路抖动 (${formatCount(totalFlaps)} 次)`
    }
    return `Node1: ${node1LinkDown}, Node2: ${node2LinkDown}`
  }

  // 计算统计
  const criticalPaths = rows.filter(r => getSeverity(r) === 'critical').length
  const warningPaths = rows.filter(r => getSeverity(r) === 'warning').length
  const infoPaths = rows.filter(r => getSeverity(r) === 'info').length

  // 指标卡片配置
  const totalPaths = summary?.total_paths ?? rows.length
  const previewRows = summary?.preview_rows ?? rows.length
  const maxLinkFlaps = summary?.max_link_flaps ?? ((rows[0] ? Number(rows[0].TotalLinkFlaps) : 0) || 0)

  const metricCards = [
    {
      key: 'total',
      label: '检测到的路径',
      value: totalPaths,
      description: 'LinkDownedCounter > 0 的唯一端到端路径',
      icon: Activity,
    },
    {
      key: 'preview',
      label: '前端预览行数',
      value: previewRows,
      description: '最多展示 200 条高频震荡路径',
      icon: RefreshCw,
    },
    {
      key: 'critical',
      label: '严重链路 (≥100 次)',
      value: summary?.critical_paths ?? criticalPaths,
      description: '持续抖动，需要优先处理',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '告警链路 (20-99 次)',
      value: summary?.warning_paths ?? warningPaths,
      description: '存在频繁 flap 迹象',
      icon: Shield,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'Path',
      label: '路径',
      render: (row) => buildPathLabel(row),
    },
    {
      key: 'TotalLinkFlaps',
      label: '总震荡次数',
      render: (row) => formatCount(row.TotalLinkFlaps || 0),
    },
    {
      key: 'Node1LinkDown',
      label: 'Node1 LinkDown',
      render: (row) => formatCount(resolveLinkDownCount(row, 1)),
    },
    {
      key: 'Node2LinkDown',
      label: 'Node2 LinkDown',
      render: (row) => formatCount(resolveLinkDownCount(row, 2)),
    },
  ]

  // 为数据添加格式化字段
  const enrichedData = rows.map(row => ({
    ...row,
    Path: buildPathLabel(row),
    Node1LinkDown: resolveLinkDownCount(row, 1),
    Node2LinkDown: resolveLinkDownCount(row, 2),
  }))

  // 优先显示的列
  const preferredColumns = [
    'Path',
    'TotalLinkFlaps',
    'Node1LinkDown',
    'Node2LinkDown',
    'NodeDesc1',
    'PortNum1',
    'NodeDesc2',
    'PortNum2',
  ]

  // 自定义渲染：高亮路径
  const renderCustomSection = ({ annotatedRows, severityCounts }) => {
    const topRow = annotatedRows[0]
    if (!topRow) return null

    const endpoints = [endpointFromRow(topRow, 1), endpointFromRow(topRow, 2)]
    const totalFlaps = Number(topRow.TotalLinkFlaps) || maxLinkFlaps

    return (
      <div className="osc-section">
        <div className="osc-section-header">
          <div>
            <h3>最严重链路震荡路径</h3>
            <p>LinkDownedCounter 累计次数最高的端到端路径</p>
          </div>
        </div>
        <div className="osc-highlight-path">
          <div className="osc-highlight-endpoint">
            <div className="osc-highlight-node">{endpoints[0]?.name || 'Node A'}</div>
            {endpoints[0]?.port != null && <div className="osc-highlight-port">Port {endpoints[0].port}</div>}
          </div>
          <div className="osc-highlight-arrow">
            <ArrowRightLeft size={32} />
            <div className="osc-highlight-flaps">{formatCount(totalFlaps)} flaps</div>
          </div>
          <div className="osc-highlight-endpoint">
            <div className="osc-highlight-node">{endpoints[1]?.name || 'Node B'}</div>
            {endpoints[1]?.port != null && <div className="osc-highlight-port">Port {endpoints[1].port}</div>}
          </div>
        </div>
      </div>
    )
  }

  return (
    <UnifiedAnalysisPage
      title="Link Oscillation"
      description="链路震荡与抖动分析"
      emptyMessage="未在 PM_INFO 中检测到 LinkDownedCounter 抖动路径"
      emptyHint="请确认采集的 ibdiagnet 包中包含 PM_INFO 表，或等待下次运行。"
      data={enrichedData}
      summary={summary}
      totalRows={totalPaths}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      showInfoLevel={true}
      topPreviewLimit={10}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      renderCustomSection={renderCustomSection}
      searchPlaceholder="搜索路径、节点名称..."
      pageSize={20}
    />
  )
}

export default LinkOscillation
