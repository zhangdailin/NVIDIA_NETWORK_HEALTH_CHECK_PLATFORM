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

  // 不再使用自定义 metricCards，让 UnifiedAnalysisPage 使用前端统一计算


  // 这样可以确保顶部指标卡片和下方筛选条的数量一致

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
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、端口、Lane..."
    />
  )
}

export default PerLanePerformanceAnalysis
