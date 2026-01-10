import { BarChart3, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * BER 高级分析页面
 */
function BerAdvancedAnalysis({ berAdvancedData, summary }) {
  const rows = ensureArray(berAdvancedData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查 FEC 未校正错误
    const fecUncorrected = toNumber(row.FECUncorrectedBlocks || row.FECUncorrected)
    if (fecUncorrected > 0) {
      return 'critical'
    }

    // 检查 BER 值
    const berLog10 = toNumber(row.EffectiveBERLog10 || row.RawBERLog10)
    if (berLog10 > -9) {
      return 'critical'
    }
    if (berLog10 > -12) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const effectiveBer = row.EffectiveBER || row['Effective BER'] || ''
    const rawBer = row.RawBER || row['Raw BER'] || ''
    const fecUncorrected = toNumber(row.FECUncorrectedBlocks || row.FECUncorrected)

    if (fecUncorrected > 0) {
      return `FEC 未校正: ${fecUncorrected}`
    }
    if (effectiveBer) {
      return `Eff BER: ${effectiveBer}`
    }
    if (rawBer) {
      return `Raw BER: ${rawBer}`
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
      key: 'ports',
      label: '端口总数',
      value: summary?.total_ports ?? rows.length,
      description: 'BER 分析',
      icon: BarChart3,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_ber_count ?? criticalCount,
      description: 'BER 严重',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_ber_count ?? warningCount,
      description: 'BER 警告',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_ports ?? healthyCount,
      description: 'BER 正常',
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
      render: (row) => row['Node Name'] || row.NodeName || 'N/A',
    },
    {
      key: 'Port',
      label: '端口',
      render: (row) => row.PortNumber || row['Port Number'] || 'N/A',
    },
    {
      key: 'EffectiveBER',
      label: 'Effective BER',
      render: (row) => row.EffectiveBER || row['Effective BER'] || 'N/A',
    },
    {
      key: 'RawBER',
      label: 'Raw BER',
      render: (row) => row.RawBER || row['Raw BER'] || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'Port Number',
    'EffectiveBER',
    'Effective BER',
    'RawBER',
    'Raw BER',
    'EffectiveBERLog10',
    'RawBERLog10',
    'FECCorrectedBlocks',
    'FECUncorrectedBlocks',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="BER Advanced Analysis"
      description="位错误率高级指标与 FEC 统计"
      emptyMessage="无 BER 高级分析数据"
      emptyHint="请确认采集的数据包中包含 BER 高级信息。"
      data={berAdvancedData}
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

export default BerAdvancedAnalysis
