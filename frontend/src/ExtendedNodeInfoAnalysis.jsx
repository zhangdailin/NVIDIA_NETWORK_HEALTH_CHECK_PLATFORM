import { HardDrive, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 扩展节点信息分析页面
 */
function ExtendedNodeInfoAnalysis({ extendedNodeInfoData, summary }) {
  const rows = ensureArray(extendedNodeInfoData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const nodeType = row.NodeType || row['Node Type'] || ''
    const numPorts = toNumber(row.NumPorts || row.PortCount)

    if (nodeType && numPorts > 0) {
      return `${nodeType} (${numPorts} 端口)`
    }
    if (nodeType) {
      return nodeType
    }

    return '节点信息'
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
    { key: 'IssueReason', label: '节点信息' },
    {
      key: 'NodeName',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'NodeType',
      label: '类型',
      render: (row) => row.NodeType || row['Node Type'] || 'N/A',
    },
    {
      key: 'NumPorts',
      label: '端口数',
      render: (row) => toNumber(row.NumPorts || row.PortCount).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'NodeType',
    'NumPorts',
    'PortCount',
    'SMP',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Extended Node Information"
      description="扩展节点属性与SMP能力"
      emptyMessage="无扩展节点信息数据"
      emptyHint="请确认采集的数据包中包含扩展节点信息。"
      data={extendedNodeInfoData}
      summary={summary}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名..."
      showInfoLevel={true}
    />
  )
}

export default ExtendedNodeInfoAnalysis
