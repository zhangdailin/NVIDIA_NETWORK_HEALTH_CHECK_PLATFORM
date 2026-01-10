import { ThermometerSun, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 温度告警分析页面
 */
function TempAlertsAnalysis({ tempAlertsData, summary }) {
  const rows = ensureArray(tempAlertsData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查是否超过阈值
    if (row.OverThreshold === true || row.OverThreshold === 'true') {
      return 'critical'
    }

    const temp = toNumber(row.Temperature || row['Current Temperature'])
    const threshold = toNumber(row.Threshold || row['Threshold Temperature'])
    if (threshold > 0 && temp >= threshold) {
      return 'critical'
    }
    if (threshold > 0 && temp >= threshold * 0.9) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const temp = toNumber(row.Temperature || row['Current Temperature'])
    const threshold = toNumber(row.Threshold || row['Threshold Temperature'])

    if (row.OverThreshold === true || row.OverThreshold === 'true') {
      return `${temp}°C 超过阈值 ${threshold}°C`
    }
    if (threshold > 0 && temp >= threshold) {
      return `${temp}°C >= 阈值 ${threshold}°C`
    }
    if (threshold > 0 && temp >= threshold * 0.9) {
      return `${temp}°C 接近阈值 ${threshold}°C`
    }
    if (temp > 0) {
      return `${temp}°C`
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
      description: '温度传感器',
      icon: ThermometerSun,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? summary?.over_threshold_count ?? criticalCount,
      description: '超过阈值',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '接近阈值',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_sensors ?? healthyCount,
      description: '温度正常',
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
      key: 'Temperature',
      label: '温度',
      render: (row) => `${toNumber(row.Temperature || row['Current Temperature'])}°C`,
    },
    {
      key: 'Threshold',
      label: '阈值',
      render: (row) => `${toNumber(row.Threshold || row['Threshold Temperature'])}°C`,
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'SensorName',
    'SensorIndex',
    'Temperature',
    'Current Temperature',
    'Threshold',
    'Threshold Temperature',
    'OverThreshold',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Temperature Alerts"
      description="温度阈值配置与告警状态"
      emptyMessage="无温度告警数据"
      emptyHint="请确认采集的数据包中包含温度阈值信息。"
      data={tempAlertsData}
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

export default TempAlertsAnalysis
