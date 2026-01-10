import { BarChart3, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 缓冲区直方图分析页面
 */
function BufferHistogramAnalysis({ bufferHistogramData, summary }) {
  const rows = ensureArray(bufferHistogramData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查缓冲区利用率
    const utilization = toNumber(row.UtilizationPct || row.Utilization)

    if (utilization >= 90) {
      return 'critical'
    }
    if (utilization >= 70) {
      return 'warning'
    }
    if (utilization >= 50) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const utilization = toNumber(row.UtilizationPct || row.Utilization)

    if (utilization >= 90) {
      return `缓冲区饱和 (${utilization.toFixed(1)}%)`
    }
    if (utilization >= 70) {
      return `缓冲区利用率高 (${utilization.toFixed(1)}%)`
    }
    if (utilization >= 50) {
      return `缓冲区利用率中等 (${utilization.toFixed(1)}%)`
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
      label: '条目总数',
      value: summary?.total_entries ?? rows.length,
      description: '缓冲区条目',
      icon: BarChart3,
    },
    {
      key: 'critical',
      label: '严重拥堵',
      value: summary?.critical_utilization_count ?? criticalCount,
      description: '利用率>90%',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.high_utilization_count ?? warningCount,
      description: '利用率>70%',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '利用率正常',
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
      key: 'Utilization',
      label: '利用率',
      render: (row) => {
        const val = toNumber(row.UtilizationPct || row.Utilization)
        return val > 0 ? `${val.toFixed(1)}%` : 'N/A'
      },
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'UtilizationPct',
    'Utilization',
    'Samples',
    'MaxUtilization',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Buffer Histograms"
      description="缓冲区拥堵分析与瓶颈检测"
      emptyMessage="无缓冲区直方图数据"
      emptyHint="请确认采集的数据包中包含缓冲区信息。"
      data={bufferHistogramData}
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

export default BufferHistogramAnalysis
