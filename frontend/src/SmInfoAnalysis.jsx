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

  // 指标卡片配置
  const metricCards = [
    {
      key: 'total',
      label: 'SM总数',
      value: summary?.total_sms ?? rows.length,
      description: '检测到的SM',
      icon: Settings,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? criticalCount,
      description: 'SM故障',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: 'SM状态异常',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: 'SM正常',
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
      metricCards={metricCards}
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
