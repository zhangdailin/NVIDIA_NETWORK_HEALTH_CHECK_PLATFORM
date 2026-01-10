import { Network, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 扩展交换机信息分析页面
 */
function ExtendedSwitchInfoAnalysis({ extendedSwitchInfoData, summary }) {
  const rows = ensureArray(extendedSwitchInfoData)

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
    const enhancedPort0 = row.EnhancedPort0 === true || row.EnhancedPort0 === 'true'
    const multicastEnabled = row.MulticastEnabled === true || row.MulticastEnabled === 'true'
    const arCapable = row.ARCapable === true || row.ARCapable === 'true'

    const features = []
    if (enhancedPort0) features.push('EnhPort0')
    if (multicastEnabled) features.push('MC')
    if (arCapable) features.push('AR')

    if (features.length > 0) {
      return `功能: ${features.join(', ')}`
    }

    return '交换机'
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 指标卡片配置
  const metricCards = [
    {
      key: 'switches',
      label: '交换机总数',
      value: summary?.total_switches ?? rows.length,
      description: '扩展信息',
      icon: Network,
    },
    {
      key: 'enhanced',
      label: 'Enhanced Port0',
      value: summary?.enhanced_port0_count ?? 0,
      description: '增强端口0',
      icon: Network,
    },
    {
      key: 'multicast',
      label: 'Multicast',
      value: summary?.multicast_enabled_count ?? 0,
      description: '多播启用',
      icon: Network,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '交换机正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '功能描述' },
    {
      key: 'NodeName',
      label: '交换机',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'EnhancedPort0',
      label: 'EnhPort0',
      render: (row) => (row.EnhancedPort0 === true || row.EnhancedPort0 === 'true') ? 'Yes' : 'No',
    },
    {
      key: 'MulticastEnabled',
      label: 'Multicast',
      render: (row) => (row.MulticastEnabled === true || row.MulticastEnabled === 'true') ? 'Yes' : 'No',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'EnhancedPort0',
    'MulticastEnabled',
    'MulticastCapacity',
    'ARCapable',
    'FilterRawEnabled',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Extended Switch Information"
      description="交换机特定能力与LFT/多播容量"
      emptyMessage="无扩展交换机信息数据"
      emptyHint="请确认采集的数据包中包含扩展交换机信息。"
      data={extendedSwitchInfoData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索交换机名..."
      showInfoLevel={true}
    />
  )
}

export default ExtendedSwitchInfoAnalysis
