import { Layers, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * Per-Lane 性能分析页面
 */
function PerLanePerformanceAnalysis({ perLanePerformanceData, summary }) {
  const rows = ensureArray(perLanePerformanceData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查错误计数
    const errorCount = toNumber(row.ErrorCount || row.Errors)
    if (errorCount > 100) {
      return 'critical'
    }
    if (errorCount > 0) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const lane = row.Lane || row.LaneNumber || 'N/A'
    const errorCount = toNumber(row.ErrorCount || row.Errors)
    const issue = row.IssueReason || row.Issue || row.Description || ''

    if (errorCount > 0) {
      return `Lane ${lane}: ${errorCount} 错误${issue ? ` - ${issue}` : ''}`
    }

    return `Lane ${lane}: 正常`
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 指标卡片配置
  const metricCards = [
    {
      key: 'lanes',
      label: 'Lane 总数',
      value: summary?.total_lanes_analyzed?.toLocaleString() ?? rows.length,
      description: 'Per-Lane 分析',
      icon: Layers,
    },
    {
      key: 'ports',
      label: '端口数',
      value: summary?.total_ports_analyzed ?? 0,
      description: '分析的端口',
      icon: Layers,
    },
    {
      key: 'issues',
      label: '问题 Lane',
      value: summary?.lanes_with_issues ?? criticalCount + warningCount,
      description: '有问题的 Lane',
      icon: AlertTriangle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: healthyCount,
      description: 'Lane 正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'NodeName',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || 'N/A',
    },
    {
      key: 'Port',
      label: '端口',
      render: (row) => row.PortNumber || row['Port Number'] || 'N/A',
    },
    {
      key: 'Lane',
      label: 'Lane',
      render: (row) => row.Lane || row.LaneNumber || 'N/A',
    },
    {
      key: 'Errors',
      label: '错误数',
      render: (row) => toNumber(row.ErrorCount || row.Errors).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'Port Number',
    'Lane',
    'LaneNumber',
    'ErrorCount',
    'Errors',
    'IssueReason',
    'Issue',
    'Description',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Per-Lane Performance"
      description="Per-Lane 信号质量与错误分布分析"
      emptyMessage="无 Per-Lane 性能数据"
      emptyHint="请确认采集的数据包中包含 Per-Lane 性能信息。"
      data={perLanePerformanceData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、端口、Lane..."
    />
  )
}

export default PerLanePerformanceAnalysis
