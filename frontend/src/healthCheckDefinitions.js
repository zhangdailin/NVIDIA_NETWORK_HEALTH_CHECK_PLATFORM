import { ensureArray } from './analysisUtils'

const DEFAULT_ROW_SEVERITY_FIELDS = [
  'Severity',
  'severity',
  'Status',
  'status',
  'State',
  'state',
  'Level',
  'level',
  'AlertLevel',
  'CongestionLevel',
  'HealthState',
  'SymbolBERSeverity',
  'EffectiveBERSeverity',
  'RawBERSeverity',
]

const DEFAULT_CRITICAL_VALUE_TOKENS = ['critical', 'severe', 'down', 'fatal', 'error', 'timeout', 'violation', 'failed']
const DEFAULT_WARNING_VALUE_TOKENS = ['warning', 'warn', 'alert', 'degraded', 'issue', 'problem', 'slow', 'missing']

const DEFAULT_CRITICAL_SUMMARY_TOKENS = [
  'critical',
  'severe',
  'error',
  'violation',
  'timeout',
  'uncorrected',
  'failed',
  'degraded',
]
const DEFAULT_WARNING_SUMMARY_TOKENS = [
  'warning',
  'warn',
  'issue',
  'problem',
  'alert',
  'mismatch',
  'missing',
  'over_threshold',
  'degraded',
]
const SUMMARY_SKIP_TOKENS = ['total', 'avg', 'average', 'mean', 'max', 'min', 'healthy', 'distribution']

const HEALTH_CHECK_GROUPS = [
  {
    key: 'connectivity',
    label: '连线 / 链路',
    description: 'Cable/Port/Link 相关健康状态',
    checks: ['cable', 'link_oscillation'],
  },
  {
    key: 'congestion',
    label: '拥塞与带宽',
    description: '发送等待、时延与按通道表现',
    checks: ['xmit', 'latency', 'per_lane_performance'],
  },
  {
    key: 'ber',
    label: '误码监控',
    description: '原始/PHY 误码率检测',
    checks: ['ber', 'ber_advanced'],
  },
  {
    key: 'nodes',
    label: '节点与固件',
    description: 'HCA, System/SM 信息',
    checks: ['hca', 'system_info', 'sm_info'],
  },
  {
    key: 'sensors',
    label: '传感器与电源',
    description: '风扇/温度/功耗相关传感器',
    checks: ['fan', 'power_sensors', 'temp_alerts'],
  },
  {
    key: 'routing',
    label: '路由与拓扑',
    description: '交换机、路由与分层结构',
    checks: ['switches', 'routing', 'routing_config', 'port_hierarchy'],
  },
  {
    key: 'performance',
    label: '性能计数器',
    description: 'MLNX 计数器、PM Delta、PCIe',
    checks: ['mlnx_counters', 'pm_delta', 'pci_performance'],
  },
  {
    key: 'qos_security',
    label: 'QoS / 安全',
    description: 'QoS、PKEY、VPorts、N2N 等',
    checks: ['qos', 'n2n_security', 'pkey', 'vports'],
  },
  {
    key: 'security_config',
    label: 'Fabric 配置',
    description: 'AR/SHARP/FEC/Watchdog 等配置',
    checks: ['ar_info', 'sharp', 'fec_mode', 'credit_watchdog'],
  },
  {
    key: 'diagnostics',
    label: '诊断扩展',
    description: 'PHY 诊断、扩展信息、邻居与缓冲',
    checks: ['phy_diagnostics', 'extended_port_info', 'extended_node_info', 'extended_switch_info', 'buffer_histogram', 'neighbors'],
  },
]

