import { Info, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * 系统信息分析页面
 */
function SystemInfoAnalysis({ systemInfoData, summary }) {
  const rows = ensureArray(systemInfoData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 系统信息一般为信息性展示
    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const productType = row.ProductType || row['Product Type'] || ''
    const serialNumber = row.SerialNumber || row['Serial Number'] || ''

    if (productType && serialNumber) {
      return `${productType} (SN: ${serialNumber.slice(0, 10)}...)`
    }
    if (productType) {
      return productType
    }

    return '系统设备'
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 指标卡片配置
  const metricCards = [
    {
      key: 'devices',
      label: '设备总数',
      value: summary?.total_devices ?? rows.length,
      description: '已发现的设备',
      icon: Info,
    },
    {
      key: 'serials',
      label: '唯一序列号',
      value: summary?.unique_serials ?? 0,
      description: '不同的序列号',
      icon: Info,
    },
    {
      key: 'products',
      label: '产品类型',
      value: summary?.product_types ?? 0,
      description: '不同产品型号',
      icon: Info,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '设备正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '设备信息' },
    {
      key: 'NodeName',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'ProductType',
      label: '产品类型',
      render: (row) => row.ProductType || row['Product Type'] || 'N/A',
    },
    {
      key: 'SerialNumber',
      label: '序列号',
      render: (row) => row.SerialNumber || row['Serial Number'] || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'ProductType',
    'SerialNumber',
    'Revision',
    'FirmwareVersion',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="System Information"
      description="硬件清单、序列号与ibdiagnet运行元数据"
      emptyMessage="无系统信息数据"
      emptyHint="请确认采集的数据包中包含系统信息。"
      data={systemInfoData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、序列号、产品类型..."
      showInfoLevel={true}
    />
  )
}

export default SystemInfoAnalysis
