import { HardDrive, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 扩展节点信息分析页面
 */
function ExtendedNodeInfoAnalysis({ extendedNodeInfoData, summary }) {
  const rows = ensureArray(extendedNodeInfoData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const nodeType = row.NodeType || row['Node Type'] || ''
    const numPorts = toNumber(row.NumPorts || row.PortCount)

    if (nodeType && numPorts > 0) {
      return `${nodeType} (${numPorts} 端口)`
    }
    if (nodeType) {
      return nodeType
    }

    return '节点信息'
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
      description: '扩展节点信息',
      icon: HardDrive,
    },
    {
      key: 'ports',
      label: '端口总数',
      value: summary?.total_ports ?? 0,
      description: '所有节点端口',
      icon: HardDrive,
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
      description: '节点正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '节点信息' },
    {
      key: 'NodeName',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'NodeType',
      label: '类型',
      render: (row) => row.NodeType || row['Node Type'] || 'N/A',
    },
    {
      key: 'NumPorts',
      label: '端口数',
      render: (row) => toNumber(row.NumPorts || row.PortCount).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'NodeType',
    'NumPorts',
    'PortCount',
    'SMP',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Extended Node Information"
      description="扩展节点属性与SMP能力"
      emptyMessage="无扩展节点信息数据"
      emptyHint="请确认采集的数据包中包含扩展节点信息。"
      data={extendedNodeInfoData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名..."
      showInfoLevel={true}
    />
  )
}

export default ExtendedNodeInfoAnalysis