const HEALTH_CHECK_DEFINITIONS = {
  cable: {
    key: 'cable',
    label: 'Cable 跳线',
    group: 'connectivity',
    dataKey: 'cable_issue_rows',
    totalKey: 'cable_total_rows',
    summaryKey: null,
    description: 'DOM 温度、光功率与合规性告警',
  },
  link_oscillation: {
    key: 'link_oscillation',
    label: '链路震荡',
    group: 'connectivity',
    dataKey: 'link_oscillation_issue_rows',
    totalKey: 'link_oscillation_total_rows',
    summaryKey: 'link_oscillation_summary',
    description: 'LinkDownedCounter 统计的抖动路径',
    severity: {
      rowFields: ['Severity'],
      assumeWarningWhenRowPresent: false,
      summaryCriticalTokens: ['critical_paths'],
      summaryWarningTokens: ['warning_paths'],
    },
  },
  xmit: {
    key: 'xmit',
    label: 'Xmit 拥塞',
    group: 'congestion',
    dataKey: 'xmit_issue_rows',
    totalKey: 'xmit_total_rows',
    summaryKey: 'xmit_summary',
    description: 'FECN/BECN、Wait Ratio、拥塞等级',
    severity: {
      rowFields: ['CongestionLevel'],
      assumeWarningWhenRowPresent: false,
      summaryCriticalTokens: ['severe_ports'],
      summaryWarningTokens: ['warning_ports', 'fecn_ports', 'becn_ports', 'link_down_ports', 'credit_watchdog_ports'],
    },
  },
  latency: {
    key: 'latency',
    label: 'Latency',
    group: 'congestion',
    dataKey: 'histogram_issue_rows',
    totalKey: 'histogram_total_rows',
    summaryKey: 'histogram_summary',
    description: '往返时延直方图与重尾检测',
    severity: {
      rowFields: [],
      assumeWarningWhenRowPresent: false,
      summaryCriticalTokens: ['severe_tail_ports'],
      summaryWarningTokens: ['high_p99_ports', 'upper_bucket_ports'],
    },
  },
  per_lane_performance: {
    key: 'per_lane_performance',
    label: 'Per-Lane 性能',
    group: 'congestion',
    dataKey: 'per_lane_performance_issue_rows',
    totalKey: 'per_lane_performance_total_rows',
    summaryKey: 'per_lane_performance_summary',
    description: '按 Lane 统计的误码/降速',
    severity: {
      rowFields: ['Severity'],
      assumeWarningWhenRowPresent: false,
      summaryCriticalTokens: ['critical_ports'],
      summaryWarningTokens: ['warning_ports', 'ports_with_lane_issues', 'ports_with_eq_issues'],
    },
  },
  ber: {
    key: 'ber',
    label: 'BER',
    group: 'ber',
    dataKey: 'ber_issue_rows',
    totalKey: 'ber_total_rows',
    summaryKey: null,
    description: 'Symbol / Effective / Raw BER',
    severity: {
      rowFields: [...DEFAULT_ROW_SEVERITY_FIELDS, 'EffectiveBERSeverity', 'RawBERSeverity', 'SymbolBERSeverity'],
    },
  },
  ber_advanced: {
    key: 'ber_advanced',
    label: 'BER Advanced',
    group: 'ber',
    dataKey: 'ber_advanced_issue_rows',
    totalKey: 'ber_advanced_total_rows',
    summaryKey: 'ber_advanced_summary',
    description: 'PHY DB16/FEC 误码统计',
  },
  hca: {
    key: 'hca',
    label: 'HCA/Firmware',
    group: 'nodes',
    dataKey: 'hca_issue_rows',
    totalKey: 'hca_total_rows',
    summaryKey: null,
    description: '驱动/固件级别、MTUSB 错误等',
  },
  system_info: {
    key: 'system_info',
    label: 'System Info',
    group: 'nodes',
    dataKey: 'system_info_issue_rows',
    totalKey: 'system_info_total_rows',
    summaryKey: 'system_info_summary',
    description: '系统级别信息及异常摘要',
  },
  sm_info: {
    key: 'sm_info',
    label: 'SM Info',
    group: 'nodes',
    dataKey: 'sm_info_issue_rows',
    totalKey: 'sm_info_total_rows',
    summaryKey: 'sm_info_summary',
    description: '子网管理器状态/警告',
  },
  fan: {
    key: 'fan',
    label: 'Fans',
    group: 'sensors',
    dataKey: 'fan_issue_rows',
    totalKey: 'fan_total_rows',
    summaryKey: null,
    description: '风扇转速与告警',
  },
  power_sensors: {
    key: 'power_sensors',
    label: 'Power Sensors',
    group: 'sensors',
    dataKey: 'power_sensors_issue_rows',
    totalKey: 'power_sensors_total_rows',
    summaryKey: 'power_sensors_summary',
    description: '节点功耗/传感器异常',
  },
  temp_alerts: {
    key: 'temp_alerts',
    label: 'Temp Alerts',
    group: 'sensors',
    dataKey: 'temp_alerts_issue_rows',
    totalKey: 'temp_alerts_total_rows',
    summaryKey: 'temp_alerts_summary',
    description: '阈值配置与温度告警',
  },
  switches: {
    key: 'switches',
    label: 'Switches',
    group: 'routing',
    dataKey: 'switch_issue_rows',
    totalKey: 'switch_total_rows',
    summaryKey: 'switch_summary',
    description: '交换机属性与异常端口',
  },
  routing: {
    key: 'routing',
    label: 'Routing',
    group: 'routing',
    dataKey: 'routing_issue_rows',
    totalKey: 'routing_total_rows',
    summaryKey: 'routing_summary',
    description: '路由异常/不可达路径',
  },
  routing_config: {
    key: 'routing_config',
    label: 'Routing Config',
    group: 'routing',
    dataKey: 'routing_config_issue_rows',
    totalKey: 'routing_config_total_rows',
    summaryKey: 'routing_config_summary',
    description: 'HBF/PFRN 配置对比',
  },
  port_hierarchy: {
    key: 'port_hierarchy',
    label: 'Port Hierarchy',
    group: 'routing',
    dataKey: 'port_hierarchy_issue_rows',
    totalKey: 'port_hierarchy_total_rows',
    summaryKey: 'port_hierarchy_summary',
    description: '分层拓扑与关键节点',
  },
  qos: {
    key: 'qos',
    label: 'QoS',
    group: 'qos_security',
    dataKey: 'qos_issue_rows',
    totalKey: 'qos_total_rows',
    summaryKey: 'qos_summary',
    description: 'QoS 配置与违规',
  },
  n2n_security: {
    key: 'n2n_security',
    label: 'N2N Security',
    group: 'qos_security',
    dataKey: 'n2n_security_issue_rows',
    totalKey: 'n2n_security_total_rows',
    summaryKey: 'n2n_security_summary',
    description: 'N2N 能力覆盖率与违规',
  },
  pkey: {
    key: 'pkey',
    label: 'PKEY',
    group: 'qos_security',
    dataKey: 'pkey_issue_rows',
    totalKey: 'pkey_total_rows',
    summaryKey: 'pkey_summary',
    description: 'PKEY 配置与冲突',
  },
  vports: {
    key: 'vports',
    label: 'VPorts',
    group: 'qos_security',
    dataKey: 'vports_issue_rows',
    totalKey: 'vports_total_rows',
    summaryKey: 'vports_summary',
    description: '虚拟端口与多租户配置',
  },
  mlnx_counters: {
    key: 'mlnx_counters',
    label: 'MLNX Counters',
    group: 'performance',
    dataKey: 'mlnx_counters_issue_rows',
    totalKey: 'mlnx_counters_total_rows',
    summaryKey: 'mlnx_counters_summary',
    description: 'Mellanox 性能计数器异常',
  },
  pm_delta: {
    key: 'pm_delta',
    label: 'PM Delta',
    group: 'performance',
    dataKey: 'pm_delta_issue_rows',
    totalKey: 'pm_delta_total_rows',
    summaryKey: 'pm_delta_summary',
    description: 'PM 周期性差异与异常激增',
  },
  pci_performance: {
    key: 'pci_performance',
    label: 'PCIe 性能',
    group: 'performance',
    dataKey: 'pci_performance_issue_rows',
    totalKey: 'pci_performance_total_rows',
    summaryKey: 'pci_performance_summary',
    description: '主机 PCIe 带宽/退化情况',
  },
  ar_info: {
    key: 'ar_info',
    label: 'Adaptive Routing',
    group: 'security_config',
    dataKey: 'ar_info_issue_rows',
    totalKey: 'ar_info_total_rows',
    summaryKey: 'ar_info_summary',
    description: 'AR 配置与异常',
  },
  sharp: {
    key: 'sharp',
    label: 'SHARP',
    group: 'security_config',
    dataKey: 'sharp_issue_rows',
    totalKey: 'sharp_total_rows',
    summaryKey: 'sharp_summary',
    description: 'SHARP 会话与节点支持情况',
  },
  fec_mode: {
    key: 'fec_mode',
    label: 'FEC Mode',
    group: 'security_config',
    dataKey: 'fec_mode_issue_rows',
    totalKey: 'fec_mode_total_rows',
    summaryKey: 'fec_mode_summary',
    description: '链路 FEC 模式与不匹配',
  },
  credit_watchdog: {
    key: 'credit_watchdog',
    label: 'Credit Watchdog',
    group: 'security_config',
    dataKey: 'credit_watchdog_issue_rows',
    totalKey: 'credit_watchdog_total_rows',
    summaryKey: 'credit_watchdog_summary',
    description: 'Credit 超时/告警',
  },
  phy_diagnostics: {
    key: 'phy_diagnostics',
    label: 'PHY Diagnostics',
    group: 'diagnostics',
    dataKey: 'phy_diagnostics_issue_rows',
    totalKey: 'phy_diagnostics_total_rows',
    summaryKey: 'phy_diagnostics_summary',
    description: 'PHY 级诊断与误码轨迹',
  },
  extended_port_info: {
    key: 'extended_port_info',
    label: 'Extended Port',
    group: 'diagnostics',
    dataKey: 'extended_port_info_issue_rows',
    totalKey: 'extended_port_info_total_rows',
    summaryKey: 'extended_port_info_summary',
    description: '端口扩展信息 (速率/特性)',
  },
  extended_node_info: {
    key: 'extended_node_info',
    label: 'Extended Node',
    group: 'diagnostics',
    dataKey: 'extended_node_info_issue_rows',
    totalKey: 'extended_node_info_total_rows',
    summaryKey: 'extended_node_info_summary',
    description: '节点扩展信息与异常属性',
  },
  extended_switch_info: {
    key: 'extended_switch_info',
    label: 'Extended Switch',
    group: 'diagnostics',
    dataKey: 'extended_switch_info_issue_rows',
    totalKey: 'extended_switch_info_total_rows',
    summaryKey: 'extended_switch_info_summary',
    description: '交换机扩展信息与故障',
  },
  buffer_histogram: {
    key: 'buffer_histogram',
    label: 'Buffer Histogram',
    group: 'diagnostics',
    dataKey: 'buffer_histogram_issue_rows',
    totalKey: 'buffer_histogram_total_rows',
    summaryKey: 'buffer_histogram_summary',
    description: '缓冲区利用率直方图',
  },
  neighbors: {
    key: 'neighbors',
    label: 'Neighbors',
    group: 'diagnostics',
    dataKey: 'neighbors_issue_rows',
    totalKey: 'neighbors_total_rows',
    summaryKey: 'neighbors_summary',
    description: '邻居和拓扑邻接异常',
  },
}

