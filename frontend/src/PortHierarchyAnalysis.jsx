import { Database, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * 端口层次结构分析页面
 */
function PortHierarchyAnalysis({ portHierarchyData, summary }) {
  const rows = ensureArray(portHierarchyData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 默认为正常
    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    const role = row.Role || row.PortRole || ''
    const tier = row.Tier || row.PortTier || ''

    if (severity === 'critical' || severity === 'error') {
      return `层次结构问题`
    }
    if (severity === 'warning') {
      return `层次警告`
    }

    return `${tier ? `Tier ${tier}` : ''}${role ? ` - ${role}` : '正常'}`
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
      description: '检测到的端口',
      icon: Database,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? criticalCount,
      description: '层次结构问题',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '配置警告',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '层次正常',
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
      key: 'Tier',
      label: '层级',
      render: (row) => row.Tier || row.PortTier || 'N/A',
    },
    {
      key: 'Role',
      label: '角色',
      render: (row) => row.Role || row.PortRole || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'Tier',
    'Role',
    'Plane',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Port Hierarchy"
      description="网络拓扑层次与端口角色分析"
      emptyMessage="无端口层次数据"
      emptyHint="请确认采集的数据包中包含端口层次信息。"
      data={portHierarchyData}
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

export default PortHierarchyAnalysis
