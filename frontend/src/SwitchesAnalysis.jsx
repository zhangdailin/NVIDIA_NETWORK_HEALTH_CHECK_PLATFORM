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

  // 不再使用自定义 metricCards，让 UnifiedAnalysisPage 使用前端统一计算


  // 这样可以确保顶部指标卡片和下方筛选条的数量一致

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
