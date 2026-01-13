import { GitBranch, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 自适应路由分析页面
 */
function RoutingAnalysis({ routingData, summary }) {
  const rows = ensureArray(routingData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 根据错误计数判断
    const frErrors = toNumber(row.FRErrors)
    const rnErrors = toNumber(row.RNErrors)
    const hbfFallbackLocal = toNumber(row.HBFFallbackLocal)
    const hbfFallbackRemote = toNumber(row.HBFFallbackRemote)

    if (frErrors > 0) {
      return 'critical'
    }
    if (rnErrors > 0 || hbfFallbackLocal > 0 || hbfFallbackRemote > 0) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const frErrors = toNumber(row.FRErrors)
    const rnErrors = toNumber(row.RNErrors)
    const hbfFallbackLocal = toNumber(row.HBFFallbackLocal)
    const hbfFallbackRemote = toNumber(row.HBFFallbackRemote)

    if (frErrors > 0) {
      return `快速恢复错误 (${frErrors}次)`
    }
    if (rnErrors > 0) {
      return `RN错误 (${rnErrors}次)`
    }
    if (hbfFallbackLocal > 0 || hbfFallbackRemote > 0) {
      return `HBF回退 (本地: ${hbfFallbackLocal}, 远程: ${hbfFallbackRemote})`
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
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'Port',
      label: '端口',
      render: (row) => row.PortNumber || row['Port Number'] || 'N/A',
    },
    {
      key: 'FRErrors',
      label: 'FR错误',
      render: (row) => toNumber(row.FRErrors).toLocaleString(),
    },
    {
      key: 'RNErrors',
      label: 'RN错误',
      render: (row) => toNumber(row.RNErrors).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'FRErrors',
    'RNErrors',
    'HBFFallbackLocal',
    'HBFFallbackRemote',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Adaptive Routing Analysis"
      description="RN计数器、HBF统计与快速恢复状态"
      emptyMessage="无路由数据"
      emptyHint="请确认采集的数据包中包含路由信息。"
      data={routingData}
      summary={summary}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、端口..."
    />
  )
}

export default RoutingAnalysis
