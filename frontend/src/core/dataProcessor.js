/**
 * 统一数据处理层
 *
 * 负责：
 * 1. 解析后端 API 返回的原始数据
 * 2. 提取和计算关键指标
 * 3. 聚合各检查项的统计数据
 * 4. 确保数据一致性
 */

import { ensureArray, toNumber } from '../analysisUtils'
import { HEALTH_CHECK_DEFINITIONS } from '../healthCheckDefinitions'

/**
 * 处理原始分析数据，返回结构化的指标
 * @param {Object} rawData - 后端返回的原始数据
 * @returns {Object} 处理后的结构化数据
 */
export function processAnalysisData(rawData) {
  if (!rawData) {
    return null
  }

  const {
    health,
    cable_data = [],
    cable_issue_rows = [],
    cable_total_rows = 0,
    ber_data = [],
    ber_issue_rows = [],
    ber_total_rows = 0,
    hca_data = [],
    hca_issue_rows = [],
    hca_total_rows = 0,
    switch_data = [],
    switch_issue_rows = [],
    switch_total_rows = 0,
    xmit_data = [],
    xmit_issue_rows = [],
    xmit_total_rows = 0,
    xmit_summary = {},
    histogram_issue_rows = [],
    histogram_total_rows = 0,
    histogram_summary = {},
    link_oscillation_data = [],
    link_oscillation_issue_rows = [],
    link_oscillation_total_rows = 0,
    link_oscillation_summary = {},
    fan_data = [],
    fan_issue_rows = [],
    fan_total_rows = 0,
    power_sensors_issue_rows = [],
    power_sensors_total_rows = 0,
    temp_alerts_issue_rows = [],
    temp_alerts_total_rows = 0,
  } = rawData

  // 1. 基础指标
  const baseMetrics = {
    totalNodes: health?.total_nodes || 0,
    totalPorts: health?.total_ports || 0,
    healthScore: health?.score || 0,
    healthGrade: health?.grade || 'N/A',
    healthStatus: health?.status || 'Unknown',
  }

  // 2. 设备统计
  const deviceMetrics = calculateDeviceMetrics(rawData)

  // 3. 异常统计
  const anomalyMetrics = calculateAnomalyMetrics(rawData, health)

  // 4. 性能指标（从实际数据中提取，不使用模拟数据）
  const performanceMetrics = calculatePerformanceMetrics(rawData)

  // 5. 各检查项详细统计
  const checkItems = calculateCheckItems(rawData)

  // 6. 快速诊断数据
  const quickDiagnostics = calculateQuickDiagnostics(rawData)

  return {
    ...baseMetrics,
    devices: deviceMetrics,
    anomalies: anomalyMetrics,
    performance: performanceMetrics,
    checkItems,
    quickDiagnostics,
    raw: rawData, // 保留原始数据以供各组件使用
  }
}

/**
 * 计算设备指标
 */
function calculateDeviceMetrics(rawData) {
  const hcaCount = ensureArray(rawData.hca_data || rawData.hca_issue_rows).length
  const switchCount = ensureArray(rawData.switch_data || rawData.switch_issue_rows).length
  const totalDevices = hcaCount + switchCount

  // 从 health 数据中获取异常设备数
  const criticalDevices = rawData.health?.summary?.critical || 0
  const warningDevices = rawData.health?.summary?.warning || 0
  const healthyDevices = Math.max(0, totalDevices - criticalDevices - warningDevices)

  return {
    total: totalDevices,
    hca: hcaCount,
    switches: switchCount,
    healthy: healthyDevices,
    critical: criticalDevices,
    warning: warningDevices,
    healthRate: totalDevices > 0 ? ((healthyDevices / totalDevices) * 100).toFixed(1) : 0,
  }
}

/**
 * 计算异常指标
 */
