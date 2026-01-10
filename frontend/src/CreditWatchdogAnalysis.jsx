import { Timer, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * Credit Watchdog 超时分析页面
 */
function CreditWatchdogAnalysis({ creditWatchdogData, summary }) {
  const rows = ensureArray(creditWatchdogData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查超时计数
    const timeoutCount = toNumber(row.TimeoutCount || row.Timeouts)
    if (timeoutCount > 100) {
      return 'critical'
    }
    if (timeoutCount > 0) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const timeoutCount = toNumber(row.TimeoutCount || row.Timeouts)
    const vl = row.VL || row.VirtualLane || 'N/A'

    if (timeoutCount > 100) {
      return `VL${vl}: ${timeoutCount.toLocaleString()} 次严重超时`
    }
    if (timeoutCount > 0) {
      return `VL${vl}: ${timeoutCount.toLocaleString()} 次超时`
    }

    return `VL${vl}: 正常`
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 指标卡片配置
  const metricCards = [
    {
      key: 'entries',
      label: '条目总数',
      value: summary?.total_entries ?? rows.length,
      description: 'Credit Watchdog',
      icon: Timer,
    },
    {
      key: 'timeout_ports',
      label: '超时端口',
      value: summary?.ports_with_timeouts ?? criticalCount + warningCount,
      description: '有超时事件',
      icon: AlertTriangle,
    },
    {
      key: 'total_events',
      label: '总超时次数',
      value: summary?.total_timeout_events?.toLocaleString() ?? 0,
      description: '所有超时事件',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: healthyCount,
      description: '无超时',
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
      key: 'VL',
      label: 'VL',
      render: (row) => row.VL || row.VirtualLane || 'N/A',
    },
    {
      key: 'Timeouts',
      label: '超时次数',
      render: (row) => toNumber(row.TimeoutCount || row.Timeouts).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'Port Number',
    'VL',
    'VirtualLane',
    'TimeoutCount',
    'Timeouts',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Credit Watchdog Timeouts"
      description="流控信用看门狗超时计数器"
      emptyMessage="无 Credit Watchdog 数据"
      emptyHint="请确认采集的数据包中包含 Credit Watchdog 信息。"
      data={creditWatchdogData}
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

export default CreditWatchdogAnalysis
