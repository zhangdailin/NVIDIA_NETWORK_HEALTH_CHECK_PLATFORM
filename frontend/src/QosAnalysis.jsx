import { Layers, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * QoS / VL仲裁分析页面
 */
function QosAnalysis({ qosData, summary }) {
  const rows = ensureArray(qosData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查VL配置问题
    const vlCount = toNumber(row.VLCount || row.ActiveVLs)
    const highPrioDominant = row.HighPrioDominant === true || row.HighPrioDominant === 'true'

    if (vlCount === 1) {
      return 'info'
    }
    if (highPrioDominant) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const vlCount = toNumber(row.VLCount || row.ActiveVLs)
    const highPrioDominant = row.HighPrioDominant === true || row.HighPrioDominant === 'true'

    if (vlCount === 1) {
      return '仅使用单个VL'
    }
    if (highPrioDominant) {
      return '高优先级VL权重过大'
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
      value: summary?.total_ports_analyzed ?? rows.length,
      description: '已分析的端口',
      icon: Layers,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? criticalCount,
      description: 'QoS配置问题',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.ports_with_high_prio_dominant ?? warningCount,
      description: '高优先级主导',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: 'QoS配置正常',
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
      key: 'VLCount',
      label: 'VL数',
      render: (row) => row.VLCount || row.ActiveVLs || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'VLCount',
    'ActiveVLs',
    'HighPrioDominant',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="QoS / VL Arbitration"
      description="虚拟通道仲裁配置与权重分析"
      emptyMessage="无QoS数据"
      emptyHint="请确认采集的数据包中包含QoS信息。"
      data={qosData}
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

export default QosAnalysis