function calculateAnomalyMetrics(rawData, health) {
  const critical = health?.summary?.critical || 0
  const warning = health?.summary?.warning || 0
  const info = health?.summary?.info || 0

  return {
    total: critical + warning + info,
    critical,
    warning,
    info,
    hasCritical: critical > 0,
    hasWarning: warning > 0,
    severity: critical > 0 ? 'critical' : warning > 0 ? 'warning' : 'ok',
  }
}

/**
 * 计算性能指标（从实际数据中提取）
 */
function calculatePerformanceMetrics(rawData) {
  // 延迟数据：从 histogram_summary 中提取
  const histogramSummary = rawData.histogram_summary || {}
  const avgLatency = extractLatencyValue(histogramSummary)

  // 拥塞数据：从 xmit_summary 中提取
  const xmitSummary = rawData.xmit_summary || {}
  const congestionLevel = extractCongestionLevel(xmitSummary)

  // 链路抖动：从 link_oscillation_summary 中提取
  const linkOscillationSummary = rawData.link_oscillation_summary || {}
  const oscillationCount = linkOscillationSummary.critical_paths || 0

  return {
    latency: {
      avg: avgLatency,
      unit: 'μs',
      status: avgLatency > 100 ? 'warning' : avgLatency > 200 ? 'critical' : 'ok',
    },
    congestion: {
      level: congestionLevel,
      severeCount: xmitSummary.critical_ports || 0,
      warningCount: xmitSummary.warning_ports || 0,
      status: congestionLevel === 'critical' ? 'critical' : congestionLevel === 'warning' ? 'warning' : 'ok',
    },
    linkOscillation: {
      count: oscillationCount,
      status: oscillationCount > 0 ? 'critical' : 'ok',
    },
  }
}

/**
 * 提取延迟值
 */
function extractLatencyValue(summary) {
  // 尝试从 summary 中提取平均延迟
  if (summary.avg_latency) return toNumber(summary.avg_latency)
  if (summary.avgLatency) return toNumber(summary.avgLatency)
  if (summary.mean_latency) return toNumber(summary.mean_latency)

  // 如果没有，尝试从 p50 提取
  if (summary.p50) return toNumber(summary.p50)

  // 默认返回 null 表示无数据
  return null
}

/**
 * 提取拥塞级别
 */
function extractCongestionLevel(summary) {
  const criticalCount = toNumber(summary.critical_ports || 0)
  const warningCount = toNumber(summary.warning_ports || 0)

  if (criticalCount > 0) return 'critical'
  if (warningCount > 0) return 'warning'
  return 'normal'
}

/**
 * 计算各检查项统计
 */
function calculateCheckItems(rawData) {
  const items = {}

  Object.keys(HEALTH_CHECK_DEFINITIONS).forEach(key => {
    const def = HEALTH_CHECK_DEFINITIONS[key]
    const issueRows = ensureArray(rawData[def.dataKey])
    const totalRows = rawData[def.totalKey] || issueRows.length
    const summary = def.summaryKey ? rawData[def.summaryKey] : null

    // 统计严重程度
    const severity = calculateItemSeverity(issueRows, summary, def)

    items[key] = {
      key,
      label: def.label,
      group: def.group,
      issueCount: issueRows.length,
      totalCount: totalRows,
      critical: severity.critical,
      warning: severity.warning,
      info: severity.info,
      status: severity.status,
      hasIssues: issueRows.length > 0,
      summary,
    }
  })

  return items
}

/**
 * 计算单个检查项的严重程度
 */
function calculateItemSeverity(rows, summary, definition) {
  let critical = 0
  let warning = 0
  let info = 0

  // 从行数据中统计
  ensureArray(rows).forEach(row => {
    const severity = extractRowSeverity(row, definition)
    if (severity === 'critical') critical++
    else if (severity === 'warning') warning++
    else info++
  })

  // 从 summary 中提取（如果有）
  if (summary) {
    critical += extractSummaryCount(summary, ['critical', 'critical_count'])
    warning += extractSummaryCount(summary, ['warning', 'warn', 'warning_count'])
  }

  const status = critical > 0 ? 'critical' : warning > 0 ? 'warning' : rows.length > 0 ? 'info' : 'ok'

  return { critical, warning, info, status }
}

