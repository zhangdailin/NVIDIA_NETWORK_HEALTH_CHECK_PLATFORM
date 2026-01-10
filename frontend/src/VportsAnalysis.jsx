import { Box, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 虚拟端口 (SR-IOV) 分析页面
 */
function VportsAnalysis({ vportsData, summary }) {
  const rows = ensureArray(vportsData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查VNode状态
    const state = String(row.State || row.VNodeState || '').toLowerCase()
    if (state === 'error' || state === 'down') {
      return 'critical'
    }
    if (state === 'inactive' || state === 'not active') {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const state = String(row.State || row.VNodeState || '').toLowerCase()
    const vNodeCount = toNumber(row.VNodeCount)

    if (state === 'error' || state === 'down') {
      return 'VNode状态异常'
    }
    if (state === 'inactive' || state === 'not active') {
      return 'VNode未激活'
    }
    if (vNodeCount > 0) {
      return `${vNodeCount} 个VNode`
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
      key: 'vnodes',
      label: 'VNode总数',
      value: summary?.total_vnodes ?? rows.length,
      description: '虚拟节点',
      icon: Box,
    },
    {
      key: 'vports',
      label: 'VPort总数',
      value: summary?.total_vports ?? 0,
      description: '虚拟端口',
      icon: Box,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '状态异常',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '状态正常',
      icon: CheckCircle,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'NodeName',
      label: '物理节点',
      render: (row) => row['Node Name'] || row.NodeName || row.PhysicalNodeGUID || 'N/A',
    },
    {
      key: 'VNodeGUID',
      label: 'VNode GUID',
      render: (row) => row.VNodeGUID || row['VNode GUID'] || 'N/A',
    },
    {
      key: 'State',
      label: '状态',
      render: (row) => row.State || row.VNodeState || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'PhysicalNodeGUID',
    'VNodeGUID',
    'VNodeCount',
    'VPortCount',
    'State',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Virtual Ports (SR-IOV)"
      description="虚拟节点与虚拟端口分析，用于SR-IOV部署"
      emptyMessage="无VPorts数据"
      emptyHint="请确认采集的数据包中包含虚拟端口信息。"
      data={vportsData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、GUID..."
      showInfoLevel={true}
    />
  )
}

export default VportsAnalysis
