import { Fan, AlertTriangle, ThermometerSun, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * 风扇健康分析页面
 * 使用 UnifiedAnalysisPage 统一组件
 */
function FanAnalysis({ fanData, summary }) {
  const rows = ensureArray(fanData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const fanSpeed = toNumber(row.FanSpeed)
    const minSpeed = toNumber(row.MinSpeed)
    const maxSpeed = toNumber(row.MaxSpeed)
    const status = String(row.FanStatus || '').toLowerCase()

    // 严重：风扇停止或转速远低于最小值
    if (status === 'alert' || status === 'failed' || status === 'critical') {
      return 'critical'
    }
    if (minSpeed > 0 && fanSpeed < minSpeed * 0.5) {
      return 'critical'
    }

    // 警告：转速低于最小值或接近最大值
    if (minSpeed > 0 && fanSpeed < minSpeed) {
      return 'warning'
    }
    if (maxSpeed > 0 && fanSpeed > maxSpeed * 0.9) {
      return 'warning'
    }
    if (status === 'warning' || status === 'degraded') {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const fanSpeed = toNumber(row.FanSpeed)
    const minSpeed = toNumber(row.MinSpeed)
    const maxSpeed = toNumber(row.MaxSpeed)
    const status = String(row.FanStatus || '').toLowerCase()

    if (status === 'failed' || status === 'critical') {
      return `风扇故障 (状态: ${row.FanStatus})`
    }
    if (status === 'alert') {
      return `风扇告警 (${fanSpeed} RPM)`
    }
    if (minSpeed > 0 && fanSpeed < minSpeed * 0.5) {
      return `转速严重偏低 (${fanSpeed} RPM < ${minSpeed * 0.5} RPM)`
    }
    if (minSpeed > 0 && fanSpeed < minSpeed) {
      return `转速低于最小值 (${fanSpeed} RPM < ${minSpeed} RPM)`
    }
    if (maxSpeed > 0 && fanSpeed > maxSpeed * 0.9) {
      return `转速接近上限 (${fanSpeed} RPM > ${maxSpeed * 0.9} RPM)`
    }
    if (status === 'warning' || status === 'degraded') {
      return `风扇警告 (状态: ${row.FanStatus})`
    }
    return '正常'
  }

  // 指标卡片配置
  const metricCards = [
    {
      key: 'total',
      label: '风扇总数',
      value: summary?.total_fans ?? rows.length,
      description: '检测到的风扇传感器',
      icon: Fan,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: summary?.critical_count ?? 0,
      description: '风扇故障或转速严重偏低',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: summary?.warning_count ?? 0,
      description: '转速偏低或偏高',
      icon: ThermometerSun,
    },
    {
      key: 'healthy',
      label: '健康',
      value: summary?.healthy_count ?? 0,
      description: '转速正常',
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
      key: 'SensorIndex',
      label: '传感器',
      render: (row) => row.SensorIndex ?? row.FanIndex ?? 'N/A',
    },
    {
      key: 'FanSpeed',
      label: '当前转速',
      render: (row) => `${toNumber(row.FanSpeed).toLocaleString()} RPM`,
    },
    {
      key: 'SpeedRange',
      label: '范围',
      render: (row) => {
        const min = toNumber(row.MinSpeed)
        const max = toNumber(row.MaxSpeed)
        if (min > 0 || max > 0) {
          return `${min.toLocaleString()} - ${max.toLocaleString()} RPM`
        }
        return 'N/A'
      },
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'SensorIndex',
    'FanSpeed',
    'MinSpeed',
    'MaxSpeed',
    'FanStatus',
    'FanAlert',
  ]

  return (
    <UnifiedAnalysisPage
      title="Fan & Chassis Health"
      description="风扇转速与告警状态分析"
      emptyMessage="无风扇数据"
      emptyHint="请确认采集的数据包中包含风扇传感器信息。"
      data={fanData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、GUID、传感器..."
    />
  )
}

export default FanAnalysis