/**
 * 从行中提取严重程度
 */
function extractRowSeverity(row, definition) {
  if (!row || typeof row !== 'object') return 'info'

  // 尝试多个可能的字段名
  const severityFields = [
    'Severity',
    'severity',
    'Status',
    'status',
    'Level',
    'level',
    'SymbolBERSeverity',
    'CongestionLevel',
    ...(definition?.severity?.rowFields || []),
  ]

  for (const field of severityFields) {
    const value = row[field]
    if (!value) continue

    const normalized = String(value).toLowerCase()
    if (normalized.includes('critical') || normalized.includes('error')) {
      return 'critical'
    }
    if (normalized.includes('warning') || normalized.includes('warn') || normalized.includes('alert')) {
      return 'warning'
    }
  }

  return 'info'
}

/**
 * 从 summary 中提取计数
 */
function extractSummaryCount(summary, keys) {
  for (const key of keys) {
    if (summary[key]) {
      const value = toNumber(summary[key])
      if (value > 0) return value
    }
  }
  return 0
}

/**
 * 计算快速诊断数据
 */
function calculateQuickDiagnostics(rawData) {
  return {
    cable: {
      total: ensureArray(rawData.cable_data || rawData.cable_issue_rows).length,
      issues: ensureArray(rawData.cable_issue_rows).length,
      status: calculateDiagnosticStatus(rawData.cable_issue_rows),
    },
    ber: {
      total: toNumber(rawData.ber_total_rows || 0),
      issues: ensureArray(rawData.ber_issue_rows).length,
      status: calculateDiagnosticStatus(rawData.ber_issue_rows),
    },
    temperature: {
      total: toNumber(rawData.fan_total_rows || 0) + toNumber(rawData.temp_alerts_total_rows || 0),
      issues: ensureArray(rawData.fan_issue_rows).length + ensureArray(rawData.temp_alerts_issue_rows).length,
      status: calculateDiagnosticStatus([
        ...ensureArray(rawData.fan_issue_rows),
        ...ensureArray(rawData.temp_alerts_issue_rows),
      ]),
    },
    linkOscillation: {
      total: toNumber(rawData.link_oscillation_total_rows || 0),
      issues: ensureArray(rawData.link_oscillation_issue_rows).length,
      status: calculateDiagnosticStatus(rawData.link_oscillation_issue_rows),
    },
    congestion: {
      total: toNumber(rawData.xmit_total_rows || 0),
      issues: ensureArray(rawData.xmit_issue_rows).length,
      status: calculateDiagnosticStatus(rawData.xmit_issue_rows),
    },
  }
}

/**
 * 计算诊断状态
 */
function calculateDiagnosticStatus(issueRows) {
  const rows = ensureArray(issueRows)
  if (rows.length === 0) return 'ok'

  const hasCritical = rows.some(row => {
    const severity = extractRowSeverity(row)
    return severity === 'critical'
  })

  return hasCritical ? 'critical' : 'warning'
}

/**
 * 获取状态显示信息
 */
export function getStatusDisplay(status) {
  const displays = {
    ok: {
      label: '正常',
      color: '#22c55e',
      bgColor: '#f0fdf4',
      icon: 'CheckCircle',
    },
    warning: {
      label: '警告',
      color: '#f59e0b',
      bgColor: '#fffbeb',
      icon: 'AlertTriangle',
    },
    critical: {
      label: '严重',
      color: '#ef4444',
      bgColor: '#fef2f2',
      icon: 'XCircle',
    },
    info: {
      label: '提示',
      color: '#3b82f6',
      bgColor: '#eff6ff',
      icon: 'Info',
    },
  }

  return displays[status] || displays.info
}

/**
 * 格式化数值
 */
export function formatValue(value, unit = '') {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'number') {
    return `${value.toLocaleString()}${unit}`
  }
  return `${value}${unit}`
}

export default {
  processAnalysisData,
  getStatusDisplay,
  formatValue,
}
