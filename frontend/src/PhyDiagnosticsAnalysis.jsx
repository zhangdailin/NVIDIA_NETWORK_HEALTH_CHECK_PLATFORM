import { Radio, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 物理层诊断分析页面
 */
function PhyDiagnosticsAnalysis({ phyDiagnosticsData, summary }) {
  const rows = ensureArray(phyDiagnosticsData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查诊断字段数量
    const nonZeroFields = toNumber(row.NonZeroFields || row.DiagnosticFields)

    if (nonZeroFields > 10) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const nonZeroFields = toNumber(row.NonZeroFields || row.DiagnosticFields)

    if (nonZeroFields > 10) {
      return `${nonZeroFields} 个诊断字段有值`
    }
    if (nonZeroFields > 0) {
      return `${nonZeroFields} 个字段`
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
      description: '已分析端口',
      icon: Radio,
    },
    {
      key: 'with_data',
      label: '有数据端口',
      value: summary?.ports_with_data ?? 0,
      description: '有诊断数据',
      icon: Radio,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '诊断异常',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '诊断正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '诊断信息' },
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
      key: 'NonZeroFields',
      label: '非零字段数',
      render: (row) => toNumber(row.NonZeroFields || row.DiagnosticFields).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'NonZeroFields',
    'DiagnosticFields',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Physical Layer Diagnostics"
      description="PHY层信号完整性与诊断数据"
      emptyMessage="无物理层诊断数据"
      emptyHint="请确认采集的数据包中包含PHY诊断信息。"
      data={phyDiagnosticsData}
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

export default PhyDiagnosticsAnalysis
