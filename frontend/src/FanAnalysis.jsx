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

  // 不再使用自定义 metricCards，让 UnifiedAnalysisPage 使用前端统一计算


  // 这样可以确保顶部指标卡片和下方筛选条的数量一致

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
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、GUID、传感器..."
    />
  )
}

export default FanAnalysis
