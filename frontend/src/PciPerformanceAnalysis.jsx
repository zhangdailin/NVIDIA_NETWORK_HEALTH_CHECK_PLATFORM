import { HardDrive, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * PCIe 性能分析页面
 */
function PciPerformanceAnalysis({ pciPerformanceData, summary }) {
  const rows = ensureArray(pciPerformanceData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查降级状态
    if (row.IsDegraded === true || String(row.Degraded || '').toLowerCase() === 'true') {
      return 'critical'
    }

    // 检查 AER 错误
    const aerErrors = toNumber(row.AERErrors || row['AER Errors'])
    if (aerErrors > 0) {
      return 'critical'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const pciGen = row.PCIGen || row['PCI Gen'] || row.Generation || ''
    const pciWidth = row.PCIWidth || row['PCI Width'] || row.Width || ''
    const aerErrors = toNumber(row.AERErrors || row['AER Errors'])

    const issues = []
    if (row.IsDegraded === true || String(row.Degraded || '').toLowerCase() === 'true') {
      issues.push('降级')
    }
    if (aerErrors > 0) {
      issues.push(`AER: ${aerErrors}`)
    }

    if (issues.length > 0) {
      return `${pciGen} x${pciWidth} - ${issues.join(', ')}`
    }

    return `${pciGen} x${pciWidth}`
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 指标卡片配置
  const metricCards = [
    {
      key: 'nodes',
      label: '节点总数',
      value: summary?.total_nodes ?? rows.length,
      description: 'PCIe 设备',
      icon: HardDrive,
    },
    {
      key: 'degraded',
      label: '降级',
      value: summary?.degraded_count ?? criticalCount,
      description: 'PCIe 降级',
      icon: AlertTriangle,
    },
    {
      key: 'aer_errors',
      label: 'AER 错误',
      value: summary?.aer_error_nodes ?? 0,
      description: 'AER 错误节点',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: healthyCount,
      description: 'PCIe 正常',
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
      key: 'PCIGen',
      label: 'Gen',
      render: (row) => row.PCIGen || row['PCI Gen'] || row.Generation || 'N/A',
    },
    {
      key: 'PCIWidth',
      label: 'Width',
      render: (row) => row.PCIWidth || row['PCI Width'] || row.Width || 'N/A',
    },
    {
      key: 'AERErrors',
      label: 'AER 错误',
      render: (row) => toNumber(row.AERErrors || row['AER Errors']).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PCIGen',
    'PCI Gen',
    'Generation',
    'PCIWidth',
    'PCI Width',
    'Width',
    'AERErrors',
    'AER Errors',
    'IsDegraded',
    'Degraded',
    'Bandwidth',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="PCIe Performance"
      description="PCIe 链路性能与降级分析"
      emptyMessage="无 PCIe 性能数据"
      emptyHint="请确认采集的数据包中包含 PCIe 性能信息。"
      data={pciPerformanceData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名..."
    />
  )
}

export default PciPerformanceAnalysis
