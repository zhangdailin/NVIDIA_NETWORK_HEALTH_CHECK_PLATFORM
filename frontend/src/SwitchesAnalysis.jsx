import { Network, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * 交换机信息分析页面
 */
function SwitchesAnalysis({ switchData, summary }) {
  const rows = ensureArray(switchData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查AR/FR配置状态
    const arEnabled = row.AREnabled || row.AR_Enabled
    const frEnabled = row.FREnabled || row.FR_Enabled

    // 如果有自适应路由能力但未启用，标记为info
    if (row.ARSupported && !arEnabled) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    const arEnabled = row.AREnabled || row.AR_Enabled
    const frEnabled = row.FREnabled || row.FR_Enabled

    if (severity === 'critical' || severity === 'error') {
      return `交换机严重问题`
    }
    if (severity === 'warning' || severity === 'warn') {
      return `交换机警告`
    }
    if (row.ARSupported && !arEnabled) {
      return 'AR支持但未启用'
    }
    if (row.FRSupported && !frEnabled) {
      return 'FR支持但未启用'
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
      label: '交换机总数',
      value: summary?.total_switches ?? rows.length,
      description: '检测到的交换机',
      icon: Network,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? criticalCount,
      description: '交换机故障',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '配置问题',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '运行正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'NodeName',
      label: '交换机',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'AR',
      label: 'AR',
      render: (row) => (row.AREnabled || row.AR_Enabled) ? '启用' : '未启用',
    },
    {
      key: 'FR',
      label: 'FR',
      render: (row) => (row.FREnabled || row.FR_Enabled) ? '启用' : '未启用',
    },
    {
      key: 'HBF',
      label: 'HBF',
      render: (row) => (row.HBFEnabled || row.HBF_Enabled) ? '启用' : '未启用',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'AREnabled',
    'FREnabled',
    'HBFEnabled',
    'Ports',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Switch Information"
      description="交换机配置与状态分析"
      emptyMessage="无交换机数据"
      emptyHint="请确认采集的数据包中包含交换机信息。"
      data={switchData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索交换机名、GUID..."
      showInfoLevel={true}
    />
  )
}

export default SwitchesAnalysis
