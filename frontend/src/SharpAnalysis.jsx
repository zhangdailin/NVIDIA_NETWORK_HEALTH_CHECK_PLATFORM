import { BrainCircuit, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * SHARP 聚合分析页面
 */
function SharpAnalysis({ sharpData, summary }) {
  const rows = ensureArray(sharpData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查SHARP状态
    const treeCapacity = toNumber(row.TreeCapacity || row.MaxTrees)
    const jobsCapacity = toNumber(row.JobsCapacity || row.MaxJobs)

    if (treeCapacity === 0 && jobsCapacity === 0) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const treeCapacity = toNumber(row.TreeCapacity || row.MaxTrees)
    const jobsCapacity = toNumber(row.JobsCapacity || row.MaxJobs)

    if (treeCapacity > 0 || jobsCapacity > 0) {
      return `Trees: ${treeCapacity}, Jobs: ${jobsCapacity}`
    }

    return 'SHARP节点'
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const healthyCount = rows.length - criticalCount - warningCount

  // 指标卡片配置
  const metricCards = [
    {
      key: 'nodes',
      label: 'SHARP节点',
      value: summary?.total_sharp_nodes ?? rows.length,
      description: '聚合节点',
      icon: BrainCircuit,
    },
    {
      key: 'tree_capacity',
      label: '树容量',
      value: summary?.total_tree_capacity ?? 0,
      description: '总树容量',
      icon: BrainCircuit,
    },
    {
      key: 'jobs_capacity',
      label: 'Jobs容量',
      value: summary?.total_jobs_capacity ?? 0,
      description: '总Jobs容量',
      icon: BrainCircuit,
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
    { key: 'IssueReason', label: '容量信息' },
    {
      key: 'NodeName',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'TreeCapacity',
      label: '树容量',
      render: (row) => toNumber(row.TreeCapacity || row.MaxTrees).toLocaleString(),
    },
    {
      key: 'JobsCapacity',
      label: 'Jobs容量',
      render: (row) => toNumber(row.JobsCapacity || row.MaxJobs).toLocaleString(),
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'TreeCapacity',
    'MaxTrees',
    'JobsCapacity',
    'MaxJobs',
    'MaxQPs',
    'DataTypes',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="SHARP (Scalable Hierarchical Aggregation)"
      description="AI/ML集合操作的SHARP聚合节点"
      emptyMessage="无SHARP数据"
      emptyHint="请确认采集的数据包中包含SHARP信息。"
      data={sharpData}
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

export default SharpAnalysis
