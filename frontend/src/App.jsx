import { useState, useEffect } from 'react'
import axios from 'axios'
import { Upload, FileText, Activity, Server, AlertTriangle, ShieldCheck, Cpu, CheckCircle, XCircle, AlertCircle, Fan as FanIcon, Clock3, BookOpen, ChevronDown, ChevronUp, Thermometer, Zap, Network, GitBranch, Link, Gauge, Layers, Settings, Database, Cpu as ChipIcon, BarChart2, Key, Box, Info, PlugZap, Shuffle, BrainCircuit, Shield, Radio, Users, BarChart3, HardDrive, Router, ThermometerSun, Timer } from 'lucide-react'
import {
  ERROR_KNOWLEDGE_BASE,
  getErrorExplanation,
  identifyIssueType,
  identifyAllIssues,
  getSeverityInfo,
  ISSUE_CATEGORIES
} from './ErrorExplanations'
import FaultSummary from './FaultSummary'
import CableAnalysis from './CableAnalysis'
import BERAnalysis from './BERAnalysis'
import CongestionAnalysis from './CongestionAnalysis'
import HealthCheckBoard from './HealthCheckBoard'
import { HEALTH_CHECK_GROUPS, HEALTH_CHECK_DEFINITIONS } from './healthCheckDefinitions'
import './App.css'

// Configuration - use relative URL for proxy support
const normalizeBaseUrl = (value = '') => value.replace(/\/+$/, '')
const rawBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_URL || '')
const hasApiSuffix = rawBaseUrl.endsWith('/api')
const apiRootUrl = hasApiSuffix ? rawBaseUrl.slice(0, -4) : rawBaseUrl
const API_ENDPOINT_BASE = hasApiSuffix ? rawBaseUrl : (apiRootUrl ? `${apiRootUrl}/api` : '/api')
const ASSET_BASE_URL = apiRootUrl || ''

const buildApiUrl = (path = '') => `${API_ENDPOINT_BASE}${path}`
const buildAssetUrl = (path = '') => `${ASSET_BASE_URL}${path}`

const resolveMaxFileSize = () => {
  const fromEnv = Number(import.meta.env.VITE_MAX_FILE_SIZE)
  if (Number.isFinite(fromEnv) && fromEnv > 0) {
    return fromEnv
  }
  return 500 * 1024 * 1024 // fallback to 500MB
}

const MAX_FILE_SIZE = resolveMaxFileSize()
const TABLE_PAGE_SIZE = 100
const MAX_TABLE_ROWS = 500
const FILE_SIZE_MB = 500
const FILE_SIZE_BYTES = FILE_SIZE_MB * 1024 * 1024

const ensureArray = (value) => (Array.isArray(value) ? value : [])

const toNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const hasAlarmFlag = (value) => {
  if (value === null || value === undefined) return false
  const text = String(value).trim()
  if (!text || text.toLowerCase() === 'n/a') return false
  const token = text.split(/\s+/)[0]
  if (!token) return false
  try {
    if (token.toLowerCase().startsWith('0x')) {
      return parseInt(token, 16) !== 0
    }
    const parsed = Number(token)
    return Number.isFinite(parsed) && parsed !== 0
  } catch {
    return false
  }
}

const TAB_ICON_MAP = {
  overview: Activity,
  cable: Server,
  cable_enhanced: PlugZap,
  port_health: Gauge,
  links: Link,
  xmit: AlertTriangle,
  latency: Clock3,
  per_lane_performance: Layers,
  ber: ShieldCheck,
  ber_advanced: BarChart3,
  hca: Cpu,
  system_info: Info,
  sm_info: Settings,
  fan: FanIcon,
  temperature: Thermometer,
  power: Zap,
  power_sensors: Zap,
  temp_alerts: ThermometerSun,
  switches: Network,
  routing: GitBranch,
  routing_config: Router,
  port_hierarchy: Database,
  qos: Layers,
  n2n_security: Shield,
  pkey: Key,
  vports: Box,
  mlnx_counters: ChipIcon,
  pm_delta: BarChart2,
  pci_performance: HardDrive,
  ar_info: Shuffle,
  sharp: BrainCircuit,
  fec_mode: Shield,
  credit_watchdog: Timer,
  phy_diagnostics: Radio,
  extended_port_info: PlugZap,
  extended_node_info: HardDrive,
  extended_switch_info: Network,
  buffer_histogram: BarChart3,
  neighbors: Users,
}

const TAB_GROUPS = HEALTH_CHECK_GROUPS.map(group => ({
  ...group,
  tabs: group.checks.map(checkKey => {
    const definition = HEALTH_CHECK_DEFINITIONS[checkKey] || { label: checkKey }
    return {
      key: checkKey,
      label: definition.label || checkKey,
      icon: TAB_ICON_MAP[checkKey] || Activity,
    }
  }),
}))

const TAB_LIST = [
  { key: 'overview', label: '总览', icon: Activity },
  ...TAB_GROUPS.flatMap(group => group.tabs),
]

const TAB_LOOKUP = TAB_LIST.reduce((acc, tab) => {
  acc[tab.key] = tab
  return acc
}, {})

const buildActionPlan = (issues = []) => {
  const safeIssues = ensureArray(issues)
  const dedup = new Set()
  const actions = []

  safeIssues.forEach(issue => {
    const kb = issue.details?.kb
    if (!kb || !Array.isArray(kb.recommended_actions)) return

    kb.recommended_actions.forEach(action => {
      if (dedup.has(action)) return
      dedup.add(action)
      actions.push({
        text: action,
        severity: issue.severity,
        category: issue.category,
        reference: kb.reference,
      })
    })
  })

  return actions
}

const buildCongestionInsights = (rows = []) => {
  const safeRows = ensureArray(rows)
  return safeRows
    .map(row => {
      const ratio = toNumber(row.WaitRatioPct)
      const waitSeconds = toNumber(row.WaitSeconds)
      const level = row.CongestionLevel
      const fecnCount = toNumber(row.FECNCount)
      const becnCount = toNumber(row.BECNCount)
      const congestionPct = toNumber(row.XmitCongestionPct)
      const severity =
        level === 'severe' || ratio >= 5 || congestionPct >= 5
          ? 'critical'
          : level === 'warning' || ratio >= 1 || congestionPct >= 1 || fecnCount > 0 || becnCount > 0
            ? 'warning'
            : 'info'
      return {
        title: `${row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown'} - Port ${row.PortNumber || row['Port Number'] || 'N/A'}`,
        ratio,
        waitSeconds,
        congestionPct,
        fecnCount,
        becnCount,
        severity,
      }
    })
    .filter(item => item.ratio >= 1 || item.congestionPct >= 1 || item.fecnCount > 0 || item.becnCount > 0)
    .sort((a, b) => (Math.max(b.ratio, b.congestionPct) - Math.max(a.ratio, a.congestionPct)))
    .slice(0, 3)
    .map(item => ({
      ...item,
      subtitle: `Wait ratio ${item.ratio.toFixed(1)}%${item.congestionPct ? `, XmitTimeCong ${item.congestionPct.toFixed(2)}%` : ''}`,
      description: `Approx. ${item.waitSeconds.toFixed(2)}s of the sample window was spent waiting. FECN/BECN=${item.fecnCount}/${item.becnCount}. ${
        item.ratio >= 5 || item.congestionPct >= 5 ? 'Severe' : 'Warning'
      } congestion per ibdiagnet (Section 5.2); rebalance flows or add bandwidth.`,
      reference: 'doc/ibdiagnet_health_check_guide.md:338-345',
    }))
}

