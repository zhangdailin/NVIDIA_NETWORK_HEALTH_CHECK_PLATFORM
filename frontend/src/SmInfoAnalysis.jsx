import { Settings, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * Subnet Manager信息分析页面
 */
function SmInfoAnalysis({ smInfoData, summary }) {
  const rows = ensureArray(smInfoData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查SM状态
    const state = String(row.State || row.SMState || '').toLowerCase()
    if (state === 'notactive' || state === 'not active' || state === 'down') {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const state = String(row.State || row.SMState || '').toLowerCase()
    const role = row.Role || row.SMRole || ''

    if (state === 'notactive' || state === 'not active' || state === 'down') {
      return `SM未激活 (${role})`
    }
    if (state === 'standby') {
      return `备用SM (${role})`
    }
    if (state === 'master') {
      return `主SM (${role})`
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
      key: 'State',
      label: '状态',
      render: (row) => row.State || row.SMState || 'N/A',
    },
    {
      key: 'Priority',
      label: '优先级',
      render: (row) => row.Priority || row.SMPriority || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'State',
    'SMState',
    'Priority',
    'Role',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Subnet Manager"
      description="SM状态、优先级与主/备配置"
      emptyMessage="无SM数据"
      emptyHint="请确认采集的数据包中包含Subnet Manager信息。"
      data={smInfoData}
      summary={summary}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名..."
      showInfoLevel={true}
    />
  )
}

export default SmInfoAnalysis
