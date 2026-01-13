import { Shield, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * FEC模式配置分析页面
 */
function FecModeAnalysis({ fecModeData, summary }) {
  const rows = ensureArray(fecModeData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查FEC配置问题
    const mismatch = row.ConfigMismatch === true || row.ConfigMismatch === 'true'
    const noFec = row.NoFEC === true || row.NoFEC === 'true' || String(row.FECActive || '').toLowerCase() === 'none'

    if (mismatch) {
      return 'critical'
    }
    if (noFec) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const mismatch = row.ConfigMismatch === true || row.ConfigMismatch === 'true'
    const noFec = row.NoFEC === true || row.NoFEC === 'true' || String(row.FECActive || '').toLowerCase() === 'none'
    const fecActive = row.FECActive || row['FEC Active'] || ''

    if (mismatch) {
      return 'FEC配置不匹配'
    }
    if (noFec) {
      return '未启用FEC'
    }
    if (fecActive) {
      return `FEC: ${fecActive}`
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
      key: 'FECActive',
      label: 'FEC激活',
      render: (row) => row.FECActive || row['FEC Active'] || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'FECActive',
    'FECSupported',
    'ConfigMismatch',
    'Speed',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="FEC Mode Configuration"
      description="前向纠错支持与每速度启用状态"
      emptyMessage="无FEC模式数据"
      emptyHint="请确认采集的数据包中包含FEC配置信息。"
      data={fecModeData}
      summary={summary}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、端口..."
    />
  )
}

export default FecModeAnalysis
