import { Thermometer, AlertTriangle, ThermometerSun, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 温度传感器分析页面
 */
function TemperatureAnalysis({ temperatureData, summary }) {
  const rows = ensureArray(temperatureData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 根据温度阈值判断
    const temp = toNumber(row.Temperature || row['Current Temperature'])
    const threshold = toNumber(row.Threshold || row['Threshold Temperature'])

    if (threshold > 0 && temp >= threshold) {
      return 'critical'
    }
    if (threshold > 0 && temp >= threshold * 0.9) {
      return 'warning'
    }
    if (temp >= 85) {
      return 'critical'
    }
    if (temp >= 75) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    const temp = toNumber(row.Temperature || row['Current Temperature'])
    const threshold = toNumber(row.Threshold || row['Threshold Temperature'])

    if (severity === 'critical' || severity === 'error') {
      return `温度严重超标 (${temp.toFixed(1)}°C)`
    }
    if (threshold > 0 && temp >= threshold) {
      return `超过阈值 (${temp.toFixed(1)}°C ≥ ${threshold}°C)`
    }
    if (temp >= 85) {
      return `温度过高 (${temp.toFixed(1)}°C ≥ 85°C)`
    }
    if (severity === 'warning' || severity === 'warn') {
      return `温度偏高 (${temp.toFixed(1)}°C)`
    }
    if (threshold > 0 && temp >= threshold * 0.9) {
      return `接近阈值 (${temp.toFixed(1)}°C)`
    }
    if (temp >= 75) {
      return `温度偏高 (${temp.toFixed(1)}°C ≥ 75°C)`
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
      label: '传感器总数',
      value: summary?.total_sensors ?? rows.length,
      description: '检测到的温度传感器',
      icon: Thermometer,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? criticalCount,
      description: '温度超过阈值',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? warningCount,
      description: '温度偏高',
      icon: ThermometerSun,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? healthyCount,
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
      render: (row) => row['Node Name'] || row.NodeName || row.NodeGUID || 'N/A',
    },
    {
      key: 'SensorName',
      label: '传感器',
      render: (row) => row.SensorName || row['Sensor Name'] || row.SensorIndex || 'N/A',
    },
    {
      key: 'Temperature',
      label: '温度',
      render: (row) => `${toNumber(row.Temperature || row['Current Temperature']).toFixed(1)}°C`,
    },
    {
      key: 'Threshold',
      label: '阈值',
      render: (row) => {
        const threshold = toNumber(row.Threshold || row['Threshold Temperature'])
        return threshold > 0 ? `${threshold}°C` : 'N/A'
      },
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'SensorName',
    'Temperature',
    'Threshold',
    'Severity',
  ]

  return (
    <UnifiedAnalysisPage
      title="Temperature Sensors"
      description="温度传感器与热点分析"
      emptyMessage="无温度数据"
      emptyHint="请确认采集的数据包中包含温度传感器信息。"
      data={temperatureData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、传感器名..."
    />
  )
}

export default TemperatureAnalysis
