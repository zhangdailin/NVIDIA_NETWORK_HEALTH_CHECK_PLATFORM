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

  // 指标卡片配置
  const metricCards = [
    {
      key: 'entries',
      label: '邻居条目',
      value: summary?.total_neighbor_entries ?? rows.length,
      description: '链路关系',
      icon: Users,
    },
    {
      key: 'nodes',
      label: '唯一节点',
      value: summary?.unique_nodes ?? 0,
      description: '不同节点数',
      icon: Users,
    },
    {
      key: 'mismatch',
      label: '不匹配',
      value: summary?.mismatched_speeds ?? 0,
      description: '速度/宽度问题',
      icon: AlertTriangle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '连接正常',
      icon: CheckCircle,
    },
  ]

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
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名..."
    />
  )
}

export default NeighborsAnalysis
