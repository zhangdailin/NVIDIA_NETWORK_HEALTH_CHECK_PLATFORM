import { BarChart2, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * PM Delta 性能计数器增量分析页面
 */
function PmDeltaAnalysis({ pmDeltaData, summary }) {
  const rows = ensureArray(pmDeltaData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 根据FEC不可纠正块和中继错误判断
    const fecUncorrectable = toNumber(row.FECUncorrectable || row.FecUncorrectedBlocks)
    const relayErrors = toNumber(row.RelayErrors)
    const linkErrors = toNumber(row.LinkErrors || row.PortRcvErrors)

    if (fecUncorrectable > 0 || linkErrors > 100) {
      return 'critical'
    }
    if (relayErrors > 0 || linkErrors > 0) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const fecUncorrectable = toNumber(row.FECUncorrectable || row.FecUncorrectedBlocks)
    const relayErrors = toNumber(row.RelayErrors)
    const linkErrors = toNumber(row.LinkErrors || row.PortRcvErrors)
    const fecCorrected = toNumber(row.FECCorrected || row.FecCorrectedBlocks)

    if (fecUncorrectable > 0) {
      return `FEC不可纠正 (${fecUncorrectable})`
    }
    if (linkErrors > 100) {
      return `链路错误过多 (${linkErrors.toLocaleString()})`
    }
    if (relayErrors > 0) {
      return `中继错误 (${relayErrors})`
    }
    if (linkErrors > 0) {
      return `存在链路错误 (${linkErrors})`
    }
    if (fecCorrected > 1000000) {
      return `高FEC纠正活动 (${(fecCorrected / 1000000).toFixed(1)}M)`
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
      key: 'FECUncorrectable',
      label: 'FEC不可纠正',
      render: (row) => toNumber(row.FECUncorrectable || row.FecUncorrectedBlocks).toLocaleString(),
    },
    {
      key: 'RelayErrors',
      label: '中继错误',
      render: (row) => toNumber(row.RelayErrors).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'FECCorrected',
    'FECUncorrectable',
    'RelayErrors',
    'XmitData',
    'RcvData',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Performance Monitor Delta (PM_DELTA)"
      description="诊断期间的实时计数器增量：FEC活动、流量与错误"
      emptyMessage="无PM Delta数据"
      emptyHint="请确认采集的数据包中包含性能计数器增量信息。"
      data={pmDeltaData}
      summary={summary}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、端口..."
    />
  )
}

export default PmDeltaAnalysis
