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
