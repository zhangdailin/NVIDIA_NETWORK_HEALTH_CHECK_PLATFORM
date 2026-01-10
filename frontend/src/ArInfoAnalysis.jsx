import { Shuffle, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 自适应路由 (AR) 分析页面
 */
function ArInfoAnalysis({ arInfoData, summary }) {
  const rows = ensureArray(arInfoData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查AR/FR/HBF启用状态
    const frEnabled = row.FREnabled === true || row.FREnabled === 'true' || row.FREnabled === 1
    const hbfEnabled = row.HBFEnabled === true || row.HBFEnabled === 'true' || row.HBFEnabled === 1
    const arSupported = row.ARSupported === true || row.ARSupported === 'true' || row.ARSupported === 1

    if (arSupported && !frEnabled && !hbfEnabled) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const frEnabled = row.FREnabled === true || row.FREnabled === 'true' || row.FREnabled === 1
    const hbfEnabled = row.HBFEnabled === true || row.HBFEnabled === 'true' || row.HBFEnabled === 1
    const arSupported = row.ARSupported === true || row.ARSupported === 'true' || row.ARSupported === 1
    const pfrnEnabled = row.PFRNEnabled === true || row.PFRNEnabled === 'true' || row.PFRNEnabled === 1

    const features = []
    if (frEnabled) features.push('FR')
    if (hbfEnabled) features.push('HBF')
    if (pfrnEnabled) features.push('PFRN')

    if (features.length > 0) {
      return `已启用: ${features.join(', ')}`
    }
    if (arSupported) {
      return 'AR支持但未启用高级特性'
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
      key: 'switches',
      label: '交换机总数',
      value: summary?.total_switches ?? rows.length,
      description: '支持AR的交换机',
      icon: Shuffle,
    },
    {
      key: 'fr_enabled',
      label: 'FR已启用',
      value: summary?.fr_enabled ?? 0,
      description: '快速恢复',
      icon: CheckCircle,
    },
    {
      key: 'hbf_enabled',
      label: 'HBF已启用',
      value: summary?.hbf_enabled ?? 0,
      description: '哈希转发',
      icon: CheckCircle,
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
    { key: 'IssueReason', label: '状态描述' },
    {
      key: 'NodeName',
      label: '交换机',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'FREnabled',
      label: 'FR',
      render: (row) => (row.FREnabled === true || row.FREnabled === 'true' || row.FREnabled === 1) ? 'Yes' : 'No',
    },
    {
      key: 'HBFEnabled',
      label: 'HBF',
      render: (row) => (row.HBFEnabled === true || row.HBFEnabled === 'true' || row.HBFEnabled === 1) ? 'Yes' : 'No',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'ARSupported',
    'FREnabled',
    'FRSupported',
    'HBFEnabled',
    'HBFSupported',
    'PFRNEnabled',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Adaptive Routing (AR)"
      description="AR、快速恢复 (FR) 与哈希转发 (HBF) 配置"
      emptyMessage="无AR信息数据"
      emptyHint="请确认采集的数据包中包含自适应路由信息。"
      data={arInfoData}
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

export default ArInfoAnalysis
