import { Shield, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * N2N (Node-to-Node) 安全分析页面
 */
function N2nSecurityAnalysis({ n2nSecurityData, summary }) {
  const rows = ensureArray(n2nSecurityData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查安全违规
    if (row.SecurityViolation === true || row.SecurityViolation === 'true') {
      return 'critical'
    }

    // 检查 N2N 未启用
    const n2nEnabled = row.N2NEnabled === true || row.N2NEnabled === 'true'
    const hasKeys = row.HasKeys === true || row.HasKeys === 'true'

    if (!n2nEnabled && !hasKeys) {
      return 'info'
    }
    if (!n2nEnabled || !hasKeys) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    if (row.SecurityViolation === true || row.SecurityViolation === 'true') {
      return '安全违规'
    }

    const n2nEnabled = row.N2NEnabled === true || row.N2NEnabled === 'true'
    const hasKeys = row.HasKeys === true || row.HasKeys === 'true'
    const capability = row.Capability || row.N2NCapability || ''

    const status = []
    if (n2nEnabled) status.push('N2N已启用')
    else status.push('N2N未启用')

    if (hasKeys) status.push('已配置密钥')
    else status.push('未配置密钥')

    if (capability) {
      return `${status.join(', ')} (${capability})`
    }

    return status.join(', ')
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const infoCount = rows.filter(r => getSeverity(r) === 'info').length
  const healthyCount = rows.length - criticalCount - warningCount - infoCount

  // 计算 N2N 覆盖率
  const nodesWithN2N = rows.filter(r => r.N2NEnabled === true || r.N2NEnabled === 'true').length
  const nodesWithKeys = rows.filter(r => r.HasKeys === true || r.HasKeys === 'true').length
  const n2nCoveragePct = rows.length > 0 ? ((nodesWithN2N / rows.length) * 100).toFixed(1) : 0
  const keyCoveragePct = rows.length > 0 ? ((nodesWithKeys / rows.length) * 100).toFixed(1) : 0

  // 不再使用自定义 metricCards，让 UnifiedAnalysisPage 使用前端统一计算


  // 这样可以确保顶部指标卡片和下方筛选条的数量一致

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '状态描述' },
    {
      key: 'NodeName',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'N2NEnabled',
      label: 'N2N',
      render: (row) => (row.N2NEnabled === true || row.N2NEnabled === 'true') ? 'Yes' : 'No',
    },
    {
      key: 'HasKeys',
      label: '密钥',
      render: (row) => (row.HasKeys === true || row.HasKeys === 'true') ? 'Yes' : 'No',
    },
    {
      key: 'Capability',
      label: '能力',
      render: (row) => row.Capability || row.N2NCapability || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'N2NEnabled',
    'HasKeys',
    'Capability',
    'N2NCapability',
    'SecurityViolation',
    'EncryptionType',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="N2N Security"
      description="节点间加密与安全配置状态"
      emptyMessage="无 N2N 安全数据"
      emptyHint="请确认采集的数据包中包含 N2N 安全信息。"
      data={n2nSecurityData}
      summary={summary}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、GUID..."
      showInfoLevel={true}
    />
  )
}

export default N2nSecurityAnalysis
