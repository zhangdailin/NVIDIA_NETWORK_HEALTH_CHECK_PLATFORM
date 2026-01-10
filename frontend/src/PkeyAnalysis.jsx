import { Key, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { ensureArray } from './analysisUtils'

/**
 * 分区密钥 (PKEY) 分析页面
 */
function PkeyAnalysis({ pkeyData, summary }) {
  const rows = ensureArray(pkeyData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查是否为受限分区或特殊配置
    const membership = String(row.Membership || '').toLowerCase()
    const pkey = String(row.PKey || row.PartitionKey || '')

    if (membership === 'limited' || membership === 'restricted') {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const membership = String(row.Membership || '').toLowerCase()
    const pkey = row.PKey || row.PartitionKey || ''

    if (membership === 'limited' || membership === 'restricted') {
      return `受限分区 (${pkey})`
    }
    if (membership === 'full') {
      return `完全成员 (${pkey})`
    }

    return pkey ? `分区 ${pkey}` : '正常'
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 指标卡片配置
  const metricCards = [
    {
      key: 'entries',
      label: 'PKEY条目',
      value: summary?.total_pkey_entries ?? rows.length,
      description: '分区配置条目',
      icon: Key,
    },
    {
      key: 'partitions',
      label: '唯一分区',
      value: summary?.unique_partitions ?? 0,
      description: '不同的分区数',
      icon: Key,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '配置问题',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '配置正常',
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
      key: 'PKey',
      label: '分区密钥',
      render: (row) => row.PKey || row.PartitionKey || 'N/A',
    },
    {
      key: 'Membership',
      label: '成员类型',
      render: (row) => row.Membership || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'PKey',
    'PartitionKey',
    'Membership',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Partition Keys (PKEY)"
      description="网络隔离与安全分区配置"
      emptyMessage="无PKEY数据"
      emptyHint="请确认采集的数据包中包含分区密钥信息。"
      data={pkeyData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、分区密钥..."
      showInfoLevel={true}
    />
  )
}

export default PkeyAnalysis