const HEALTH_CHECK_KEYS = Object.keys(HEALTH_CHECK_DEFINITIONS)

const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value)

const normalizeNumeric = (value) => {
  if (isFiniteNumber(value)) {
    return value
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const stringIncludesAny = (text, tokens) => {
  if (!text || !tokens || !tokens.length) return false
  const lower = text.toLowerCase()
  return tokens.some(token => lower.includes(token))
}

const extractSeverityFromValue = (value, def) => {
  if (value == null) return null
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (!text) return null
    if (stringIncludesAny(text, (def?.criticalTokens || DEFAULT_CRITICAL_VALUE_TOKENS))) {
      return 'critical'
    }
    if (stringIncludesAny(text, (def?.warningTokens || DEFAULT_WARNING_VALUE_TOKENS))) {
      return 'warning'
    }
    return null
  }
  if (isFiniteNumber(value)) {
    return value > 0 ? 'warning' : null
  }
  if (typeof value === 'boolean') {
    return value ? 'warning' : null
  }
  return null
}

const analyzeRows = (rows, def) => {
  const rowFields = def?.severity?.rowFields || DEFAULT_ROW_SEVERITY_FIELDS
  const treatPresenceAsWarning = def?.severity?.assumeWarningWhenRowPresent !== false
  let critical = 0
  let warning = 0

  ensureArray(rows).forEach(row => {
    if (!row || typeof row !== 'object') {
      if (treatPresenceAsWarning) {
        warning += 1
      }
      return
    }
    let detected = null
    for (const field of rowFields) {
      if (Object.prototype.hasOwnProperty.call(row, field)) {
        detected = extractSeverityFromValue(row[field], def?.severity)
        if (detected) break
      }
    }
    if (!detected) {
      for (const [key, value] of Object.entries(row)) {
        const lowerKey = key.toLowerCase()
        if (lowerKey.includes('severity') || lowerKey.includes('status')) {
          detected = extractSeverityFromValue(value, def?.severity)
          if (detected) break
        }
        if (lowerKey.includes('anomaly') && extractSeverityFromValue(value, def?.severity)) {
          detected = extractSeverityFromValue(value, def?.severity)
          break
        }
      }
    }
    if (!detected && treatPresenceAsWarning) {
      warning += 1
    } else if (detected === 'critical') {
      critical += 1
    } else if (detected === 'warning') {
      warning += 1
    }
  })

  return { critical, warning }
}

const analyzeSummary = (summary, def) => {
  if (!summary || typeof summary !== 'object') {
    return { critical: 0, warning: 0 }
  }
  const criticalTokens = def?.severity?.summaryCriticalTokens || DEFAULT_CRITICAL_SUMMARY_TOKENS
  const warningTokens = def?.severity?.summaryWarningTokens || DEFAULT_WARNING_SUMMARY_TOKENS
  let critical = 0
  let warning = 0

  Object.entries(summary).forEach(([key, value]) => {
    const lowerKey = key.toLowerCase()
    if (SUMMARY_SKIP_TOKENS.some(token => lowerKey.includes(token))) {
      return
    }
    if (!isFiniteNumber(value)) {
      return
    }
    if (stringIncludesAny(lowerKey, criticalTokens)) {
      critical += normalizeNumeric(value)
    } else if (stringIncludesAny(lowerKey, warningTokens)) {
      warning += normalizeNumeric(value)
    }
  })

  return { critical, warning }
}

const evaluateSingleCheck = (payload, definition) => {
  if (!definition) return null
  const rows = ensureArray(payload?.[definition.dataKey])
  const summary = definition.summaryKey ? payload?.[definition.summaryKey] : null
  const totals = payload?.[definition.totalKey]
  const summaryCounts = analyzeSummary(summary, definition)
  const rowCounts = analyzeRows(rows, definition)
  const criticalCount = summaryCounts.critical + rowCounts.critical
  const warningCount = summaryCounts.warning + rowCounts.warning
  const hasRows = rows.length > 0
  const status = criticalCount > 0 ? 'critical' : (warningCount > 0 || hasRows ? 'warning' : 'ok')

  return {
    key: definition.key,
    label: definition.label,
    group: definition.group,
    dataKey: definition.dataKey,
    summaryKey: definition.summaryKey,
    totalKey: definition.totalKey,
    description: definition.description,
    status,
    issueCount: criticalCount + warningCount,
    criticalCount,
    warningCount,
    hasRows,
    totalRows: typeof totals === 'number' ? totals : rows.length,
    summary,
  }
}

const evaluateHealthChecks = (payload) => {
  const result = {}
  HEALTH_CHECK_KEYS.forEach(key => {
    result[key] = evaluateSingleCheck(payload, HEALTH_CHECK_DEFINITIONS[key])
  })
  return result
}

export {
  HEALTH_CHECK_GROUPS,
  HEALTH_CHECK_DEFINITIONS,
  HEALTH_CHECK_KEYS,
  evaluateHealthChecks,
}
