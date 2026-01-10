import { PlugZap, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 扩展端口信息分析页面
 */
function ExtendedPortInfoAnalysis({ extendedPortInfoData, summary }) {
  const rows = ensureArray(extendedPortInfoData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查unhealthy状态
    const unhealthyReason = row.UnhealthyReason || row['Unhealthy Reason'] || ''
    const bwUtilization = toNumber(row.BWUtilization || row.BandwidthUtilization)

    if (unhealthyReason && unhealthyReason !== 'N/A' && unhealthyReason !== '') {
      return 'critical'
    }
    if (bwUtilization >= 95) {
      return 'warning'
    }
    if (bwUtilization >= 80) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const unhealthyReason = row.UnhealthyReason || row['Unhealthy Reason'] || ''
    const bwUtilization = toNumber(row.BWUtilization || row.BandwidthUtilization)

    if (unhealthyReason && unhealthyReason !== 'N/A' && unhealthyReason !== '') {
      return `不健康: ${unhealthyReason}`
    }
    if (bwUtilization >= 95) {
      return `带宽利用率过高 (${bwUtilization.toFixed(1)}%)`
    }
    if (bwUtilization >= 80) {
      return `带宽利用率较高 (${bwUtilization.toFixed(1)}%)`
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
      icon: PlugZap,
    },
    {
      key: 'unhealthy',
      label: '不健康端口',
      value: summary?.unhealthy_ports ?? criticalCount,
      description: '存在问题',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '带宽利用率高',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '端口正常',
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
      key: 'BWUtilization',
      label: '带宽利用率',
      render: (row) => {
        const val = toNumber(row.BWUtilization || row.BandwidthUtilization)
        return val > 0 ? `${val.toFixed(1)}%` : 'N/A'
      },
    },
    {
      key: 'UnhealthyReason',
      label: '不健康原因',
      render: (row) => row.UnhealthyReason || row['Unhealthy Reason'] || '-',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'BWUtilization',
    'BandwidthUtilization',
    'UnhealthyReason',
    'FECMode',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Extended Port Info"
      description="带宽利用率、不健康原因与每速度FEC模式"
      emptyMessage="无扩展端口信息数据"
      emptyHint="请确认采集的数据包中包含扩展端口信息。"
      data={extendedPortInfoData}
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

export default ExtendedPortInfoAnalysis
