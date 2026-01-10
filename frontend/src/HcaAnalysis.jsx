import { Cpu, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { toNumber, ensureArray } from './analysisUtils'

/**
 * HCA 设备与固件分析页面
 *
 * 这个组件需要额外的 firmwareWarnings 和 pciWarnings 数据来显示
 * 完整的固件健康状态评估
 */
function HcaAnalysis({ hcaData, firmwareWarnings = [], pciWarnings = [], summary }) {
  const rows = ensureArray(hcaData)
  const fwWarnings = ensureArray(firmwareWarnings)
  const pciWarns = ensureArray(pciWarnings)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查固件合规性
    const fwCompliant = row.FW_Compliant
    if (fwCompliant === false || fwCompliant === 'false' || fwCompliant === 'False') {
      return 'critical'
    }

    // 检查 PSID 合规性
    const psidCompliant = row.PSID_Compliant
    if (psidCompliant === false || psidCompliant === 'false' || psidCompliant === 'False') {
      return 'warning'
    }

    // 检查最近重启
    if (row.RecentlyRebooted || row.recentlyRebooted) {
      return 'info'
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const issues = []

    const fwCompliant = row.FW_Compliant
    if (fwCompliant === false || fwCompliant === 'false' || fwCompliant === 'False') {
      issues.push('固件过时')
    }

    const psidCompliant = row.PSID_Compliant
    if (psidCompliant === false || psidCompliant === 'false' || psidCompliant === 'False') {
      issues.push('PSID 不支持')
    }

    if (row.RecentlyRebooted || row.recentlyRebooted) {
      const uptime = row['Up Time'] || row.UpTime || row.HWInfo_UpTime || ''
      issues.push(`最近重启${uptime ? ` (${uptime})` : ''}`)
    }

    if (issues.length > 0) {
      return issues.join('; ')
    }

    const fwVersion = row.FW_Version || row.FirmwareVersion || ''
    if (fwVersion) {
      return `FW: ${fwVersion}`
    }

    return '正常'
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const infoCount = rows.filter(r => getSeverity(r) === 'info').length
  const healthyCount = rows.length - criticalCount - warningCount - infoCount

  // 统计固件版本数
  const fwVersions = new Set()
  rows.forEach(row => {
    const fwVersion = row.FW_Version || row.FirmwareVersion
    if (fwVersion) fwVersions.add(fwVersion)
  })

  // 指标卡片配置
  const metricCards = [
    {
      key: 'devices',
      label: '设备总数',
      value: summary?.total ?? rows.length,
      description: 'HCA 设备',
      icon: Cpu,
    },
    {
      key: 'outdated',
      label: '固件过时',
      value: summary?.outdatedFwCount ?? criticalCount,
      description: '需要升级',
      icon: AlertTriangle,
    },
    {
      key: 'psid',
      label: 'PSID 问题',
      value: summary?.psidIssueCount ?? warningCount,
      description: '不支持的 PSID',
      icon: AlertCircle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: healthyCount,
      description: '设备正常',
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
      key: 'FWVersion',
      label: '固件版本',
      render: (row) => row.FW_Version || row.FirmwareVersion || 'N/A',
    },
    {
      key: 'DeviceType',
      label: '设备类型',
      render: (row) => row.DeviceType || row['Device Type'] || 'N/A',
    },
  ]

  // 优先显示的列
  const preferredColumns = [
    'Node Name',
    'NodeGUID',
    'FW_Version',
    'FirmwareVersion',
    'FW_Compliant',
    'PSID',
    'PSID_Compliant',
    'DeviceType',
    'Device Type',
    'Up Time',
    'UpTime',
    'HWInfo_UpTime',
    'RecentlyRebooted',
    'Severity',
  ]

  // 额外的摘要信息
  const extraSummary = (
    <>
      {(fwWarnings.length > 0 || pciWarns.length > 0 || fwVersions.size > 3) && (
        <div style={{ marginTop: '12px', padding: '12px', background: '#1e293b', borderRadius: '8px' }}>
          <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', color: '#e2e8f0' }}>
            <div><strong>固件版本数:</strong> {fwVersions.size}</div>
            <div><strong>固件警告:</strong> <span style={{ color: fwWarnings.length > 0 ? '#f59e0b' : '#22c55e' }}>{fwWarnings.length}</span></div>
            <div><strong>PCI 降级:</strong> <span style={{ color: pciWarns.length > 0 ? '#dc2626' : '#22c55e' }}>{pciWarns.length}</span></div>
          </div>
        </div>
      )}
    </>
  )

  return (
    <UnifiedAnalysisPage
      title="Device & Firmware Analysis"
      description="固件版本不一致与设备异常分析"
      emptyMessage="无 HCA 设备数据"
      emptyHint="请确认采集的数据包中包含 HCA 设备信息。"
      data={hcaData}
      summary={summary}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索节点名、GUID、固件版本..."
      showInfoLevel={true}
      extraSummary={extraSummary}
    />
  )
}

export default HcaAnalysis
