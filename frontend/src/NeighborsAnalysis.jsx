import { Users, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * 邻居拓扑分析页面
 */
function NeighborsAnalysis({ neighborsData, summary }) {
  const rows = ensureArray(neighborsData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查速度/宽度不匹配
    const speedMismatch = row.SpeedMismatch === true || row.SpeedMismatch === 'true'
    const widthMismatch = row.WidthMismatch === true || row.WidthMismatch === 'true'

    if (speedMismatch || widthMismatch) {
      return 'critical'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const speedMismatch = row.SpeedMismatch === true || row.SpeedMismatch === 'true'
    const widthMismatch = row.WidthMismatch === true || row.WidthMismatch === 'true'
    const neighborNode = row.NeighborNodeName || row['Neighbor Node'] || ''

    if (speedMismatch && widthMismatch) {
      return '速度与宽度均不匹配'
    }
    if (speedMismatch) {
      return '链路速度不匹配'
    }
    if (widthMismatch) {
      return '链路宽度不匹配'
    }
    if (neighborNode) {
      return `邻居: ${neighborNode.slice(0, 20)}...`
    }

    return '正常'
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 不再使用自定义 metricCards，让 UnifiedAnalysisPage 使用前端统一计算


  // 这样可以确保顶部指标卡片和下方筛选条的数量一致

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'NodeName',
      label: '源节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'Port',
      label: '端口',
      render: (row) => row.PortNumber || row['Port Number'] || 'N/A',
    },
    {
      key: 'NeighborNode',
      label: '邻居节点',
      render: (row) => row.NeighborNodeName || row['Neighbor Node'] || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'NeighborNodeName',
    'NeighborPortNumber',
    'Speed',
    'Width',
    'SpeedMismatch',
    'WidthMismatch',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Neighbors Topology"
      description="邻居关系与链路属性拓扑分析"
      emptyMessage="无邻居拓扑数据"
      emptyHint="请确认采集的数据包中包含邻居信息。"
      data={neighborsData}
      summary={summary}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名..."
    />
  )
}

export default NeighborsAnalysis
