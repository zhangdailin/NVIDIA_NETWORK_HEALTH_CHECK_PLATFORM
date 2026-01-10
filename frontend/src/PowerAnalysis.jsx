import { Zap, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 电源健康分析页面
 */
function PowerAnalysis({ powerData, summary }) {
  const rows = ensureArray(powerData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查电源状态
    const status = String(row.Status || row['PSU Status'] || '').toLowerCase()
    if (status === 'failed' || status === 'error' || status === 'critical') {
      return 'critical'
    }
    if (status === 'warning' || status === 'degraded') {
      return 'warning'
    }

    // 检查是否存在
    if (row.IsPresent === false) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    const status = String(row.Status || row['PSU Status'] || '').toLowerCase()
    const power = toNumber(row.PowerConsumption || row['Power Consumption'])

    if (severity === 'critical' || severity === 'error') {
      return `电源严重故障 (状态: ${row.Status || 'Critical'})`
    }
    if (status === 'failed' || status === 'error') {
      return `电源失效 (${power > 0 ? power + 'W' : '无输出'})`
    }
    if (severity === 'warning' || severity === 'warn') {
      return `电源告警 (状态: ${row.Status || 'Warning'})`
    }
    if (status === 'degraded') {
      return `电源性能降级 (${power}W)`
    }
    if (row.IsPresent === false) {
      return '电源槽位未安装'
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
      label: '电源总数',
      value: summary?.total_psus ?? rows.length,
      description: '检测到的电源单元',
      icon: Zap,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.psu_critical_count ?? criticalCount,
      description: '电源故障或失效',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.psu_warning_count ?? warningCount,
      description: '电源告警',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
      description: '电源正常',
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
      key: 'PSU',
      label: '电源',
      render: (row) => row.PSU || row['PSU Name'] || row.Name || 'N/A',
    },
    {
      key: 'Status',
      label: '状态',
      render: (row) => row.Status || row['PSU Status'] || 'N/A',
    },
    {
      key: 'Power',
      label: '功率',
      render: (row) => {
        const power = toNumber(row.PowerConsumption || row['Power Consumption'])
        return power > 0 ? `${power}W` : 'N/A'
      },
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PSU',
    'PSU Name',
    'Status',
    'PowerConsumption',
    'Severity',
    'IsPresent',
  ]

  return (
    <UnifiedAnalysisPage
      title="Power Supplies"
      description="电源状态与健康分析"
      emptyMessage="无电源数据"
      emptyHint="请确认采集的数据包中包含电源信息。"
      data={powerData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、电源名..."
    />
  )
}

export default PowerAnalysis
