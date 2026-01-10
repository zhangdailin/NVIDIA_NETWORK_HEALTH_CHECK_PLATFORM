import { Cpu, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * Mellanox计数器分析页面
 */
function MlnxCountersAnalysis({ mlnxCountersData, summary }) {
  const rows = ensureArray(mlnxCountersData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 根据计数器值判断
    const rnrRetries = toNumber(row.RNRRetries || row.RnrRetryCount)
    const timeouts = toNumber(row.Timeouts || row.TimeoutCount)
    const totalErrors = toNumber(row.TotalErrors || row.QPErrors)

    if (timeouts > 1000 || totalErrors > 100) {
      return 'critical'
    }
    if (rnrRetries > 100 || timeouts > 0 || totalErrors > 0) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const rnrRetries = toNumber(row.RNRRetries || row.RnrRetryCount)
    const timeouts = toNumber(row.Timeouts || row.TimeoutCount)
    const totalErrors = toNumber(row.TotalErrors || row.QPErrors)

    if (timeouts > 1000) {
      return `超时严重 (${timeouts.toLocaleString()}次)`
    }
    if (totalErrors > 100) {
      return `QP错误过多 (${totalErrors.toLocaleString()})`
    }
    if (rnrRetries > 100) {
      return `RNR重试过多 (${rnrRetries.toLocaleString()}次)`
    }
    if (timeouts > 0) {
      return `存在超时 (${timeouts}次)`
    }
    if (totalErrors > 0) {
      return `存在QP错误 (${totalErrors})`
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
      key: 'total',
      label: '端口总数',
      value: summary?.total_ports_analyzed ?? rows.length,
      description: '已分析的端口',
      icon: Cpu,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? criticalCount,
      description: '严重超时或错误',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: 'RNR重试或超时',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '计数器正常',
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
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'Port',
      label: '端口',
      render: (row) => row.PortNumber || row['Port Number'] || 'N/A',
    },
    {
      key: 'RNRRetries',
      label: 'RNR重试',
      render: (row) => toNumber(row.RNRRetries || row.RnrRetryCount).toLocaleString(),
    },
    {
      key: 'Timeouts',
      label: '超时',
      render: (row) => toNumber(row.Timeouts || row.TimeoutCount).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'RNRRetries',
    'Timeouts',
    'TotalErrors',
    'QPErrors',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Mellanox Counters (MLNX_CNTRS_INFO)"
      description="RNR重试、超时与QP错误分析"
      emptyMessage="无MLNX计数器数据"
      emptyHint="请确认采集的数据包中包含Mellanox计数器信息。"
      data={mlnxCountersData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、端口..."
    />
  )
}

export default MlnxCountersAnalysis
