import { Router, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * HBF/PFRN 路由配置分析页面
 */
function RoutingConfigAnalysis({ routingConfigData, summary }) {
  const rows = ensureArray(routingConfigData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查HBF/PFRN配置
    const hbfEnabled = row.HBFEnabled === true || row.HBFEnabled === 'true'
    const pfrnEnabled = row.PFRNEnabled === true || row.PFRNEnabled === 'true'

    if (!hbfEnabled && !pfrnEnabled) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const hbfEnabled = row.HBFEnabled === true || row.HBFEnabled === 'true'
    const pfrnEnabled = row.PFRNEnabled === true || row.PFRNEnabled === 'true'
    const seed = row.Seed || row.HashSeed || ''

    const features = []
    if (hbfEnabled) features.push('HBF')
    if (pfrnEnabled) features.push('PFRN')

    if (features.length > 0) {
      return `已启用: ${features.join(', ')}${seed ? ` (Seed: ${seed})` : ''}`
    }

    return '未启用高级路由'
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
      description: '路由配置',
      icon: Router,
    },
    {
      key: 'hbf',
      label: 'HBF已启用',
      value: summary?.hbf_enabled_count ?? 0,
      description: '哈希转发',
      icon: Router,
    },
    {
      key: 'pfrn',
      label: 'PFRN已启用',
      value: summary?.pfrn_enabled_count ?? 0,
      description: '精确转发',
      icon: Router,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '配置正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '配置状态' },
    {
      key: 'NodeName',
      label: '交换机',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'HBFEnabled',
      label: 'HBF',
      render: (row) => (row.HBFEnabled === true || row.HBFEnabled === 'true') ? 'Yes' : 'No',
    },
    {
      key: 'PFRNEnabled',
      label: 'PFRN',
      render: (row) => (row.PFRNEnabled === true || row.PFRNEnabled === 'true') ? 'Yes' : 'No',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'HBFEnabled',
    'PFRNEnabled',
    'Seed',
    'HashSeed',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="HBF/PFRN Routing Configuration"
      description="哈希转发与精确转发路由通知配置"
      emptyMessage="无路由配置数据"
      emptyHint="请确认采集的数据包中包含路由配置信息。"
      data={routingConfigData}
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

export default RoutingConfigAnalysis
