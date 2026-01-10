import { Clock, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 延迟直方图分析页面
 */
function LatencyAnalysis({ histogramData, summary }) {
  const rows = ensureArray(histogramData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 根据延迟指标判断
    const p99OverMedian = toNumber(row.RttP99OverMedian)
    const upperRatio = toNumber(row.RttUpperBucketRatio)

    // P99 超过中位数 5 倍为严重
    if (p99OverMedian >= 5) {
      return 'critical'
    }
    // P99 超过中位数 3 倍或高延迟桶占比超过 20% 为警告
    if (p99OverMedian >= 3 || upperRatio >= 0.2) {
      return 'warning'
    }
    // 高延迟桶占比超过 10% 为信息
    if (upperRatio >= 0.1) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const p99OverMedian = toNumber(row.RttP99OverMedian)
    const upperRatio = toNumber(row.RttUpperBucketRatio) * 100
    const medianUs = toNumber(row.RttMedianUs)
    const p99Us = toNumber(row.RttP99Us)

    if (p99OverMedian >= 5) {
      return `P99延迟严重偏高 (${p99Us.toFixed(1)}μs = ${p99OverMedian.toFixed(1)}x 中位数)`
    }
    if (p99OverMedian >= 3) {
      return `P99延迟偏高 (${p99Us.toFixed(1)}μs = ${p99OverMedian.toFixed(1)}x 中位数)`
    }
    if (upperRatio >= 20) {
      return `高延迟桶占比过高 (${upperRatio.toFixed(1)}%)`
    }
    if (upperRatio >= 10) {
      return `高延迟桶占比偏高 (${upperRatio.toFixed(1)}%)`
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
      value: summary?.total_ports ?? rows.length,
      description: '已分析的端口',
      icon: Clock,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.severe_tail_ports ?? criticalCount,
      description: 'P99延迟严重偏高',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.high_p99_ports ?? warningCount,
      description: 'P99延迟偏高',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '延迟正常',
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
      key: 'Median',
      label: '中位数延迟',
      render: (row) => `${toNumber(row.RttMedianUs).toFixed(2)} μs`,
    },
    {
      key: 'P99',
      label: 'P99延迟',
      render: (row) => `${toNumber(row.RttP99Us).toFixed(2)} μs`,
    },
    {
      key: 'Ratio',
      label: 'P99/中位数',
      render: (row) => `${toNumber(row.RttP99OverMedian).toFixed(1)}x`,
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'RttMedianUs',
    'RttP99Us',
    'RttP99OverMedian',
    'RttUpperBucketRatio',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Latency Histogram"
      description="RTT分布与重尾延迟检测"
      emptyMessage="无延迟直方图数据"
      emptyHint="请确认采集的数据包中包含延迟直方图信息。"
      data={histogramData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、端口..."
      showInfoLevel={true}
    />
  )
}

export default LatencyAnalysis
