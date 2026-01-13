import { AlertTriangle, XCircle, Clock, Activity, Database } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, formatCount } from './analysisUtils'

function CongestionAnalysis({ xmitData, summary, taskId, serviceName, enableStreaming }) {
  // 定义严重度判断逻辑 - 优先使用后端返回的 CongestionLevel
  const getSeverity = (row) => {
    // 如果后端已经计算了 CongestionLevel，直接使用
    if (row.CongestionLevel) {
      const level = String(row.CongestionLevel).toLowerCase()
      if (level === 'severe') return 'critical'
      if (level === 'warning') return 'warning'
      if (level === 'normal') return 'ok'
    }

    // 否则使用前端逻辑计算
    const waitRatio = toNumber(row.WaitRatioPct)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)

    if (waitRatio >= 5 || congestionPct >= 5 || linkDowned > 10) return 'critical'
    if (waitRatio >= 1 || congestionPct >= 1 || linkDowned > 0) return 'warning'
    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const waitRatio = toNumber(row.WaitRatioPct)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)
    const fecn = toNumber(row.FECNCount)
    const becn = toNumber(row.BECNCount)
    const reasons = []

    if (waitRatio >= 5) {
      reasons.push(`等待比例 ${waitRatio.toFixed(2)}% ≥ 5%`)
    } else if (waitRatio >= 1) {
      reasons.push(`等待比例 ${waitRatio.toFixed(2)}% ≥ 1%`)
    }
    if (congestionPct >= 5) {
      reasons.push(`XmitTimeCong ${congestionPct.toFixed(2)}% ≥ 5%`)
    } else if (congestionPct >= 1) {
      reasons.push(`XmitTimeCong ${congestionPct.toFixed(2)}% ≥ 1%`)
    }
    if (linkDowned > 10) {
      reasons.push(`链路断开 ${linkDowned} 次`)
    } else if (linkDowned > 0) {
      reasons.push(`链路断开 ${linkDowned} 次`)
    }
    if (fecn > 0 || becn > 0) {
      reasons.push(`FECN/BECN ${fecn}/${becn}`)
    }

    if (!reasons.length) {
      return '无异常'
    }

    return reasons.join(' / ')
  }

  // 计算统计
  const rows = xmitData || []
  const severePorts = rows.filter(r => {
    const waitRatio = toNumber(r.WaitRatioPct)
    const congestionPct = toNumber(r.XmitCongestionPct)
    return waitRatio >= 5 || congestionPct >= 5
  }).length

  const moderatePorts = rows.filter(r => {
    const waitRatio = toNumber(r.WaitRatioPct)
    const congestionPct = toNumber(r.XmitCongestionPct)
    return (waitRatio >= 1 && waitRatio < 5) || (congestionPct >= 1 && congestionPct < 5)
  }).length

  const fecnBecnCount = rows.filter(r => {
    const fecn = toNumber(r.FECNCount)
    const becn = toNumber(r.BECNCount)
    return fecn > 0 || becn > 0
  }).length

  const linkDownCount = rows.filter(r => {
    const linkDowned = toNumber(r.LinkDownedCounter || r.LinkDownedCounterExt)
    return linkDowned > 0
  }).length

  // 指标卡片配置
  const totalPorts = summary?.total_ports ?? rows.length
  const criticalCount = summary?.severe_ports ?? severePorts
  const warningCount = summary?.moderate_ports ?? moderatePorts

  // 不再使用自定义 metricCards，让 UnifiedAnalysisPage 使用前端统一计算


  // 这样可以确保顶部指标卡片和下方筛选条的数量一致

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'Node Name',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'PortNumber',
      label: '端口',
      render: (row) => row.PortNumber || row['Port Number'] || 'N/A',
    },
    {
      key: 'WaitRatioPct',
      label: '等待比例',
      render: (row) => {
        const val = toNumber(row.WaitRatioPct)
        return val > 0 ? `${val.toFixed(2)}%` : '0%'
      },
    },
    {
      key: 'XmitCongestionPct',
      label: 'XmitCong',
      render: (row) => {
        const val = toNumber(row.XmitCongestionPct)
        return val > 0 ? `${val.toFixed(2)}%` : '0%'
      },
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'WaitRatioPct',
    'WaitSeconds',
    'XmitCongestionPct',
    'FECNCount',
    'BECNCount',
    'LinkDownedCounter',
    'LinkDownedCounterExt',
    'CongestionLevel',
  ]

  return (
    <UnifiedAnalysisPage
      title="Congestion Analysis"
      description="网络拥塞与延迟分析"
      emptyMessage="无拥塞故障数据"
      emptyHint="当前网络状态良好，未检测到拥塞问题。点击'显示全部'查看所有端口。"
      data={xmitData}
      summary={summary}
      totalRows={summary?.xmit_wait_rows ?? xmitData?.length}
      taskId={taskId}
      serviceName={serviceName}
      enableStreaming={enableStreaming}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      topPreviewLimit={10}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、GUID、端口号..."
      pageSize={20}
    />
  )
}

export default CongestionAnalysis
