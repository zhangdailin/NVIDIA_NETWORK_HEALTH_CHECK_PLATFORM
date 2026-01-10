import { Zap, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 电源传感器分析页面
 */
function PowerSensorsAnalysis({ powerSensorsData, summary }) {
  const rows = ensureArray(powerSensorsData)

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
    const status = String(row.Status || '').toLowerCase()
    if (status === 'critical' || status === 'error' || status === 'failed') {
      return 'critical'
    }
    if (status === 'warning' || status === 'degraded') {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const status = String(row.Status || '').toLowerCase()
    const power = toNumber(row.PowerMW || row.Power)

    if (status === 'critical' || status === 'error' || status === 'failed') {
      return `电源故障 (${power}mW)`
    }
    if (status === 'warning' || status === 'degraded') {
      return `电源告警 (${power}mW)`
    }
    if (power > 0) {
      return `${(power / 1000).toFixed(1)}W`
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
      key: 'sensors',
      label: '传感器总数',
      value: summary?.total_sensors ?? rows.length,
      description: '电源传感器',
      icon: Zap,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? criticalCount,
      description: '电源故障',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
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
      render: (row) => row['Node Name'] || row.NodeName || 'N/A',
    },
    {
      key: 'Sensor',
      label: '传感器',
      render: (row) => row.SensorName || row['Sensor Name'] || row.SensorIndex || 'N/A',
    },
    {
      key: 'Power',
      label: '功率 (mW)',
      render: (row) => toNumber(row.PowerMW || row.Power).toLocaleString(),
    },
    {
      key: 'Status',
      label: '状态',
      render: (row) => row.Status || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'SensorName',
    'SensorIndex',
    'PowerMW',
    'Power',
    'Status',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Power Sensors"
      description="单个电源传感器读数，用于详细电源监控"
      emptyMessage="无电源传感器数据"
      emptyHint="请确认采集的数据包中包含电源传感器信息。"
      data={powerSensorsData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、传感器..."
    />
  )
}

export default PowerSensorsAnalysis