// 添加问题摘要组件 - 增强版，集成知识库
function ProblemSummary({ title, problems, totalChecked, dataType }) {
  const [expandedProblems, setExpandedProblems] = useState({})

  const toggleProblem = (idx) => {
    setExpandedProblems(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }))
  }

  if (!problems || problems.length === 0) {
    return (
      <div style={{
        padding: '16px',
        marginBottom: '20px',
        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        borderRadius: '8px',
        border: '1px solid #059669'
      }}>
        <h3 style={{ margin: '0 0 8px 0', color: '#fff', fontSize: '1.1rem' }}>
          ✅ {title} - 未发现问题
        </h3>
        <p style={{ margin: 0, color: '#d1fae5', fontSize: '0.95rem' }}>
          已检查 {totalChecked} 个端口，所有指标正常
        </p>
      </div>
    )
  }

  const criticalCount = problems.filter(p => p.severity === 'critical').length
  const warningCount = problems.filter(p => p.severity === 'warning').length

  return (
    <div style={{
      padding: '16px',
      marginBottom: '20px',
      background: criticalCount > 0
        ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
        : 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
      borderRadius: '8px',
      border: `1px solid ${criticalCount > 0 ? '#dc2626' : '#d97706'}`
    }}>
      <h3 style={{ margin: '0 0 12px 0', color: '#fff', fontSize: '1.1rem' }}>
        {criticalCount > 0 ? '🔴' : '⚠️'} {title} - 发现 {problems.length} 类问题
      </h3>
      <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
        {criticalCount > 0 && (
          <span style={{
            padding: '4px 12px',
            background: 'rgba(0,0,0,0.3)',
            borderRadius: '12px',
            color: '#fff',
            fontSize: '0.9rem'
          }}>
            🔴 {criticalCount} 个严重问题
          </span>
        )}
        {warningCount > 0 && (
          <span style={{
            padding: '4px 12px',
            background: 'rgba(0,0,0,0.3)',
            borderRadius: '12px',
            color: '#fff',
            fontSize: '0.9rem'
          }}>
            ⚠️ {warningCount} 个警告
          </span>
        )}
      </div>

      {/* 问题列表 - 可展开查看知识库详情 */}
      <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: '6px', padding: '8px' }}>
        {problems.map((problem, idx) => {
          const isExpanded = expandedProblems[idx]
          const kb = problem.kbType ? getErrorExplanation(problem.kbType) : null

          return (
            <div key={idx} style={{ marginBottom: idx < problems.length - 1 ? '8px' : 0 }}>
              <div
                onClick={() => kb && toggleProblem(idx)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: 'rgba(255,255,255,0.15)',
                  borderRadius: '4px',
                  cursor: kb ? 'pointer' : 'default'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#fff' }}>
                    {problem.severity === 'critical' ? '🔴' : '⚠️'}
                  </span>
                  <span style={{ color: '#fff', fontSize: '0.95rem' }}>{problem.summary}</span>
                </div>
                {kb && (
                  <span style={{ color: 'rgba(255,255,255,0.7)' }}>
                    {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </span>
                )}
              </div>

              {/* 展开的知识库详情 */}
              {isExpanded && kb && (
                <div style={{
                  marginTop: '4px',
                  padding: '12px',
                  background: 'rgba(255,255,255,0.95)',
                  borderRadius: '4px',
                  color: '#1f2937'
                }}>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '1rem', color: '#374151' }}>
                    <BookOpen size={14} style={{ marginRight: '6px' }} />
                    {kb.title} ({kb.titleEn})
                  </h4>

                  <p style={{ margin: '0 0 12px 0', fontSize: '0.9rem', color: '#4b5563' }}>
                    <strong>为什么重要：</strong>{kb.why_it_matters}
                  </p>

                  <div style={{ marginBottom: '12px' }}>
                    <strong style={{ fontSize: '0.85rem', color: '#374151' }}>可能原因：</strong>
                    <ul style={{ margin: '4px 0 0 0', paddingLeft: '20px', fontSize: '0.85rem', color: '#4b5563' }}>
                      {kb.likely_causes?.slice(0, 3).map((cause, i) => (
                        <li key={i}>{cause}</li>
                      ))}
                    </ul>
                  </div>

                  <div style={{ marginBottom: '8px' }}>
                    <strong style={{ fontSize: '0.85rem', color: '#374151' }}>建议操作：</strong>
                    <ol style={{ margin: '4px 0 0 0', paddingLeft: '20px', fontSize: '0.85rem', color: '#4b5563' }}>
                      {kb.recommended_actions?.slice(0, 4).map((action, i) => (
                        <li key={i}>{action}</li>
                      ))}
                    </ol>
                  </div>

                  {kb.mttr_estimate && (
                    <p style={{ margin: '8px 0 0 0', fontSize: '0.8rem', color: '#6b7280' }}>
                      <Clock3 size={12} style={{ marginRight: '4px' }} />
                      预计修复时间: {kb.mttr_estimate}
                    </p>
                  )}

                  {kb.reference && (
                    <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#6b7280' }}>
                      参考文档: {kb.reference}
                    </p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

const buildBerInsights = (rows = []) => {
  const safeRows = ensureArray(rows)
  return safeRows
    .map(row => {
      // Support multiple BER Log10 field names
      const log10 = toNumber(row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10)
      // Support both severity field names
      const severity = row.SymbolBERSeverity || row.Severity || 'info'
      return {
        title: `${row['Node Name'] || row.NodeName || row.NodeGUID || 'Node'} - Port ${row.PortNumber || row['Port Number'] || 'N/A'}`,
        log10,
        severity,
      }
    })
    .filter(item => Number.isFinite(item.log10) && (item.severity === 'critical' || item.severity === 'warning'))
    .sort((a, b) => b.log10 - a.log10)
    .slice(0, 3)
    .map(item => ({
      ...item,
      subtitle: `Symbol BER ~ 10^${item.log10.toFixed(1)}`,
      description: 'Symbol BER should stay at or below 1e-12. Inspect fiber cleanliness, optical power, and module temperature; replace optics if the value stays high.',
      reference: 'doc/ibdiagnet_health_check_guide.md:155-177',
    }))
}

const buildCableInsights = (rows = []) => {
  const safeRows = ensureArray(rows)
  return safeRows
    .map(row => {
      const temp = toNumber(row['Temperature (c)'] ?? row.Temperature)
      const vendor = row.Vendor || row['Vendor Name'] || 'Optic'
      const linkDown = toNumber(row.LinkDownedCounter ?? row.LinkDownedCounterExt)
      const redFlagCounters = ['PortRcvErrors', 'PortXmitDiscards', 'PortRcvRemotePhysicalErrors']
      const hasErrors = redFlagCounters.some(key => toNumber(row[key]) > 0)
      const biasAlarm = hasAlarmFlag(row['TX Bias Alarm and Warning'])
      const txPowerAlarm = hasAlarmFlag(row['TX Power Alarm and Warning'])
      const rxPowerAlarm = hasAlarmFlag(row['RX Power Alarm and Warning'])
      const voltageAlarm = hasAlarmFlag(row['Latched Voltage Alarm and Warning'])
      const opticalIssues = []
      if (biasAlarm) opticalIssues.push('TX bias current alarm')
      if (txPowerAlarm) opticalIssues.push('TX optical power alarm')
      if (rxPowerAlarm) opticalIssues.push('RX optical power alarm')
      if (voltageAlarm) opticalIssues.push('Module supply voltage alarm')

      const severity = temp >= 80 || linkDown > 0 || hasErrors || opticalIssues.length
        ? 'critical'
        : temp >= 70
          ? 'warning'
          : 'info'

      return {
        vendor,
        title: `${vendor} - ${row['Node Name'] || row.NodeName || 'Port'} ${row.PortNumber || row['Port Number'] || 'N/A'}`,
        temp,
        linkDown,
        hasErrors,
        opticalIssues,
        supplyVoltage: row['Supply Voltage Reporting'] ?? row.SupplyVoltageReporting ?? '',
        severity,
      }
    })
    .filter(item => item.temp >= 70 || item.linkDown > 0 || item.hasErrors || item.opticalIssues.length > 0)
    .sort((a, b) => b.temp - a.temp)
    .slice(0, 3)
    .map(item => ({
      ...item,
      subtitle: item.temp
        ? `Module temperature ${item.temp.toFixed(1)}C`
        : item.opticalIssues.length
          ? `${item.opticalIssues.join('; ')}`
          : 'Optical issue detected',
      description:
        item.temp >= 80
          ? 'Optic temperature is in the critical zone. Improve cooling and consider swapping the module.'
          : item.temp >= 70
            ? 'Optic temperature is trending high; clean airflow paths and monitor closely.'
            : item.opticalIssues.length
              ? `Active optical alarms: ${item.opticalIssues.join(', ')}${item.supplyVoltage ? ` (Supply ${item.supplyVoltage})` : ''}. Inspect the module immediately.`
              : 'Error counters exceeded zero; inspect the cable/optic and clear counters before retesting.',
      reference: 'doc/ibdiagnet_health_check_guide.md:170-233,320-357',
      actions:
        item.temp >= 70
          ? ['Check rack airflow or blocked filters', 'Schedule optic replacement if temperature keeps rising']
          : item.opticalIssues.length
            ? ['Clean or replace the optic pair and verify power/bias return to spec', 'Inspect SM logs for optical alarms and reseat the module']
            : ['Inspect cable seating and clean the connector', 'Reset counters and verify whether errors reappear'],
    }))
}

const buildFanInsights = (rows = []) => {
  const safeRows = ensureArray(rows)
  return safeRows
    .map(row => {
      const node = row['Node Name'] || row.NodeName || row.NodeGUID || 'Chassis'
      const sensor = row.SensorIndex ?? row.PortNumber ?? 'N/A'
      const fanSpeed = toNumber(row.FanSpeed)
      const minSpeed = toNumber(row.MinSpeed)
      const maxSpeed = toNumber(row.MaxSpeed)
      const deviation = toNumber(row.FanAlert)
      const status = row.FanStatus || (deviation > 0 ? 'Alert' : 'OK')
      const percentBelow = minSpeed > 0 && fanSpeed > 0 ? Math.max(0, minSpeed - fanSpeed) / Math.max(1, minSpeed) : 0
      const severity =
        status === 'Alert' && (percentBelow >= 0.5 || fanSpeed <= 0)
          ? 'critical'
          : status === 'Alert'
            ? 'warning'
            : 'info'
      return {
        node,
        sensor,
        fanSpeed,
        minSpeed,
        maxSpeed,
        deviation,
        status,
        percentBelow,
        severity,
      }
    })
    .filter(item => item.status === 'Alert')
    .sort((a, b) => (b.percentBelow - a.percentBelow) || (b.deviation - a.deviation))
    .slice(0, 3)
    .map(item => ({
      title: `${item.node} - Fan ${item.sensor}`,
      subtitle: `Measured ${item.fanSpeed ? `${item.fanSpeed.toFixed(0)} RPM` : 'unknown'} (Min ${item.minSpeed ? item.minSpeed.toFixed(0) : 'N/A'})`,
      description: item.severity === 'critical'
        ? 'Fan speed is far below the chassis minimum; check airflow paths and replace the fan module if alerts persist.'
        : 'Fan speed dipped under the recommended minimum; inspect filters for dust and confirm the fan tray is operational.',
      severity: item.severity,
      reference: 'doc/ibdiagnet_manual_summary.md: Chassis fan alerts',
      actions: [
        'Inspect the switch fan tray and remove dust or blockages',
        'Schedule replacement of the affected fan if the alert repeats after cleaning'
      ],
    }))
}

const buildLatencyInsights = (rows = []) => {
  const safeRows = ensureArray(rows)
  return safeRows
    .map(row => {
      const ratio = toNumber(row.RttP99OverMedian)
      const upper = toNumber(row.RttUpperBucketRatio) * 100
      return {
        title: `${row['Node Name'] || row.NodeName || row.NodeGUID || 'Node'} - Port ${row.PortNumber || row['Port Number'] || 'N/A'}`,
        median: toNumber(row.RttMedianUs),
        p99: toNumber(row.RttP99Us),
        ratio,
        upper,
      }
    })
    .filter(item => item.ratio >= 3 || item.upper >= 20)
    .sort((a, b) => b.ratio - a.ratio)
    .slice(0, 3)
    .map(item => ({
      ...item,
      severity: item.ratio >= 5 || item.upper >= 30 ? 'critical' : 'warning',
      subtitle: `Median ${item.median.toFixed(2)}µs | P99 ${item.p99.toFixed(2)}µs`,
      description:
        item.ratio >= 5
          ? `P99 latency is ${item.ratio.toFixed(1)}x the median, indicating heavy tail RTT.`
          : `Upper histogram buckets account for ${item.upper.toFixed(1)}% of samples.`,
      reference: 'doc/ibdiagnet_manual_summary.md §2.3',
      actions: [
        'Inspect congested flows on this path and rebalance routes',
        'Validate adaptive routing configuration and queue depths',
      ],
    }))
}

function InsightCard({ title, subtitle, description, actions = [], severity = 'info', reference }) {
  return (
    <div className={`insight-card ${severity}`}>
      <h4>{title}</h4>
      {subtitle && <p className="insight-card-subtitle">{subtitle}</p>}
      {description && <p className="insight-card-text">{description}</p>}
      {actions.length > 0 && (
        <ul className="insight-card-list">
          {actions.slice(0, 2).map((action, idx) => (
            <li key={idx}>{action}</li>
          ))}
        </ul>
      )}
      {reference && <p className="insight-card-reference">Reference: {reference}</p>}
    </div>
  )
}

const resolveTabMeta = (key) => TAB_LOOKUP[key] || { label: key, icon: Activity }

const summarizeCableHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let critical = 0
  let warning = 0

  safeRows.forEach(row => {
    const temp = toNumber(row['Temperature (c)'] ?? row.Temperature)
    const hasOpticalAlarm = [
      'TX Bias Alarm and Warning',
      'TX Power Alarm and Warning',
      'RX Power Alarm and Warning',
      'Latched Voltage Alarm and Warning'
    ].some(key => hasAlarmFlag(row[key]))
    const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
    const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()

    const severity = temp >= 80 || hasOpticalAlarm
      ? 'critical'
      : temp >= 70 || (complianceStatus && complianceStatus !== 'ok') || (speedStatus && speedStatus !== 'ok')
        ? 'warning'
        : 'info'

    if (severity === 'critical') critical++
    else if (severity === 'warning') warning++
  })

  return {
    total: safeRows.length,
    critical,
    warning,
    healthy: Math.max(0, safeRows.length - critical - warning),
    severity: critical > 0 ? 'critical' : warning > 0 ? 'warning' : 'info',
  }
}

const summarizeCongestionHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let critical = 0
  let warning = 0

  safeRows.forEach(row => {
    const ratio = toNumber(row.WaitRatioPct)
    const waitSeconds = toNumber(row.WaitSeconds)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const level = String(row.CongestionLevel || '').toLowerCase()
    const fecnCount = toNumber(row.FECNCount)
    const becnCount = toNumber(row.BECNCount)

    const isCritical = ratio >= 5 || congestionPct >= 5 || level === 'critical'
    const isWarning =
      isCritical ? false : (
        ratio >= 1 ||
        congestionPct >= 1 ||
        waitSeconds > 0 ||
        level === 'warning' ||
        fecnCount > 0 ||
        becnCount > 0
      )

    if (isCritical) critical++
    else if (isWarning) warning++
  })

  return {
    total: safeRows.length,
    critical,
    warning,
    severity: critical > 0 ? 'critical' : warning > 0 ? 'warning' : 'info',
  }
}

const combineBerRows = (berData = [], berAdvancedData = []) => {
  const allRows = [...ensureArray(berData).map(row => ({ ...row, source: 'basic' }))]

  ensureArray(berAdvancedData).forEach(row => {
    const idx = allRows.findIndex(
      item => item.NodeGUID === row.NodeGUID && item.PortNumber === row.PortNumber
    )
    if (idx === -1) {
      allRows.push({ ...row, source: 'advanced' })
    } else {
      allRows[idx] = { ...allRows[idx], ...row, source: 'merged' }
    }
  })

  return allRows
}

const summarizeBerHealth = (berData = [], berAdvancedData = []) => {
  const rows = combineBerRows(berData, berAdvancedData)
  const critical = []
  const warning = []
  const noThreshold = []

  rows.forEach(row => {
    const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
    const eventName = String(row.EventName || row.Issues || '').toLowerCase()
    const normalized = {
      nodeName: row['Node Name'] || row.NodeName || 'Unknown',
      nodeGuid: row.NodeGUID || row['Node GUID'] || '',
      portNumber: row.PortNumber || row['Port Number'] || 'N/A',
      symbolBer: row.SymbolBER || row['Symbol BER'] || row.EffectiveBER || row.RawBER || 'N/A',
      effectiveBer: row.EffectiveBER || row['Effective BER'] || 'N/A',
      rawBer: row.RawBER || row['Raw BER'] || 'N/A',
      log10Value: toNumber(row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10),
      severity: severity || 'info',
    }

    if (severity === 'critical') critical.push(normalized)
    else if (severity === 'warning') warning.push(normalized)
    else if (eventName.includes('no_threshold')) noThreshold.push(normalized)
  })

  critical.sort((a, b) => b.log10Value - a.log10Value)
  warning.sort((a, b) => b.log10Value - a.log10Value)

  return {
    total: rows.length,
    criticalCount: critical.length,
    warningCount: warning.length,
    noThresholdCount: noThreshold.length,
    topCritical: critical.slice(0, 4),
    topWarning: warning.slice(0, 4),
    severity: critical.length > 0 ? 'critical' : warning.length > 0 ? 'warning' : 'info',
  }
}

const evaluateFirmwareHealth = (rows = [], firmwareWarnings = [], pciWarnings = []) => {
  const safeRows = ensureArray(rows)
  let outdatedFwCount = 0
  let psidIssueCount = 0
  const fwVersions = new Set()

  safeRows.forEach(row => {
    const fwCompliant = row.FW_Compliant
    const psidCompliant = row.PSID_Compliant
    const fwVersion = row.FW_Version || row.FirmwareVersion

    if (fwVersion) fwVersions.add(fwVersion)

    if (fwCompliant === false || fwCompliant === 'false' || fwCompliant === 'False') {
      outdatedFwCount++
    }
    if (psidCompliant === false || psidCompliant === 'false' || psidCompliant === 'False') {
      psidIssueCount++
    }
  })

  const problems = []

  if (outdatedFwCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${outdatedFwCount} 个设备固件版本过旧，建议升级`,
      kbType: 'HCA_FIRMWARE_OUTDATED'
    })
  }
  if (psidIssueCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${psidIssueCount} 个设备PSID不在支持列表中`,
      kbType: 'HCA_PSID_UNSUPPORTED'
    })
  }
  if (fwVersions.size > 3) {
    problems.push({
      severity: 'info',
      summary: `检测到 ${fwVersions.size} 个不同的固件版本，建议统一`,
      kbType: 'HCA_FIRMWARE_MIXED_VERSIONS'
    })
  }
  if (firmwareWarnings.length > 0) {
    problems.push({
      severity: 'warning',
      summary: `${firmwareWarnings.length} 个节点固件版本不一致 (来自ibdiagnet警告)`,
      kbType: 'HCA_FIRMWARE_MIXED_VERSIONS'
    })
  }
  if (pciWarnings.length > 0) {
    problems.push({
      severity: 'critical',
      summary: `${pciWarnings.length} 个端口PCI速度降级 (如Gen4→Gen3)，影响性能`,
      kbType: 'PCI_DEGRADATION'
    })
  }

  return {
    problems,
    stats: {
      total: safeRows.length,
      outdatedFwCount,
      psidIssueCount,
      firmwareWarningCount: firmwareWarnings.length,
      pciWarningCount: pciWarnings.length,
      uniqueFwVersions: fwVersions.size,
      severity: pciWarnings.length > 0 || outdatedFwCount > 0
        ? 'critical'
        : (psidIssueCount > 0 || fwVersions.size > 3 || firmwareWarnings.length > 0 ? 'warning' : 'info'),
    }
  }
}

const evaluateLatencyHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let highP99Count = 0
  let upperBucketCount = 0
  let jitterCount = 0

  safeRows.forEach(row => {
    const p99OverMedian = toNumber(row.RttP99OverMedian)
    const upperRatio = toNumber(row.RttUpperBucketRatio)
    const minRtt = toNumber(row.RttMinUs)
    const maxRtt = toNumber(row.RttMaxUs)

    if (p99OverMedian >= 3) highP99Count++
    if (upperRatio >= 0.1) upperBucketCount++
    if (minRtt > 0 && maxRtt > minRtt * 10) jitterCount++
  })

  const problems = []
  if (highP99Count > 0) {
    problems.push({
      severity: highP99Count > 5 ? 'critical' : 'warning',
      summary: `${highP99Count} 个端口P99延迟异常偏高 (>3倍中位数)`,
      kbType: 'HISTOGRAM_HIGH_LATENCY'
    })
  }
  if (upperBucketCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${upperBucketCount} 个端口高延迟桶占比过高 (>10%)`,
      kbType: 'HISTOGRAM_UPPER_BUCKET'
    })
  }
  if (jitterCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${jitterCount} 个端口延迟抖动过大`,
      kbType: 'HISTOGRAM_JITTER'
    })
  }

  return {
    problems,
    stats: {
      total: safeRows.length,
      highP99Count,
      upperBucketCount,
      jitterCount,
      severity: highP99Count > 0 ? 'critical' : (upperBucketCount > 0 || jitterCount > 0 ? 'warning' : 'info'),
    }
  }
}

const evaluateFanHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let lowSpeedCount = 0
  let highSpeedCount = 0
  let alertCount = 0

  safeRows.forEach(row => {
    const fanSpeed = toNumber(row.FanSpeed)
    const minSpeed = toNumber(row.MinSpeed)
    const maxSpeed = toNumber(row.MaxSpeed)
    const status = String(row.FanStatus || '').toLowerCase()

    if (status === 'alert') alertCount++
    if (minSpeed > 0 && fanSpeed < minSpeed) lowSpeedCount++
    if (maxSpeed > 0 && fanSpeed > maxSpeed * 0.9) highSpeedCount++
  })

  const problems = []
  if (lowSpeedCount > 0 || alertCount > 0) {
    problems.push({
      severity: 'critical',
      summary: `${Math.max(lowSpeedCount, alertCount)} 个风扇转速过低或告警，可能导致设备过热`,
      kbType: 'FAN_SPEED_LOW'
    })
  }
  if (highSpeedCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${highSpeedCount} 个风扇长时间高速运转，散热系统压力大`,
      kbType: 'FAN_SPEED_HIGH'
    })
  }

  return {
    problems,
    stats: {
      total: safeRows.length,
      lowSpeedCount,
      highSpeedCount,
      alertCount,
      severity: lowSpeedCount > 0 || alertCount > 0 ? 'critical' : (highSpeedCount > 0 ? 'warning' : 'info'),
    }
  }
}

const evaluateTemperatureHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let criticalCount = 0
  let warningCount = 0

  safeRows.forEach(row => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical') criticalCount++
    else if (severity === 'warning') warningCount++
  })

  const problems = []
  if (criticalCount > 0) {
    problems.push({
      severity: 'critical',
      summary: `${criticalCount} 个传感器温度严重过高，可能导致设备损坏`,
      kbType: 'CABLE_HIGH_TEMPERATURE'
    })
  }
  if (warningCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${warningCount} 个传感器温度偏高，建议检查散热`,
      kbType: 'CABLE_HIGH_TEMPERATURE'
    })
  }

  return {
    problems,
    stats: {
      total: safeRows.length,
      criticalCount,
      warningCount,
      severity: criticalCount > 0 ? 'critical' : (warningCount > 0 ? 'warning' : 'info'),
    }
  }
}

const evaluatePowerHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let psuCriticalCount = 0
  let psuWarningCount = 0
  let notPresentCount = 0

  safeRows.forEach(row => {
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical') psuCriticalCount++
    else if (severity === 'warning') psuWarningCount++
    if (row.IsPresent === false) notPresentCount++
  })

  const problems = []
  if (psuCriticalCount > 0) {
    problems.push({
      severity: 'critical',
      summary: `${psuCriticalCount} 个电源有严重故障，可能影响设备运行`,
      kbType: 'FAN_SPEED_LOW'
    })
  }
  if (psuWarningCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${psuWarningCount} 个电源有告警状态`,
      kbType: 'FAN_SPEED_LOW'
    })
  }
  if (notPresentCount > 0) {
    problems.push({
      severity: 'info',
      summary: `${notPresentCount} 个电源槽位未安装模块`,
      kbType: 'FAN_SPEED_LOW'
    })
  }

  return {
    problems,
    stats: {
      total: safeRows.length,
      psuCriticalCount,
      psuWarningCount,
      notPresentCount,
      severity: psuCriticalCount > 0 ? 'critical' : (psuWarningCount > 0 ? 'warning' : 'info'),
    }
  }
}

const evaluateRoutingHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let rnErrorCount = 0
  let frErrorCount = 0
  let hbfFallbackCount = 0

  safeRows.forEach(row => {
    if (toNumber(row.RNErrors) > 0) rnErrorCount++
    if (toNumber(row.FRErrors) > 0) frErrorCount++
    if (toNumber(row.HBFFallbackLocal) > 0 || toNumber(row.HBFFallbackRemote) > 0) {
      hbfFallbackCount++
    }
  })

  const problems = []
  if (frErrorCount > 0) {
    problems.push({
      severity: 'critical',
      summary: `${frErrorCount} 个端口有快速恢复错误，表明链路存在间歇性问题`,
      kbType: 'XMIT_LINK_DOWN_COUNTER'
    })
  }
  if (rnErrorCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${rnErrorCount} 个端口有RN (Re-route Notification) 错误`,
      kbType: 'XMIT_FECN_BECN'
    })
  }
  if (hbfFallbackCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${hbfFallbackCount} 个端口触发HBF回退，自适应路由效率可能受影响`,
      kbType: 'XMIT_MODERATE_CONGESTION'
    })
  }

  return {
    problems,
    stats: {
      total: safeRows.length,
      rnErrorCount,
      frErrorCount,
      hbfFallbackCount,
      severity: frErrorCount > 0 ? 'critical' : (rnErrorCount > 0 || hbfFallbackCount > 0 ? 'warning' : 'info'),
    }
  }
}

const evaluatePortHealth = (rows = []) => {
  const safeRows = ensureArray(rows)
  let icrcErrorCount = 0
  let parityErrorCount = 0
  let unhealthyCount = 0
   let linkDownPortCount = 0
   let linkDownEvents = 0
   let linkRecoveryPortCount = 0
   let linkRecoveryEvents = 0

  safeRows.forEach(row => {
    if (toNumber(row.RxICRCErrors) > 0) icrcErrorCount++
    if (toNumber(row.TxParityErrors) > 0) parityErrorCount++
    if (toNumber(row.UnhealthyReason) > 0) unhealthyCount++
    const downEvents = toNumber(
      row.LinkDownEvents ?? row.LinkDownedCounter ?? row.LinkDownedCounterExt ?? row.link_down_events
    )
    if (downEvents > 0) {
      linkDownPortCount++
      linkDownEvents += downEvents
    }
    const recoveryEvents = toNumber(
      row.LinkRecoveryEvents ?? row.LinkErrorRecoveryCounter ?? row.LinkErrorRecoveryCounterExt ?? row.link_recovery_events
    )
    if (recoveryEvents > 0) {
      linkRecoveryPortCount++
      linkRecoveryEvents += recoveryEvents
    }
  })

  const problems = []
  if (linkDownPortCount > 0) {
    problems.push({
      severity: 'critical',
      summary: `${linkDownPortCount} 个端口出现 LinkDown (共 ${linkDownEvents} 次)`,
      kbType: 'XMIT_LINK_DOWN_COUNTER',
    })
  }
  if (linkRecoveryPortCount > 0) {
    problems.push({
      severity: linkDownPortCount > 0 ? 'critical' : 'warning',
      summary: `${linkRecoveryPortCount} 个端口发生链路恢复事件 (共 ${linkRecoveryEvents} 次)`,
      kbType: 'XMIT_LINK_RECOVERY',
    })
  }
  if (parityErrorCount > 0) {
    problems.push({
      severity: 'critical',
      summary: `${parityErrorCount} 个端口有奇偶校验错误，可能存在硬件故障`,
      kbType: 'BER_CRITICAL'
    })
  }
  if (unhealthyCount > 0) {
    problems.push({
      severity: 'critical',
      summary: `${unhealthyCount} 个端口被标记为不健康状态`,
      kbType: 'XMIT_LINK_DOWN_COUNTER'
    })
  }
  if (icrcErrorCount > 0) {
    problems.push({
      severity: 'warning',
      summary: `${icrcErrorCount} 个端口有ICRC错误，数据完整性受影响`,
      kbType: 'BER_WARNING'
    })
  }

  return {
    problems,
    stats: {
      total: safeRows.length,
      icrcErrorCount,
      parityErrorCount,
      unhealthyCount,
      linkDownPortCount,
      linkDownEvents,
      linkRecoveryPortCount,
      linkRecoveryEvents,
      severity:
        parityErrorCount > 0 ||
        unhealthyCount > 0 ||
        linkDownPortCount > 0
          ? 'critical'
          : (icrcErrorCount > 0 || linkRecoveryPortCount > 0 ? 'warning' : 'info'),
    }
  }
}

const summarizeN2NSecurity = (summary = {}, rows = []) => {
  const safeSummary = summary || {}
  const totalNodes = safeSummary.total_nodes ?? ensureArray(rows).length
  const coveragePct = safeSummary.n2n_coverage_pct ?? 0
  const nodesWithN2N = safeSummary.nodes_with_n2n_enabled ?? 0
  const nodesWithKeys = safeSummary.nodes_with_keys ?? 0
  const violations = safeSummary.security_violations ?? 0

  return {
    totalNodes,
    coveragePct,
    nodesWithN2N,
    nodesWithKeys,
    violations,
    severity: violations > 0
      ? 'critical'
      : (coveragePct && coveragePct < 80 ? 'warning' : 'info'),
  }
}
// Health Score Component
function HealthScore({ health }) {
  if (!health) return null

  const getScoreColor = (score) => {
    if (score >= 80) return '#22c55e'  // green
    if (score >= 60) return '#eab308'  // yellow
    return '#ef4444'  // red
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'Healthy': return <CheckCircle size={24} color="#22c55e" />
      case 'Warning': return <AlertCircle size={24} color="#eab308" />
      case 'Critical': return <XCircle size={24} color="#ef4444" />
      default: return null
    }
  }

  return (
    <div className="health-score-container">
      <div className="health-score-main">
        <div className="health-score-circle" style={{ borderColor: getScoreColor(health.score) }}>
          <span className="health-score-value" style={{ color: getScoreColor(health.score) }}>
            {health.score}
          </span>
          <span className="health-score-grade">{health.grade}</span>
        </div>
        <div className="health-score-info">
          <div className="health-status">
            {getStatusIcon(health.status)}
            <span>{health.status}</span>
          </div>
          <div className="health-stats">
            <span>{health.total_nodes} Nodes</span>
            <span>{health.total_ports} Ports</span>
          </div>
        </div>
      </div>

      <div className="health-summary">
        <div className="issue-badge critical">
          <XCircle size={14} />
          <span>{health.summary?.critical || 0} Critical</span>
        </div>
        <div className="issue-badge warning">
          <AlertCircle size={14} />
          <span>{health.summary?.warning || 0} Warning</span>
        </div>
        <div className="issue-badge info">
          <AlertCircle size={14} />
          <span>{health.summary?.info || 0} Info</span>
        </div>
      </div>

      {health.category_scores && (
        <div className="category-scores">
          {Object.entries(health.category_scores).map(([category, score]) => (
            <div key={category} className="category-score-item">
              <span className="category-name">{category}</span>
              <div className="category-bar">
                <div
                  className="category-bar-fill"
                  style={{
                    width: `${score}%`,
                    backgroundColor: getScoreColor(score)
                  }}
                />
              </div>
              <span className="category-value">{score}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Issues List Component
function IssuesList({ issues }) {
  const [expandedCategories, setExpandedCategories] = useState({})
  const [expandedIssues, setExpandedIssues] = useState({})

  if (!issues || issues.length === 0) {
    return <p className="no-issues">No issues detected</p>
  }

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return '#ef4444'
      case 'warning': return '#eab308'
      case 'info': return '#3b82f6'
      default: return '#6b7280'
    }
  }

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }))
  }

  const toggleIssue = (issueKey) => {
    setExpandedIssues(prev => ({
      ...prev,
      [issueKey]: !prev[issueKey]
    }))
  }

  // Group issues by category
  const groupedIssues = issues.reduce((acc, issue) => {
    if (!acc[issue.category]) acc[issue.category] = []
    acc[issue.category].push(issue)
    return acc
  }, {})

  return (
    <div className="issues-list">
      {Object.entries(groupedIssues).map(([category, categoryIssues]) => {
        const isExpanded = expandedCategories[category]
        const displayIssues = isExpanded ? categoryIssues : categoryIssues.slice(0, 5)

        return (
          <div key={category} className="issue-category">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 className="issue-category-title">
                {category.toUpperCase()} ({categoryIssues.length})
              </h4>
              {categoryIssues.length > 5 && (
                <button
                  onClick={() => toggleCategory(category)}
                  style={{
                    padding: '4px 12px',
                    fontSize: '0.85rem',
                    background: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '4px',
                    color: '#94a3b8',
                    cursor: 'pointer'
                  }}
                >
                  {isExpanded ? 'Show Less' : `Show All (${categoryIssues.length})`}
                </button>
              )}
            </div>

            {displayIssues.map((issue, idx) => {
              const issueKey = `${category}-${idx}`
              const isIssueExpanded = expandedIssues[issueKey]

              return (
                <div key={idx} className="issue-item" style={{ borderLeftColor: getSeverityColor(issue.severity) }}>
                  <div className="issue-header">
                    <span className="issue-severity" style={{ color: getSeverityColor(issue.severity) }}>
                      {issue.severity.toUpperCase()}
                    </span>
                    <span className="issue-description">{issue.description}</span>
                  </div>
                  <div className="issue-details">
                    <span>Node: {issue.node_guid ? String(issue.node_guid).slice(0, 16) + '...' : 'N/A'}</span>
                    <span>Port: {issue.port_number || 'N/A'}</span>
                    {issue.weight && <span>Weight: {Number(issue.weight).toFixed(2)}</span>}
                  </div>

                  {issue.details?.kb && (
                    <>
                      <button
                        onClick={() => toggleIssue(issueKey)}
                        style={{
                          marginTop: '8px',
                          padding: '4px 8px',
                          fontSize: '0.8rem',
                          background: 'transparent',
                          border: '1px solid #334155',
                          borderRadius: '4px',
                          color: '#3b82f6',
                          cursor: 'pointer'
                        }}
                      >
                        {isIssueExpanded ? '▼ Hide Details' : '▶ Show Details'}
                      </button>

                      {isIssueExpanded && (
                        <div className="issue-knowledge" style={{ marginTop: '12px' }}>
                          <p className="issue-knowledge-title">{issue.details.kb.title}</p>
                          <p className="issue-knowledge-text">{issue.details.kb.why_it_matters}</p>
                          {issue.details.kb.likely_causes?.length > 0 && (
                            <div className="issue-knowledge-section">
                              <strong>Possible causes:</strong>
                              <ul>
                                {issue.details.kb.likely_causes.map((cause, idx2) => (
                                  <li key={idx2}>{cause}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {issue.details.kb.recommended_actions?.length > 0 && (
                            <div className="issue-knowledge-section">
                              <strong>Recommended actions:</strong>
                              <ul>
                                {issue.details.kb.recommended_actions.map((action, idx3) => (
                                  <li key={idx3}>{action}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {issue.details.kb.reference && (
                            <p className="issue-knowledge-reference">
                              <strong>Reference:</strong> {issue.details.kb.reference}
                            </p>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

// PaginatedTable component - moved outside to prevent re-creation on every render
function PaginatedTable({ rows, totalRows, emptyDebug }) {
  const data = ensureArray(rows)
  const [page, setPage] = useState(1)

  useEffect(() => {
    setPage(1)
  }, [rows])

  if (!data.length) {
    if (emptyDebug?.stderr || emptyDebug?.stdout) {
      return (
        <div>
          <p>No structured data available.</p>
          {emptyDebug.stderr && (
            <div style={{ marginTop: '20px' }}>
              <h4>Debug Error Log:</h4>
              <pre style={{ color: 'red' }}>{emptyDebug.stderr}</pre>
            </div>
          )}
          {emptyDebug.stdout && (
            <div style={{ marginTop: '20px' }}>
              <h4>Debug Output Log:</h4>
              <pre>{emptyDebug.stdout}</pre>
            </div>
          )}
        </div>
      )
    }
    return <p>No data available.</p>
  }

  const columns = Object.keys(data[0] || {})
  if (columns.length === 0) {
    return <p>No structured columns available.</p>
  }

  const totalPreviewRows = data.length
  const pageSize = TABLE_PAGE_SIZE
  const totalPages = Math.max(1, Math.ceil(totalPreviewRows / pageSize))
  const currentPage = Math.min(page, totalPages)
  const startIndex = (currentPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, totalPreviewRows)
  const displayRows = data.slice(startIndex, endIndex)
  const totalRecords = Number.isFinite(totalRows) && totalRows > 0 ? totalRows : totalPreviewRows
  const previewTrimmed = totalRecords > totalPreviewRows

  const infoParts = [`Showing rows ${startIndex + 1}-${endIndex} of ${totalRecords} rows.`]
  if (previewTrimmed) {
    infoParts.push(`Only ${totalPreviewRows} rows are available in this preview.`)
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            {columns.map(col => <th key={col}>{col}</th>)}
          </tr>
        </thead>
        <tbody>
          {displayRows.map((row, i) => (
            <tr key={`${currentPage}-${i}`}>
              {columns.map(col => (
                <td key={col}>
                  {typeof row[col] === 'object' ? JSON.stringify(row[col]) : row[col]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            style={{ padding: '6px 12px', borderRadius: '4px', border: '1px solid #1f2937', background: '#0f172a', color: '#e2e8f0', cursor: 'pointer' }}
            disabled={currentPage === 1}
            onClick={() => setPage(Math.max(1, currentPage - 1))}
          >
            Previous
          </button>
          <button
            style={{ padding: '6px 12px', borderRadius: '4px', border: '1px solid #1f2937', background: '#0f172a', color: '#e2e8f0', cursor: 'pointer' }}
            disabled={currentPage === totalPages}
            onClick={() => setPage(Math.min(totalPages, currentPage + 1))}
          >
            Next
          </button>
        </div>
        <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
          Page {currentPage} / {totalPages}
        </span>
      </div>
      <p style={{ marginTop: '10px', fontSize: '0.85rem', color: '#94a3b8' }}>
        {infoParts.join(' ')} Backend previews include anomalies only. Download the uploaded ibdiagnet archive for the complete dataset.
      </p>
    </div>
  )
}

function App() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [uploadProgress, setUploadProgress] = useState(0)

  const validateFile = (file, allowedExtensions, maxSize = MAX_FILE_SIZE) => {
    // Check file size
    if (file.size > maxSize) {
      throw new Error(`File too large. Maximum size is ${maxSize / (1024 * 1024)}MB`)
    }

    // Check file extension
    const fileName = file.name.toLowerCase()
    const isValid = allowedExtensions.some(ext => fileName.endsWith(ext))

    if (!isValid) {
      throw new Error(`Invalid file type. Allowed: ${allowedExtensions.join(', ')}`)
    }

    return true
  }

  const formatError = (err) => {
    // Handle axios errors with response
    if (err.response) {
      if (err.response.status === 413) {
        return `File too large. Maximum size is ${FILE_SIZE_MB}MB`
      }
      if (err.response.status === 400) {
        return err.response.data?.detail || 'Invalid file format'
      }
      if (err.response.status === 500) {
        return `Server error: ${err.response.data?.detail || 'Analysis failed'}`
      }
      // Generic response error
      return err.response.data?.detail || `Server error (${err.response.status})`
    }

    // Handle axios errors with request but no response
    if (err.request) {
      return 'No response from server. Please check if the backend is running'
    }

    // Handle specific error codes
    if (err.code === 'ECONNABORTED') {
      return 'Request timeout. File may be too large or server is busy'
    }
    if (err.code === 'ERR_NETWORK') {
      return 'Network error. Please check if the backend server is running'
    }

    // Fallback to error message
    return err.message || 'Unknown error occurred'
  }

  const handleIbdiagnetUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setLoading(true)
    setError(null)
    setResult(null)
    setActiveTab('overview')
    setUploadProgress(0)

    try {
      // Validate file before upload
      validateFile(file, ['.zip', '.tar.gz', '.tgz'])

      const formData = new FormData()
      formData.append('file', file)

      const response = await axios.post(buildApiUrl('/upload/ibdiagnet'), formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 900000, // 15 minutes timeout (increased for large files)
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(percentCompleted)
        }
      })
      setResult({ type: 'ibdiagnet', data: response.data })
      setUploadProgress(100)
    } catch (err) {
      console.error('Upload error:', err)
      setError(formatError(err))
    } finally {
      setLoading(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const handleCsvUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setLoading(true)
    setError(null)
    setResult(null)
    setActiveTab('data')
    setUploadProgress(0)

    try {
      // Validate file before upload
      validateFile(file, ['.csv'])

      const formData = new FormData()
      formData.append('file', file)

      const response = await axios.post(buildApiUrl('/upload/ufm-csv'), formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 600000, // 10 minutes timeout (increased for large files)
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(percentCompleted)
        }
      })
      setResult({ type: 'csv', data: response.data })
      setUploadProgress(100)
    } catch (err) {
      console.error('Upload error:', err)
      setError(formatError(err))
    } finally {
      setLoading(false)
      // Reset file input
      event.target.value = ''
    }
  }

  const renderIbdiagnetContent = () => {
    const {
      data,
      cable_data,
      xmit_data,
      ber_data,
      hca_data,
      fan_data,
      histogram_data,
      temperature_data,
      power_data,
      switch_data,
      routing_data,
      port_health_data,
      links_data,
      qos_data,
      sm_info_data,
      port_hierarchy_data,
      mlnx_counters_data,
      pm_delta_data,
      vports_data,
      pkey_data,
      system_info_data,
      extended_port_info_data,
      ar_info_data,
      sharp_data,
      fec_mode_data,
      phy_diagnostics_data,
      neighbors_data,
      buffer_histogram_data,
      extended_node_info_data,
      extended_switch_info_data,
      power_sensors_data,
      routing_config_data,
      temp_alerts_data,
      credit_watchdog_data,
      pci_performance_data,
      ber_advanced_data,
      cable_enhanced_data,
      per_lane_performance_data,
      n2n_security_data,
      temperature_summary,
      power_summary,
      switch_summary,
      routing_summary,
      port_health_summary,
      links_summary,
      qos_summary,
      sm_info_summary,
      port_hierarchy_summary,
      mlnx_counters_summary,
      pm_delta_summary,
      vports_summary,
      pkey_summary,
      system_info_summary,
      extended_port_info_summary,
      ar_info_summary,
      sharp_summary,
      fec_mode_summary,
      phy_diagnostics_summary,
      neighbors_summary,
      buffer_histogram_summary,
      extended_node_info_summary,
      extended_switch_info_summary,
      power_sensors_summary,
      routing_config_summary,
      temp_alerts_summary,
      credit_watchdog_summary,
      pci_performance_summary,
      ber_advanced_summary,
      cable_enhanced_summary,
      per_lane_performance_summary,
      n2n_security_summary,
      warnings_by_category,
      warnings_summary,
      health,
      data_total_rows,
      cable_total_rows,
      xmit_total_rows,
      ber_total_rows,
      hca_total_rows,
      fan_total_rows,
      histogram_total_rows,
      temperature_total_rows,
      power_total_rows,
      switch_total_rows,
      routing_total_rows,
      port_health_total_rows,
      links_total_rows,
      qos_total_rows,
      sm_info_total_rows,
      port_hierarchy_total_rows,
      mlnx_counters_total_rows,
      pm_delta_total_rows,
      vports_total_rows,
      pkey_total_rows,
      system_info_total_rows,
      extended_port_info_total_rows,
      ar_info_total_rows,
      sharp_total_rows,
      fec_mode_total_rows,
      phy_diagnostics_total_rows,
      neighbors_total_rows,
      buffer_histogram_total_rows,
      extended_node_info_total_rows,
      extended_switch_info_total_rows,
      power_sensors_total_rows,
      routing_config_total_rows,
      temp_alerts_total_rows,
      credit_watchdog_total_rows,
      pci_performance_total_rows,
      ber_advanced_total_rows,
      cable_enhanced_total_rows,
      per_lane_performance_total_rows,
      n2n_security_total_rows,
    } = result.data

    // Extract warnings by category for merging into tabs
    const firmwareWarnings = warnings_by_category?.firmware || []
    const pciWarnings = warnings_by_category?.pci || []

    switch (activeTab) {
      case 'overview': {
        const actionPlan = buildActionPlan(health?.issues || [])
        const berSnapshot = summarizeBerHealth(ber_data, ber_advanced_data)
        const berTopList = berSnapshot.topCritical.length > 0 ? berSnapshot.topCritical : berSnapshot.topWarning
        const warningCategories = Object.entries(warnings_by_category || {})
          .map(([category, entries]) => {
            const list = ensureArray(entries)
            if (!list.length) return null
            const severity = list.some(item => String(item?.severity || item?.level || '').toLowerCase() === 'critical')
              ? 'critical'
              : 'warning'
            const samples = list.slice(0, 3).map(item => (
              item?.summary ||
              item?.message ||
              item?.description ||
              item?.code ||
              item?.title ||
              'IBDiagnet warning'
            ))
            return {
              category,
              count: list.length,
              severity,
              samples,
            }
          })
          .filter(Boolean)
          .sort((a, b) => b.count - a.count)

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>?? 故障汇总 (所有有问题的内容)</h2>
              <FaultSummary analysisData={result.data} />
            </div>

            <div className="card">
              <div className="card-header-row">
                <h2>Network Health Score</h2>
                <p className="card-subtitle">IBDiagnet 汇总得分</p>
              </div>
              <HealthScore health={health} />
            </div>

            <div className="card">
              <div className="card-header-row">
                <h2>健康检查看板</h2>
                <p className="card-subtitle">统一展示 AnalysisService 返回的检查项，点击卡片跳转标签</p>
              </div>
              <HealthCheckBoard
                payload={result.data}
                onSelectTab={setActiveTab}
                resolveTabMeta={resolveTabMeta}
              />
            </div>

            {warningCategories.length > 0 && (
              <div className="card">
                <div className="card-header-row">
                  <h2>IBDiagnet 警告分类</h2>
                  <p className="card-subtitle">来自 warnings_by_category 的结构化告警</p>
                </div>
                <div className="warning-category-grid">
                  {warningCategories.map(entry => (
                    <div
                      key={entry.category}
                      className={`warning-category-card warning-${entry.severity}`}
                    >
                      <div className="warning-category-header">
                        <strong>{entry.category}</strong>
                        <span className="warning-chip">{entry.count}</span>
                      </div>
                      <ul>
                        {entry.samples.map((sample, idx) => (
                          <li key={`${entry.category}-${idx}`}>{sample}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {berSnapshot.total > 0 && (
              <div className="card">
                <div className="card-header-row">
                  <h2>?? BER 快速概览</h2>
                  <button type="button" className="ghost-link" onClick={() => setActiveTab('ber')}>
                    查看 BER 标签
                  </button>
                </div>
                <div className="overview-stat-row">
                  <div className="overview-stat">
                    <span className="overview-stat-label">严重端口</span>
                    <span className="overview-stat-value">{berSnapshot.criticalCount}</span>
                  </div>
                  <div className="overview-stat">
                    <span className="overview-stat-label">警告端口</span>
                    <span className="overview-stat-value">{berSnapshot.warningCount}</span>
                  </div>
                  <div className="overview-stat">
                    <span className="overview-stat-label">总端口</span>
                    <span className="overview-stat-value">{berSnapshot.total}</span>
                  </div>
                </div>
                {berTopList.length > 0 && (
                  <ul className="overview-alert-list">
                    {berTopList.slice(0, 4).map((item, idx) => (
                      <li key={`${item.nodeGuid || item.nodeName}-${item.portNumber}-${idx}`}>
                        <div>
                          <strong>{item.nodeName}</strong> · Port {item.portNumber}
                        </div>
                        <div className="overview-alert-metadata">
                          <span>{item.symbolBer}</span>
                          {item.effectiveBer && item.effectiveBer !== 'N/A' && (
                            <span>Eff {item.effectiveBer}</span>
                          )}
                          {item.rawBer && item.rawBer !== 'N/A' && (
                            <span>Raw {item.rawBer}</span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div className="card">
              <h2>Detected Issues</h2>
              <IssuesList issues={health?.issues} />
            </div>
            <div className="card">
              <h2>Recommended Next Actions</h2>
              {actionPlan.length ? (
                <ul className="action-plan">
                  {actionPlan.slice(0, 4).map((item, idx) => (
                    <li key={`${item.text}-${idx}`}>
                      <span className={`action-plan-badge ${item.severity}`}>{idx + 1}</span>
                      <div>
                        <p>{item.text}</p>
                        <small>
                          {item.category?.toUpperCase() || 'INFO'} | {item.reference || 'NVIDIA Guide'}
                        </small>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No immediate remediation items detected in this run.</p>
              )}
            </div>
            <div className="card">
              <h2>Analysis Brief</h2>
              {Array.isArray(data) ? (
                <PaginatedTable
                  rows={data}
                  totalRows={data_total_rows}
                  emptyDebug={{ stdout: result.data?.debug_stdout, stderr: result.data?.debug_stderr }}
                />
              ) : (
                <pre>{JSON.stringify(data, null, 2)}</pre>
              )}
            </div>
          </div>
        )
      }
      case 'cable': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>📡 线缆与光模块健康分析</h2>
              <p>光模块温度、光功率、线缆规格完整分析</p>
              <CableAnalysis cableData={cable_data} />
            </div>
          </div>
        )
      }
      case 'xmit': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>🚦 拥塞与错误分析 (Xmit)</h2>
              <p>端口等待时间、FECN/BECN拥塞通知、链路稳定性完整分析</p>
              <CongestionAnalysis xmitData={xmit_data} />
            </div>
          </div>
        )
      }
      case 'ber': {
        const berProblems = ensureArray(ber_data).filter(row => {
          const severity = (row.SymbolBERSeverity || row.Severity || '').toLowerCase()
          return severity === 'critical' || severity === 'warning'
        })
        const berProblemCards = berProblems.map(row => {
          const severity = (row.SymbolBERSeverity || row.Severity || '').toLowerCase()
          const node = row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown'
          const port = row.PortNumber || row['Port Number'] || 'N/A'
          const raw = row['Raw BER'] || row.RawBER || row.rawBer || 'N/A'
          const effective = row['Effective BER'] || row.EffectiveBER || row.effectiveBer || 'N/A'
          const symbol = row['Symbol BER'] || row.SymbolBER || row.symbolBer || 'N/A'
          return {
            severity,
            summary: `${node} - 端口 ${port} BER 超过阈值`,
            kbType: severity === 'critical' ? 'BER_CRITICAL' : 'BER_WARNING',
            node,
            port,
            raw,
            effective,
            symbol,
          }
        })

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>📊 误码率 (BER) 健康分析</h2>
              <p>Symbol BER、Effective BER、FEC纠正活动完整分析</p>

              <ProblemSummary
                title="🚦 BER 问题摘要"
                problems={berProblemCards}
                totalChecked={ber_data?.length || 0}
                dataType="ber"
              />

              <BERAnalysis
                berData={ber_data}
                berAdvancedData={ber_advanced_data}
                perLaneData={per_lane_performance_data}
                berAdvancedSummary={ber_advanced_summary}
                showOnlyProblematic
              />
            </div>
          </div>
        )
      }
      case 'hca': {
        const { problems: hcaProblems, stats: hcaStats } = evaluateFirmwareHealth(
          hca_data,
          firmwareWarnings,
          pciWarnings
        )

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Device & Firmware Analysis</h2>
              <p>Firmware version inconsistencies and device anomalies.</p>

              <ProblemSummary
                title="固件分析"
                problems={hcaProblems}
                totalChecked={hcaStats.total}
                dataType="hca"
              />

              <PaginatedTable
                rows={hca_data}
                totalRows={hca_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'latency': {
        const latencyInsights = buildLatencyInsights(histogram_data || [])
        const { problems: latencyProblems, stats: latencyStats } = evaluateLatencyHealth(histogram_data)

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Latency Histogram</h2>
              <p>RTT distribution and heavy-tail detection from ibdiagnet histograms.</p>

              <ProblemSummary
                title="延迟分析"
                problems={latencyProblems}
                totalChecked={latencyStats.total}
                dataType="histogram"
              />

              {latencyInsights.length > 0 && (
                <div className="insight-grid">
                  {latencyInsights.map((insight, idx) => (
                    <InsightCard
                      key={`lat-${idx}`}
                      title={insight.title}
                      subtitle={insight.subtitle}
                      description={insight.description}
                      severity={insight.severity}
                      reference={insight.reference}
                      actions={insight.actions}
                    />
                  ))}
                </div>
              )}
              <PaginatedTable
                rows={histogram_data}
                totalRows={histogram_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'fan': {
        const fanInsights = buildFanInsights(fan_data || [])
        const { problems: fanProblems, stats: fanStats } = evaluateFanHealth(fan_data)

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Fan &amp; Chassis Health</h2>
              <p>Fan speed deviations based on FANS_SPEED/THRESHOLD tables.</p>

              <ProblemSummary
                title="风扇健康检查"
                problems={fanProblems}
                totalChecked={fanStats.total}
                dataType="fan"
              />

              {fanInsights.length > 0 && (
                <div className="insight-grid">
                  {fanInsights.map((insight, idx) => (
                    <InsightCard
                      key={`fan-${idx}`}
                      title={insight.title}
                      subtitle={insight.subtitle}
                      description={insight.description}
                      severity={insight.severity}
                      reference={insight.reference}
                      actions={insight.actions}
                    />
                  ))}
                </div>
              )}
              <PaginatedTable
                rows={fan_data}
                totalRows={fan_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'temperature': {
        const { problems: tempProblems, stats: tempStats } = evaluateTemperatureHealth(temperature_data)

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Temperature Sensors</h2>
              <p>Switch and device temperature monitoring from TEMPERATURE_SENSORS table.</p>

              <ProblemSummary
                title="温度监控"
                problems={tempProblems}
                totalChecked={tempStats.total}
                dataType="temperature"
              />

              {temperature_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Sensors:</strong> {temperature_summary.total_sensors || 0}</div>
                    <div><strong>Avg Temp:</strong> {temperature_summary.avg_temperature || 0}°C</div>
                    <div><strong>Max Temp:</strong> {temperature_summary.max_temperature || 0}°C</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={temperature_data}
                totalRows={temperature_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'power': {
        const { problems: powerProblems, stats: powerStats } = evaluatePowerHealth(power_data)

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Power Supplies</h2>
              <p>Power supply unit status and health from POWER_SUPPLIES table.</p>

              <ProblemSummary
                title="电源状态"
                problems={powerProblems}
                totalChecked={powerStats.total}
                dataType="power"
              />

              {power_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total PSUs:</strong> {power_summary.total_psus || 0}</div>
                    <div><strong>Present:</strong> {power_summary.present_count || 0}</div>
                    <div><strong>Total Power:</strong> {power_summary.total_power_consumption || 0}W</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={power_data}
                totalRows={power_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'switches': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Switch Information</h2>
              <p>Switch-level configuration and adaptive routing status.</p>

              {switch_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Switches:</strong> {switch_summary.total_switches || 0}</div>
                    <div><strong>AR Enabled:</strong> {switch_summary.ar_enabled_count || 0}</div>
                    <div><strong>FR Enabled:</strong> {switch_summary.fr_enabled_count || 0}</div>
                    <div><strong>HBF Enabled:</strong> {switch_summary.hbf_enabled_count || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={switch_data}
                totalRows={switch_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'routing': {
        const { problems: routingProblems, stats: routingStats } = evaluateRoutingHealth(routing_data)

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Adaptive Routing Analysis</h2>
              <p>RN counters, HBF statistics, and fast recovery status.</p>

              <ProblemSummary
                title="自适应路由分析"
                problems={routingProblems}
                totalChecked={routingStats.total}
                dataType="routing"
              />

              {routing_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Ports:</strong> {routing_summary.total_ports || 0}</div>
                    <div><strong>AR Traffic:</strong> {routing_summary.ports_with_ar_traffic || 0} ports</div>
                    <div><strong>HBF Traffic:</strong> {routing_summary.ports_with_hbf_traffic || 0} ports</div>
                    <div><strong>RN Errors:</strong> {routing_summary.total_rn_errors || 0}</div>
                    <div><strong>FR Errors:</strong> {routing_summary.total_fr_errors || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={routing_data}
                totalRows={routing_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'port_health': {
        const { problems: portHealthProblems, stats: portHealthStats } = evaluatePortHealth(port_health_data)

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Port Health Details</h2>
              <p>ICRC errors, parity errors, FEC mode, and unhealthy port analysis.</p>

              <ProblemSummary
                title="端口健康详情"
                problems={portHealthProblems}
                totalChecked={portHealthStats.total}
                dataType="port_health"
              />

              {port_health_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Ports:</strong> {port_health_summary.total_ports || 0}</div>
                    <div><strong>ICRC Errors:</strong> {port_health_summary.total_icrc_errors || 0}</div>
                    <div><strong>Parity Errors:</strong> {port_health_summary.total_parity_errors || 0}</div>
                    <div><strong>Unhealthy Ports:</strong> {port_health_summary.unhealthy_ports || 0}</div>
                    <div><strong>Link Down Events:</strong> {port_health_summary.total_link_down_events || 0}</div>
                    <div><strong>Link Recovery Events:</strong> {port_health_summary.total_link_recovery_events || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={port_health_data}
                totalRows={port_health_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'links': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Network Links</h2>
              <p>Node-to-node connectivity and link topology.</p>

              {links_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Links:</strong> {links_summary.total_links || 0}</div>
                    <div><strong>Unique Nodes:</strong> {links_summary.unique_nodes || 0}</div>
                    <div><strong>Avg Ports/Node:</strong> {links_summary.avg_ports_per_node || 0}</div>
                    <div><strong>Max Ports/Node:</strong> {links_summary.max_ports_per_node || 0}</div>
                    {links_summary.asymmetric_links > 0 && (
                      <div style={{ color: '#ef4444' }}><strong>Asymmetric Links:</strong> {links_summary.asymmetric_links}</div>
                    )}
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={links_data}
                totalRows={links_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'qos': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>QoS / VL Arbitration</h2>
              <p>Virtual Lane arbitration configuration and weight distribution analysis.</p>

              {qos_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Ports:</strong> {qos_summary.total_ports_analyzed || 0}</div>
                    <div><strong>Avg VLs/Port:</strong> {qos_summary.avg_vls_per_port || 0}</div>
                    <div><strong>Single VL Ports:</strong> {qos_summary.ports_with_single_vl || 0}</div>
                    <div><strong>High Priority Dominant:</strong> {qos_summary.ports_with_high_prio_dominant || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={qos_data}
                totalRows={qos_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'sm_info': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Subnet Manager</h2>
              <p>SM state, priority, and master/standby configuration.</p>

              {sm_info_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total SMs:</strong> {sm_info_summary.total_sms || 0}</div>
                    <div><strong>Master:</strong> {sm_info_summary.master_count || 0}</div>
                    <div><strong>Standby:</strong> {sm_info_summary.standby_count || 0}</div>
                    <div><strong>Redundancy:</strong> {sm_info_summary.has_redundancy ? 'Yes' : 'No'}</div>
                    {sm_info_summary.master_sm && (
                      <div><strong>Master Node:</strong> {sm_info_summary.master_sm.node_name}</div>
                    )}
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={sm_info_data}
                totalRows={sm_info_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'port_hierarchy': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Port Hierarchy</h2>
              <p>Network topology hierarchy and port tier/role information.</p>

              {port_hierarchy_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Ports:</strong> {port_hierarchy_summary.total_ports || 0}</div>
                    <div><strong>Unique Nodes:</strong> {port_hierarchy_summary.unique_nodes || 0}</div>
                    <div><strong>Planes:</strong> {port_hierarchy_summary.plane_count || 0}</div>
                    <div><strong>Multi-Plane:</strong> {port_hierarchy_summary.is_multi_plane ? 'Yes' : 'No'}</div>
                  </div>
                  {port_hierarchy_summary.role_distribution && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>Role Distribution:</strong>{' '}
                      {Object.entries(port_hierarchy_summary.role_distribution).map(([role, count]) => (
                        <span key={role} style={{ marginRight: '12px' }}>{role}: {count}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={port_hierarchy_data}
                totalRows={port_hierarchy_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'mlnx_counters': {
        // Analyze MLNX counters problems
        const mlnxProblems = []
        let rnrCriticalCount = 0
        let rnrWarningCount = 0
        let timeoutCount = 0
        let qpErrorCount = 0

        ensureArray(mlnx_counters_data).forEach(row => {
          const severity = String(row.Severity || '').toLowerCase()
          if (severity === 'critical') rnrCriticalCount++
          else if (severity === 'warning') rnrWarningCount++
          if (toNumber(row.Timeouts) > 0) timeoutCount++
          if (toNumber(row.TotalErrors) > 0) qpErrorCount++
        })

        if (rnrCriticalCount > 0) {
          mlnxProblems.push({
            severity: 'critical',
            summary: `${rnrCriticalCount} 个端口有严重的RNR/超时问题，可能导致性能下降`,
            kbType: 'XMIT_SEVERE_CONGESTION'
          })
        }
        if (rnrWarningCount > 0) {
          mlnxProblems.push({
            severity: 'warning',
            summary: `${rnrWarningCount} 个端口有RNR重试或超时警告`,
            kbType: 'XMIT_MODERATE_CONGESTION'
          })
        }
        if (qpErrorCount > 0) {
          mlnxProblems.push({
            severity: 'warning',
            summary: `${qpErrorCount} 个端口有QP(Queue Pair)错误`,
            kbType: 'BER_WARNING'
          })
        }

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Mellanox Counters (MLNX_CNTRS_INFO)</h2>
              <p>RNR retries, timeouts, and Queue Pair error analysis.</p>

              <ProblemSummary
                title="MLNX计数器分析"
                problems={mlnxProblems}
                totalChecked={ensureArray(mlnx_counters_data).length}
                dataType="mlnx_counters"
              />

              {mlnx_counters_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Ports Analyzed:</strong> {mlnx_counters_summary.total_ports_analyzed || 0}</div>
                    <div><strong>Ports with Activity:</strong> {mlnx_counters_summary.total_ports_with_activity || 0}</div>
                    <div><strong>RNR Retries:</strong> {mlnx_counters_summary.total_rnr_retries?.toLocaleString() || 0}</div>
                    <div><strong>Timeouts:</strong> {mlnx_counters_summary.total_timeouts?.toLocaleString() || 0}</div>
                    <div><strong>QP Errors:</strong> {mlnx_counters_summary.total_qp_errors || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={mlnx_counters_data}
                totalRows={mlnx_counters_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'pm_delta': {
        // Analyze PM Delta problems
        const pmDeltaProblems = []
        let fecCriticalCount = 0
        let fecWarningCount = 0
        let relayErrorCount = 0

        ensureArray(pm_delta_data).forEach(row => {
          const severity = String(row.Severity || '').toLowerCase()
          if (severity === 'critical') fecCriticalCount++
          else if (severity === 'warning') fecWarningCount++
          if (toNumber(row.RelayErrors) > 0) relayErrorCount++
        })

        if (fecCriticalCount > 0) {
          pmDeltaProblems.push({
            severity: 'critical',
            summary: `${fecCriticalCount} 个端口在诊断期间有FEC不可纠正块，信号严重问题`,
            kbType: 'BER_CRITICAL'
          })
        }
        if (fecWarningCount > 0) {
          pmDeltaProblems.push({
            severity: 'warning',
            summary: `${fecWarningCount} 个端口有高FEC纠正活动或其他警告`,
            kbType: 'BER_WARNING'
          })
        }
        if (relayErrorCount > 0) {
          pmDeltaProblems.push({
            severity: 'warning',
            summary: `${relayErrorCount} 个端口有交换机中继错误`,
            kbType: 'XMIT_FECN_BECN'
          })
        }

        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Performance Monitor Delta (PM_DELTA)</h2>
              <p>Real-time counter changes during ibdiagnet run: FEC activity, traffic, and active errors.</p>

              <ProblemSummary
                title="性能计数器增量分析"
                problems={pmDeltaProblems}
                totalChecked={ensureArray(pm_delta_data).length}
                dataType="pm_delta"
              />

              {pm_delta_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Ports Sampled:</strong> {pm_delta_summary.total_ports_sampled || 0}</div>
                    <div><strong>Ports with Activity:</strong> {pm_delta_summary.ports_with_activity || 0}</div>
                    <div><strong>Total TX:</strong> {pm_delta_summary.total_xmit_gb || 0} GB</div>
                    <div><strong>Total RX:</strong> {pm_delta_summary.total_rcv_gb || 0} GB</div>
                    <div><strong>FEC Corrected:</strong> {pm_delta_summary.total_fec_corrected?.toLocaleString() || 0}</div>
                    <div><strong>FEC Uncorrectable:</strong> {pm_delta_summary.total_fec_uncorrectable || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={pm_delta_data}
                totalRows={pm_delta_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'vports': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Virtual Ports (SR-IOV)</h2>
              <p>Virtual node and port analysis for SR-IOV virtualization deployments.</p>

              {vports_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total VNodes:</strong> {vports_summary.total_vnodes || 0}</div>
                    <div><strong>Total VPorts:</strong> {vports_summary.total_vports || 0}</div>
                    <div><strong>Physical Nodes w/ VNodes:</strong> {vports_summary.physical_nodes_with_vnodes || 0}</div>
                    <div><strong>Avg VNodes/Physical:</strong> {vports_summary.avg_vnodes_per_physical || 0}</div>
                    <div><strong>Max VNodes/Physical:</strong> {vports_summary.max_vnodes_per_physical || 0}</div>
                    <div><strong>Virtualization Enabled:</strong> {vports_summary.virtualization_enabled ? 'Yes' : 'No'}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={vports_data}
                totalRows={vports_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'pkey': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Partition Keys (PKEY)</h2>
              <p>Network isolation and security partitioning configuration.</p>

              {pkey_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total PKEY Entries:</strong> {pkey_summary.total_pkey_entries || 0}</div>
                    <div><strong>Unique Partitions:</strong> {pkey_summary.unique_partitions || 0}</div>
                    <div><strong>Unique Nodes:</strong> {pkey_summary.unique_nodes || 0}</div>
                    <div><strong>Multi-Partition Nodes:</strong> {pkey_summary.nodes_with_multiple_partitions || 0}</div>
                    <div><strong>Default Partition Nodes:</strong> {pkey_summary.default_partition_nodes || 0}</div>
                    <div><strong>Isolation Enabled:</strong> {pkey_summary.isolation_enabled ? 'Yes' : 'No'}</div>
                  </div>
                  {pkey_summary.partition_list && pkey_summary.partition_list.length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>Partitions:</strong> {pkey_summary.partition_list.slice(0, 10).join(', ')}
                      {pkey_summary.partition_list.length > 10 && ` ... and ${pkey_summary.partition_list.length - 10} more`}
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={pkey_data}
                totalRows={pkey_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'system_info': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>System Information</h2>
              <p>Hardware inventory, serial numbers, and ibdiagnet run metadata.</p>

              {system_info_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Devices:</strong> {system_info_summary.total_devices || 0}</div>
                    <div><strong>Unique Serials:</strong> {system_info_summary.unique_serials || 0}</div>
                    <div><strong>Product Types:</strong> {system_info_summary.product_types || 0}</div>
                    <div><strong>Revision Types:</strong> {system_info_summary.revision_types || 0}</div>
                  </div>
                  {system_info_summary.ibdiagnet_version && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>IBDiagnet Version:</strong> {system_info_summary.ibdiagnet_version}
                    </div>
                  )}
                  {system_info_summary.run_date && (
                    <div style={{ marginTop: '4px' }}>
                      <strong>Run Date:</strong> {system_info_summary.run_date}
                    </div>
                  )}
                  {system_info_summary.product_distribution && Object.keys(system_info_summary.product_distribution).length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>Product Distribution:</strong>
                      <div style={{ marginTop: '4px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                        {Object.entries(system_info_summary.product_distribution).slice(0, 5).map(([product, count]) => (
                          <span key={product} style={{ padding: '2px 8px', background: '#e2e8f0', borderRadius: '4px', fontSize: '0.85rem' }}>
                            {product}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={system_info_data}
                totalRows={system_info_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'extended_port_info': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Extended Port Info</h2>
              <p>Bandwidth utilization, unhealthy reasons, and FEC modes per speed.</p>

              {extended_port_info_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Ports:</strong> {extended_port_info_summary.total_ports || 0}</div>
                    <div><strong>Unhealthy Ports:</strong> <span style={{ color: extended_port_info_summary.unhealthy_ports > 0 ? '#dc2626' : '#22c55e' }}>{extended_port_info_summary.unhealthy_ports || 0}</span></div>
                    <div><strong>Avg BW Utilization:</strong> {extended_port_info_summary.avg_bw_utilization?.toFixed(1) || 0}%</div>
                    <div><strong>Max BW Utilization:</strong> {extended_port_info_summary.max_bw_utilization?.toFixed(1) || 0}%</div>
                  </div>
                  {extended_port_info_summary.unhealthy_reasons && Object.keys(extended_port_info_summary.unhealthy_reasons).length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>Unhealthy Reasons:</strong>
                      <div style={{ marginTop: '4px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {Object.entries(extended_port_info_summary.unhealthy_reasons).map(([reason, count]) => (
                          <span key={reason} style={{ padding: '2px 8px', background: '#fecaca', color: '#991b1b', borderRadius: '4px', fontSize: '0.85rem' }}>
                            {reason}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={extended_port_info_data}
                totalRows={extended_port_info_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'ar_info': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Adaptive Routing (AR)</h2>
              <p>AR, Fast Recovery (FR), and Hash-Based Forwarding (HBF) configuration.</p>

              {ar_info_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Switches:</strong> {ar_info_summary.total_switches || 0}</div>
                    <div><strong>AR Supported:</strong> {ar_info_summary.ar_supported || 0}</div>
                    <div><strong>FR Enabled:</strong> {ar_info_summary.fr_enabled || 0} / {ar_info_summary.fr_supported || 0}</div>
                    <div><strong>HBF Enabled:</strong> {ar_info_summary.hbf_enabled || 0} / {ar_info_summary.hbf_supported || 0}</div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>FR Coverage:</strong> <span style={{ color: ar_info_summary.fr_coverage_pct >= 80 ? '#22c55e' : '#eab308' }}>{ar_info_summary.fr_coverage_pct?.toFixed(1) || 0}%</span></div>
                    <div><strong>HBF Coverage:</strong> <span style={{ color: ar_info_summary.hbf_coverage_pct >= 80 ? '#22c55e' : '#eab308' }}>{ar_info_summary.hbf_coverage_pct?.toFixed(1) || 0}%</span></div>
                    <div><strong>PFRN Enabled:</strong> {ar_info_summary.pfrn_enabled || 0} / {ar_info_summary.pfrn_supported || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={ar_info_data}
                totalRows={ar_info_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'sharp': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>SHARP (Scalable Hierarchical Aggregation)</h2>
              <p>SHARP aggregation nodes for AI/ML collective operations.</p>

              {sharp_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>SHARP Nodes:</strong> {sharp_summary.total_sharp_nodes || 0}</div>
                    <div><strong>SHARP Enabled:</strong> {sharp_summary.sharp_enabled ? 'Yes' : 'No'}</div>
                    <div><strong>Total Tree Capacity:</strong> {sharp_summary.total_tree_capacity || 0}</div>
                    <div><strong>Total Jobs Capacity:</strong> {sharp_summary.total_jobs_capacity || 0}</div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Avg Tree Size:</strong> {sharp_summary.avg_tree_size || 0}</div>
                    <div><strong>Avg Jobs/Node:</strong> {sharp_summary.avg_jobs_per_node || 0}</div>
                    <div><strong>Max QPs/Node:</strong> {sharp_summary.max_qps_per_node || 0}</div>
                  </div>
                  {sharp_summary.data_types_supported && sharp_summary.data_types_supported.length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>Supported Data Types:</strong>
                      <div style={{ marginTop: '4px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {sharp_summary.data_types_supported.map(dtype => (
                          <span key={dtype} style={{ padding: '2px 8px', background: '#dbeafe', color: '#1e40af', borderRadius: '4px', fontSize: '0.85rem' }}>
                            {dtype}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={sharp_data}
                totalRows={sharp_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'fec_mode': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>FEC Mode Configuration</h2>
              <p>Forward Error Correction support and enablement per speed.</p>

              {fec_mode_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Ports:</strong> {fec_mode_summary.total_ports || 0}</div>
                    <div><strong>Ports without FEC:</strong> <span style={{ color: fec_mode_summary.ports_without_fec > 0 ? '#eab308' : '#22c55e' }}>{fec_mode_summary.ports_without_fec || 0}</span></div>
                    <div><strong>Ports with RS-FEC:</strong> {fec_mode_summary.ports_with_rs_fec || 0}</div>
                    <div><strong>Config Mismatches:</strong> <span style={{ color: fec_mode_summary.mismatch_count > 0 ? '#dc2626' : '#22c55e' }}>{fec_mode_summary.mismatch_count || 0}</span></div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>HDR Capable:</strong> {fec_mode_summary.hdr_capable_ports || 0}</div>
                    <div><strong>NDR Capable:</strong> {fec_mode_summary.ndr_capable_ports || 0}</div>
                  </div>
                  {fec_mode_summary.fec_active_distribution && Object.keys(fec_mode_summary.fec_active_distribution).length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>FEC Active Distribution:</strong>
                      <div style={{ marginTop: '4px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {Object.entries(fec_mode_summary.fec_active_distribution).slice(0, 5).map(([mode, count]) => (
                          <span key={mode} style={{ padding: '2px 8px', background: mode.includes('RS-FEC') ? '#dcfce7' : '#fef3c7', color: mode.includes('RS-FEC') ? '#166534' : '#92400e', borderRadius: '4px', fontSize: '0.85rem' }}>
                            {mode}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={fec_mode_data}
                totalRows={fec_mode_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'phy_diagnostics': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Physical Layer Diagnostics</h2>
              <p>PHY-level signal integrity and diagnostic data.</p>

              {phy_diagnostics_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Ports:</strong> {phy_diagnostics_summary.total_ports || 0}</div>
                    <div><strong>Diagnostic Fields:</strong> {phy_diagnostics_summary.total_diagnostic_fields || 0}</div>
                    <div><strong>Ports with Data:</strong> {phy_diagnostics_summary.ports_with_data || 0}</div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Avg Non-Zero Fields:</strong> {phy_diagnostics_summary.avg_non_zero_fields || 0}</div>
                    <div><strong>Max Non-Zero Fields:</strong> {phy_diagnostics_summary.max_non_zero_fields || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={phy_diagnostics_data}
                totalRows={phy_diagnostics_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'neighbors': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Neighbors Topology</h2>
              <p>Neighbor relationships and link properties for topology analysis.</p>

              {neighbors_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Neighbor Entries:</strong> {neighbors_summary.total_neighbor_entries || 0}</div>
                    <div><strong>Unique Nodes:</strong> {neighbors_summary.unique_nodes || 0}</div>
                    <div><strong>Avg Connections/Node:</strong> {neighbors_summary.avg_connections_per_node || 0}</div>
                    <div><strong>Max Connections:</strong> {neighbors_summary.max_connections_per_node || 0}</div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Speed Mismatches:</strong> <span style={{ color: neighbors_summary.mismatched_speeds > 0 ? '#dc2626' : '#22c55e' }}>{neighbors_summary.mismatched_speeds || 0}</span></div>
                    <div><strong>Width Mismatches:</strong> <span style={{ color: neighbors_summary.mismatched_widths > 0 ? '#dc2626' : '#22c55e' }}>{neighbors_summary.mismatched_widths || 0}</span></div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={neighbors_data}
                totalRows={neighbors_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'buffer_histogram': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Buffer Histograms</h2>
              <p>Buffer congestion analysis for bottleneck detection.</p>

              {buffer_histogram_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Entries:</strong> {buffer_histogram_summary.total_entries || 0}</div>
                    <div><strong>Total Samples:</strong> {buffer_histogram_summary.total_samples?.toLocaleString() || 0}</div>
                    <div><strong>High Utilization:</strong> <span style={{ color: buffer_histogram_summary.high_utilization_count > 0 ? '#eab308' : '#22c55e' }}>{buffer_histogram_summary.high_utilization_count || 0}</span></div>
                    <div><strong>Critical:</strong> <span style={{ color: buffer_histogram_summary.critical_utilization_count > 0 ? '#dc2626' : '#22c55e' }}>{buffer_histogram_summary.critical_utilization_count || 0}</span></div>
                  </div>
                  <div style={{ marginTop: '8px' }}>
                    <strong>Max Utilization:</strong> {buffer_histogram_summary.max_utilization_pct || 0}%
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={buffer_histogram_data}
                totalRows={buffer_histogram_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'extended_node_info': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Extended Node Information</h2>
              <p>Extended node attributes and SMP capabilities.</p>

              {extended_node_info_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Nodes:</strong> {extended_node_info_summary.total_nodes || 0}</div>
                    <div><strong>Total Ports:</strong> {extended_node_info_summary.total_ports || 0}</div>
                    <div><strong>Avg Ports/Node:</strong> {extended_node_info_summary.avg_ports_per_node || 0}</div>
                    <div><strong>SMP Entries:</strong> {extended_node_info_summary.smp_entries || 0}</div>
                  </div>
                  {extended_node_info_summary.node_type_distribution && Object.keys(extended_node_info_summary.node_type_distribution).length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <strong>Node Types:</strong>
                      <div style={{ marginTop: '4px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {Object.entries(extended_node_info_summary.node_type_distribution).map(([type, count]) => (
                          <span key={type} style={{ padding: '2px 8px', background: '#e2e8f0', borderRadius: '4px', fontSize: '0.85rem' }}>
                            {type}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={extended_node_info_data}
                totalRows={extended_node_info_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'extended_switch_info': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Extended Switch Information</h2>
              <p>Switch-specific capabilities and LFT/multicast capacity.</p>

              {extended_switch_info_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Switches:</strong> {extended_switch_info_summary.total_switches || 0}</div>
                    <div><strong>Enhanced Port0:</strong> {extended_switch_info_summary.enhanced_port0_count || 0}</div>
                    <div><strong>Multicast Enabled:</strong> {extended_switch_info_summary.multicast_enabled_count || 0}</div>
                    <div><strong>AR Capable:</strong> {extended_switch_info_summary.ar_capable_count || 0}</div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Multicast Cap:</strong> {extended_switch_info_summary.total_multicast_capacity?.toLocaleString() || 0}</div>
                    <div><strong>Filter Raw Enabled:</strong> {extended_switch_info_summary.filter_raw_enabled_count || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={extended_switch_info_data}
                totalRows={extended_switch_info_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'power_sensors': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Power Sensors</h2>
              <p>Individual power sensor readings for detailed power monitoring.</p>

              {power_sensors_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Sensors:</strong> {power_sensors_summary.total_sensors || 0}</div>
                    <div><strong>Unique Nodes:</strong> {power_sensors_summary.unique_nodes || 0}</div>
                    <div><strong>Total Power:</strong> {power_sensors_summary.total_power_w?.toFixed(1) || 0} W</div>
                    <div><strong>Max Sensor:</strong> {power_sensors_summary.max_sensor_power_mw?.toFixed(1) || 0} mW</div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Warnings:</strong> <span style={{ color: power_sensors_summary.warning_count > 0 ? '#eab308' : '#22c55e' }}>{power_sensors_summary.warning_count || 0}</span></div>
                    <div><strong>Critical:</strong> <span style={{ color: power_sensors_summary.critical_count > 0 ? '#dc2626' : '#22c55e' }}>{power_sensors_summary.critical_count || 0}</span></div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={power_sensors_data}
                totalRows={power_sensors_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'routing_config': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>HBF/PFRN Routing Configuration</h2>
              <p>Hash-Based Forwarding and Precise Forwarding Routing Notification config.</p>

              {routing_config_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Switches:</strong> {routing_config_summary.total_switches || 0}</div>
                    <div><strong>HBF Enabled:</strong> {routing_config_summary.hbf_enabled_count || 0}</div>
                    <div><strong>PFRN Enabled:</strong> {routing_config_summary.pfrn_enabled_count || 0}</div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>HBF Coverage:</strong> <span style={{ color: routing_config_summary.hbf_coverage_pct >= 80 ? '#22c55e' : '#eab308' }}>{routing_config_summary.hbf_coverage_pct?.toFixed(1) || 0}%</span></div>
                    <div><strong>PFRN Coverage:</strong> <span style={{ color: routing_config_summary.pfrn_coverage_pct >= 80 ? '#22c55e' : '#eab308' }}>{routing_config_summary.pfrn_coverage_pct?.toFixed(1) || 0}%</span></div>
                    <div><strong>Unique Seeds:</strong> {routing_config_summary.unique_seeds || 0}</div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={routing_config_data}
                totalRows={routing_config_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'temp_alerts': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Temperature Alerts</h2>
              <p>Temperature threshold configuration and alert status.</p>

              {temp_alerts_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Sensors:</strong> {temp_alerts_summary.total_sensors || 0}</div>
                    <div><strong>Max Temp:</strong> {temp_alerts_summary.max_temperature || 0}°C</div>
                    <div><strong>Healthy:</strong> <span style={{ color: '#22c55e' }}>{temp_alerts_summary.healthy_sensors || 0}</span></div>
                    <div><strong>Over Threshold:</strong> <span style={{ color: temp_alerts_summary.over_threshold_count > 0 ? '#dc2626' : '#22c55e' }}>{temp_alerts_summary.over_threshold_count || 0}</span></div>
                  </div>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Warnings:</strong> <span style={{ color: temp_alerts_summary.warning_count > 0 ? '#eab308' : '#22c55e' }}>{temp_alerts_summary.warning_count || 0}</span></div>
                    <div><strong>Critical:</strong> <span style={{ color: temp_alerts_summary.critical_count > 0 ? '#dc2626' : '#22c55e' }}>{temp_alerts_summary.critical_count || 0}</span></div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={temp_alerts_data}
                totalRows={temp_alerts_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'credit_watchdog': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Credit Watchdog Timeouts</h2>
              <p>Flow control credit watchdog timeout counters.</p>

              {credit_watchdog_summary && (
                <div style={{ marginBottom: '16px', padding: '12px', background: '#f1f5f9', borderRadius: '6px' }}>
                  <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
                    <div><strong>Total Entries:</strong> {credit_watchdog_summary.total_entries || 0}</div>
                    <div><strong>Ports with Timeouts:</strong> <span style={{ color: credit_watchdog_summary.ports_with_timeouts > 0 ? '#dc2626' : '#22c55e' }}>{credit_watchdog_summary.ports_with_timeouts || 0}</span></div>
                    <div><strong>Total Timeout Events:</strong> {credit_watchdog_summary.total_timeout_events?.toLocaleString() || 0}</div>
                    <div><strong>Max Count:</strong> {credit_watchdog_summary.max_timeout_count?.toLocaleString() || 0}</div>
                  </div>
                  <div style={{ marginTop: '8px' }}>
                    <strong>Affected VLs:</strong> {credit_watchdog_summary.affected_vls || 0}
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={credit_watchdog_data}
                totalRows={credit_watchdog_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'pci_performance': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2><HardDrive size={20} /> PCIe Performance</h2>
              {pci_performance_summary && (
                <div className="summary-box" style={{ marginBottom: '16px', padding: '12px', background: 'var(--sidebar-bg)', borderRadius: '8px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                    <div><strong>Total Nodes:</strong> {pci_performance_summary.total_nodes || 0}</div>
                    <div><strong>Degraded:</strong> <span style={{ color: pci_performance_summary.degraded_count > 0 ? '#dc2626' : '#22c55e' }}>{pci_performance_summary.degraded_count || 0}</span></div>
                    <div><strong>AER Errors:</strong> <span style={{ color: pci_performance_summary.aer_error_nodes > 0 ? '#dc2626' : '#22c55e' }}>{pci_performance_summary.aer_error_nodes || 0}</span></div>
                    <div><strong>Avg Bandwidth:</strong> {pci_performance_summary.avg_bandwidth_gbps?.toFixed(1) || 0} GB/s</div>
                  </div>
                  {pci_performance_summary.gen_distribution && Object.keys(pci_performance_summary.gen_distribution).length > 0 && (
                    <div style={{ marginTop: '12px' }}>
                      <strong>Generation Distribution:</strong>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                        {Object.entries(pci_performance_summary.gen_distribution).map(([gen, count]) => (
                          <span key={gen} style={{ background: 'var(--button-bg)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.85em' }}>
                            {gen}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={pci_performance_data}
                totalRows={pci_performance_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'ber_advanced': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2><BarChart3 size={20} /> BER Advanced Analysis</h2>
              {ber_advanced_summary && (
                <div className="summary-box" style={{ marginBottom: '16px', padding: '12px', background: 'var(--sidebar-bg)', borderRadius: '8px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                    <div><strong>Total Ports:</strong> {ber_advanced_summary.total_ports || 0}</div>
                    <div><strong>Critical BER:</strong> <span style={{ color: ber_advanced_summary.critical_ber_count > 0 ? '#dc2626' : '#22c55e' }}>{ber_advanced_summary.critical_ber_count || 0}</span></div>
                    <div><strong>Warning BER:</strong> <span style={{ color: ber_advanced_summary.warning_ber_count > 0 ? '#f59e0b' : '#22c55e' }}>{ber_advanced_summary.warning_ber_count || 0}</span></div>
                    <div><strong>Healthy Ports:</strong> <span style={{ color: '#22c55e' }}>{ber_advanced_summary.healthy_ports || 0}</span></div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', marginTop: '12px' }}>
                    <div><strong>Lanes Analyzed:</strong> {ber_advanced_summary.total_lanes_analyzed?.toLocaleString() || 0}</div>
                    <div><strong>FEC Corrected:</strong> {ber_advanced_summary.fec_corrected_total?.toLocaleString() || 0}</div>
                    <div><strong>FEC Uncorrected:</strong> <span style={{ color: ber_advanced_summary.fec_uncorrected_total > 0 ? '#dc2626' : '#22c55e' }}>{ber_advanced_summary.fec_uncorrected_total?.toLocaleString() || 0}</span></div>
                    {ber_advanced_summary.worst_ber_log10 && <div><strong>Worst BER:</strong> 10^{ber_advanced_summary.worst_ber_log10}</div>}
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={ber_advanced_data}
                totalRows={ber_advanced_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'cable_enhanced': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2><PlugZap size={20} /> Cable Enhanced Analysis</h2>
              {cable_enhanced_summary && (
                <div className="summary-box" style={{ marginBottom: '16px', padding: '12px', background: 'var(--sidebar-bg)', borderRadius: '8px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
                    <div><strong>Total Cables:</strong> {cable_enhanced_summary.total_cables || 0}</div>
                    <div><strong>Optical:</strong> {cable_enhanced_summary.optical_count || 0}</div>
                    <div><strong>AOC:</strong> {cable_enhanced_summary.aoc_count || 0}</div>
                    <div><strong>Copper:</strong> {cable_enhanced_summary.copper_count || 0}</div>
                    <div><strong>DOM Capable:</strong> {cable_enhanced_summary.dom_capable_count || 0}</div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginTop: '12px' }}>
                    <div><strong>Temp Warnings:</strong> <span style={{ color: cable_enhanced_summary.temp_warning_count > 0 ? '#f59e0b' : '#22c55e' }}>{cable_enhanced_summary.temp_warning_count || 0}</span></div>
                    <div><strong>Temp Critical:</strong> <span style={{ color: cable_enhanced_summary.temp_critical_count > 0 ? '#dc2626' : '#22c55e' }}>{cable_enhanced_summary.temp_critical_count || 0}</span></div>
                    <div><strong>Power Issues:</strong> <span style={{ color: (cable_enhanced_summary.power_warning_count + cable_enhanced_summary.power_critical_count) > 0 ? '#dc2626' : '#22c55e' }}>{(cable_enhanced_summary.power_warning_count || 0) + (cable_enhanced_summary.power_critical_count || 0)}</span></div>
                    <div><strong>Compliance Issues:</strong> <span style={{ color: cable_enhanced_summary.compliance_issues > 0 ? '#f59e0b' : '#22c55e' }}>{cable_enhanced_summary.compliance_issues || 0}</span></div>
                  </div>
                </div>
              )}

              <PaginatedTable
                rows={cable_enhanced_data}
                totalRows={cable_enhanced_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'per_lane_performance': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2><Layers size={20} /> Per-Lane Performance</h2>
              {per_lane_performance_summary && (
                <div className="summary-box" style={{ marginBottom: '16px', padding: '12px', background: 'var(--sidebar-bg)', borderRadius: '8px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                    <div><strong>Lanes Analyzed:</strong> {per_lane_performance_summary.total_lanes_analyzed?.toLocaleString() || 0}</div>
                    <div><strong>Ports Analyzed:</strong> {per_lane_performance_summary.total_ports_analyzed || 0}</div>
                    <div><strong>Lanes with Issues:</strong> <span style={{ color: per_lane_performance_summary.lanes_with_issues > 0 ? '#dc2626' : '#22c55e' }}>{per_lane_performance_summary.lanes_with_issues || 0}</span></div>
                    <div><strong>Issue Rate:</strong> <span style={{ color: per_lane_performance_summary.issue_rate_pct > 1 ? '#dc2626' : '#22c55e' }}>{per_lane_performance_summary.issue_rate_pct || 0}%</span></div>
                  </div>
                  {per_lane_performance_summary.lane_error_distribution && Object.keys(per_lane_performance_summary.lane_error_distribution).length > 0 && (
                    <div style={{ marginTop: '12px' }}>
                      <strong>Errors by Lane:</strong>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                        {Object.entries(per_lane_performance_summary.lane_error_distribution).map(([lane, count]) => (
                          <span key={lane} style={{ background: count > 0 ? '#fee2e2' : 'var(--button-bg)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.85em' }}>
                            Lane {lane}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={per_lane_performance_data}
                totalRows={per_lane_performance_total_rows}
              />
            </div>
          </div>
        )
      }
      case 'n2n_security': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2><Shield size={20} /> N2N Security</h2>
              {n2n_security_summary && (
                <div className="summary-box" style={{ marginBottom: '16px', padding: '12px', background: 'var(--sidebar-bg)', borderRadius: '8px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                    <div><strong>Total Nodes:</strong> {n2n_security_summary.total_nodes || 0}</div>
                    <div><strong>N2N Enabled:</strong> {n2n_security_summary.nodes_with_n2n_enabled || 0} ({n2n_security_summary.n2n_coverage_pct || 0}%)</div>
                    <div><strong>With Keys:</strong> {n2n_security_summary.nodes_with_keys || 0} ({n2n_security_summary.key_coverage_pct || 0}%)</div>
                    <div><strong>Security Violations:</strong> <span style={{ color: n2n_security_summary.security_violations > 0 ? '#dc2626' : '#22c55e' }}>{n2n_security_summary.security_violations || 0}</span></div>
                  </div>
                  {n2n_security_summary.capability_distribution && Object.keys(n2n_security_summary.capability_distribution).length > 0 && (
                    <div style={{ marginTop: '12px' }}>
                      <strong>Capability Distribution:</strong>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                        {Object.entries(n2n_security_summary.capability_distribution).slice(0, 6).map(([cap, count]) => (
                          <span key={cap} style={{ background: 'var(--button-bg)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.85em' }}>
                            {cap}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <PaginatedTable
                rows={n2n_security_data}
                totalRows={n2n_security_total_rows}
              />
            </div>
          </div>
        )
      }
      default:
        return null
    }
  }

  return (
    <div className="container">
      <header className="header">
        <h1><Activity size={28} color="#76b900" /> NVIDIA Network Health Check Platform</h1>
      </header>
      
      <div className="main">
        <div className="sidebar">
          <div className="upload-card">
            <h3><Server size={20} /> IBDiagnet Analysis</h3>
            <p>Upload .zip / .tar.gz from ibdiagnet.</p>
            <div className="file-input-wrapper">
              <input 
                type="file" 
                accept=".zip,.tar.gz" 
                onChange={handleIbdiagnetUpload} 
                disabled={loading}
              />
            </div>
          </div>

          <div className="upload-card">
            <h3><FileText size={20} /> UFM CSV Analysis</h3>
            <p>Upload command CSV (e.g. low_freq_debug).</p>
            <div className="file-input-wrapper">
              <input 
                type="file" 
                accept=".csv" 
                onChange={handleCsvUpload} 
                disabled={loading}
              />
            </div>
          </div>
          
          {error && (
            <div style={{color: '#c53030', background: '#fff5f5', padding: '10px', borderRadius: '4px', border: '1px solid #fed7d7'}}>
              <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
                <AlertTriangle size={16} />
                <strong>Error</strong>
              </div>
              <p style={{margin: '5px 0 0 0', fontSize: '0.9rem'}}>{error}</p>
            </div>
          )}
        </div>

        <div className="content">
          {result && result.type === 'ibdiagnet' && (
            <div className="tabs grouped-tabs">
              <div
                className={`tab overview-tab ${activeTab === 'overview' ? 'active' : ''}`}
                onClick={() => setActiveTab('overview')}
              >
                <Activity size={16} /> 总览
              </div>
              {TAB_GROUPS.map(group => (
                <div key={group.key} className="tab-group">
                  <div className="tab-group-header">
                    <h4>{group.label}</h4>
                    <span>{group.description}</span>
                  </div>
                  <div className="tab-group-tabs">
                    {group.tabs.map(({ key, label, icon: Icon }) => (
                      <div
                        key={key}
                        className={`tab ${activeTab === key ? 'active' : ''}`}
                        onClick={() => setActiveTab(key)}
                      >
                        {Icon && <Icon size={16} />} {label}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="content-inner">
            {result ? (
              <>
                {result.type === 'ibdiagnet' && renderIbdiagnetContent()}
                
                {result.type === 'csv' && (
                  <div className="scroll-area">
                    <div className="card">
                      <h2>{result.data.filename}</h2>
                      <p>Total Rows: {result.data.row_count}</p>
                      <PaginatedTable
                        rows={result.data.data}
                        totalRows={result.data.row_count}
                      />
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="placeholder">
                <Activity size={48} style={{opacity: 0.2, marginBottom: '20px'}} />
                <p>Select a file from the sidebar to start analysis.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          {uploadProgress > 0 && uploadProgress < 100 ? (
            <>
              <p>Uploading file... Please wait.</p>
              <div style={{ marginTop: '20px', width: '300px' }}>
                <div style={{
                  width: '100%',
                  height: '8px',
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  borderRadius: '4px',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    width: `${uploadProgress}%`,
                    height: '100%',
                    backgroundColor: '#76b900',
                    transition: 'width 0.3s ease'
                  }} />
                </div>
                <p style={{ marginTop: '10px', fontSize: '0.9rem' }}>
                  Progress: {uploadProgress}%
                </p>
              </div>
            </>
          ) : (
            <>
              <p>Processing Analysis... This may take several minutes for large files.</p>
              <p style={{ marginTop: '10px', fontSize: '0.85rem', opacity: 0.8 }}>
                Please be patient. Backend is analyzing the network data.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default App
