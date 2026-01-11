import { Thermometer, Zap, AlertTriangle, Cable, Database } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, hasAlarmFlag } from './analysisUtils'

function CableAnalysis({ cableData, summary }) {
  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    // 优先使用后端返回的 Severity 字段
    const backendSeverity = String(row.Severity || '').toLowerCase()
    if (backendSeverity && (backendSeverity === 'critical' || backendSeverity === 'warning' || backendSeverity === 'normal')) {
      return backendSeverity === 'normal' ? 'ok' : backendSeverity
    }

    // 如果后端未标记，使用前端规则作为后备
    const temp = toNumber(row['Temperature (c)'] || row.Temperature)
    if (temp >= 80) return 'critical'

    const alarms = [
      row['TX Bias Alarm and Warning'],
      row['TX Power Alarm and Warning'],
      row['RX Power Alarm and Warning'],
      row['Latched Voltage Alarm and Warning'],
    ]
    if (alarms.some(hasAlarmFlag)) return 'critical'

    if (temp >= 70) return 'warning'

    const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
    const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
    if ((complianceStatus && complianceStatus !== 'ok') || (speedStatus && speedStatus !== 'ok')) {
      return 'warning'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    // 优先使用后端返回的 Severity 字段
    const backendSeverity = String(row.Severity || '').toLowerCase()

    // 检查温度
    const temp = toNumber(row['Temperature (c)'] || row.Temperature)
    if (temp >= 80) {
      return `温度过高 (${temp.toFixed(1)}°C ≥ 80°C)`
    }

    // 检查告警
    const alarmDetails = []
    if (hasAlarmFlag(row['TX Bias Alarm and Warning'])) alarmDetails.push('TX Bias')
    if (hasAlarmFlag(row['TX Power Alarm and Warning'])) alarmDetails.push('TX Power')
    if (hasAlarmFlag(row['RX Power Alarm and Warning'])) alarmDetails.push('RX Power')
    if (hasAlarmFlag(row['Latched Voltage Alarm and Warning'])) alarmDetails.push('Voltage')
    if (alarmDetails.length) {
      return `光功率告警: ${alarmDetails.join(', ')}`
    }

    if (temp >= 70) {
      return `温度偏高 (${temp.toFixed(1)}°C ≥ 70°C)`
    }

    // 检查合规性
    const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
    const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
    if ((complianceStatus && complianceStatus !== 'ok') || (speedStatus && speedStatus !== 'ok')) {
      return `规格/速率不合规: ${row.CableComplianceStatus || 'N/A'} / ${row.CableSpeedStatus || 'N/A'}`
    }

    // 如果后端标记为问题但前端未识别具体原因
    if (backendSeverity === 'critical') {
      return '严重问题'
    } else if (backendSeverity === 'warning') {
      return '警告问题'
    }

    return '健康'
  }

  // 指标卡片配置
  const totalPorts = summary?.total_cables ?? (cableData?.length || 0)
  const criticalCount = summary?.critical_count ?? 0
  const warningCount = summary?.warning_count ?? 0
  const healthyCount = summary?.healthy_count ?? Math.max(totalPorts - criticalCount - warningCount, 0)

  const metricCards = [
    {
      key: 'total',
      label: '总端口数',
      value: totalPorts,
      description: '全部检测端口',
      icon: Database,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: criticalCount,
      description: '温度 ≥80°C 或光功率告警',
      icon: Thermometer,
    },
    {
      key: 'warning',
      label: '警告',
      value: warningCount,
      description: '温度 ≥70°C 或规格不合规',
      icon: AlertTriangle,
    },
    {
      key: 'healthy',
      label: '健康端口',
      value: healthyCount,
      description: '无异常端口',
      icon: Cable,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'Node Name',
      label: '节点',
      render: (row) => row['Node Name'] || row.NodeName || 'N/A',
    },
    {
      key: 'PortNumber',
      label: '端口',
      render: (row) => row.PortNumber || row['Port Number'] || 'N/A',
    },
    {
      key: 'Temperature',
      label: '温度',
      render: (row) => {
        const temp = toNumber(row['Temperature (c)'] || row.Temperature)
        return `${temp.toFixed(1)}°C`
      },
    },
    {
      key: 'Vendor',
      label: '厂商',
      render: (row) => row.Vendor || row['Vendor Name'] || 'N/A',
    },
    {
      key: 'PN',
      label: '型号',
      render: (row) => row.PN || row['Part Number'] || row.PartNumber || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'PortNumber',
    'Vendor',
    'PN',
    'SN',
    'Temperature (c)',
    'CableComplianceStatus',
    'CableSpeedStatus',
    'TX Bias Alarm and Warning',
    'TX Power Alarm and Warning',
    'RX Power Alarm and Warning',
    'Latched Voltage Alarm and Warning',
    'LengthSMFiber',
    'LengthCopperOrActive',
  ]

  return (
    <UnifiedAnalysisPage
      title="Cable Analysis"
      description="线缆与光模块健康分析"
      emptyMessage="无线缆数据"
      emptyHint="请确认采集的数据包中包含线缆信息表格。"
      data={cableData}
      summary={summary}
      totalRows={summary?.cable_info_rows ?? cableData?.length}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      topPreviewLimit={10}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、GUID、端口号、厂商..."
      pageSize={20}
    />
  )
}

export default CableAnalysis
