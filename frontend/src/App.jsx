import { useState } from 'react'
import axios from 'axios'
import { Upload, FileText, Activity, Server, AlertTriangle, ShieldCheck, Cpu, CheckCircle, XCircle, AlertCircle, Fan as FanIcon, Clock3, BookOpen, ChevronDown, ChevronUp, Thermometer, Zap, Network, GitBranch, Layers, Settings, Database, Cpu as ChipIcon, BarChart2, Key, Box, Info, PlugZap, Shuffle, BrainCircuit, Shield, Radio, Users, BarChart3, HardDrive, Router, ThermometerSun, Timer } from 'lucide-react'
import { getErrorExplanation } from './ErrorExplanations'
import { ensureArray, toNumber } from './analysisUtils'
import FaultSummary from './FaultSummary'
import CableAnalysis from './CableAnalysis'
import BERAnalysis from './BERAnalysis'
import CongestionAnalysis from './CongestionAnalysis'
import LinkOscillation from './LinkOscillation'
import HcaAnalysis from './HcaAnalysis'
import FanAnalysis from './FanAnalysis'
import SwitchesAnalysis from './SwitchesAnalysis'
import RoutingAnalysis from './RoutingAnalysis'
import QosAnalysis from './QosAnalysis'
import SmInfoAnalysis from './SmInfoAnalysis'
import PortHierarchyAnalysis from './PortHierarchyAnalysis'
import MlnxCountersAnalysis from './MlnxCountersAnalysis'
import PmDeltaAnalysis from './PmDeltaAnalysis'
import VportsAnalysis from './VportsAnalysis'
import PkeyAnalysis from './PkeyAnalysis'
import SystemInfoAnalysis from './SystemInfoAnalysis'
import ExtendedPortInfoAnalysis from './ExtendedPortInfoAnalysis'
import ArInfoAnalysis from './ArInfoAnalysis'
import SharpAnalysis from './SharpAnalysis'
import FecModeAnalysis from './FecModeAnalysis'
import PhyDiagnosticsAnalysis from './PhyDiagnosticsAnalysis'
import NeighborsAnalysis from './NeighborsAnalysis'
import BufferHistogramAnalysis from './BufferHistogramAnalysis'
import ExtendedNodeInfoAnalysis from './ExtendedNodeInfoAnalysis'
import ExtendedSwitchInfoAnalysis from './ExtendedSwitchInfoAnalysis'
import PowerSensorsAnalysis from './PowerSensorsAnalysis'
import RoutingConfigAnalysis from './RoutingConfigAnalysis'
import TempAlertsAnalysis from './TempAlertsAnalysis'
import CreditWatchdogAnalysis from './CreditWatchdogAnalysis'
import PciPerformanceAnalysis from './PciPerformanceAnalysis'
import PerLanePerformanceAnalysis from './PerLanePerformanceAnalysis'
import N2nSecurityAnalysis from './N2nSecurityAnalysis'
import LatencyAnalysis from './LatencyAnalysis'
import HealthCheckBoard from './HealthCheckBoard'
import { HEALTH_CHECK_GROUPS, HEALTH_CHECK_DEFINITIONS } from './healthCheckDefinitions'
import './App.css'
import DataTable from './DataTable'

// Configuration - use relative URL for proxy support
const normalizeBaseUrl = (value = '') => value.replace(/\/+$/, '')
const rawBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_URL || '')
const hasApiSuffix = rawBaseUrl.endsWith('/api')
const apiRootUrl = hasApiSuffix ? rawBaseUrl.slice(0, -4) : rawBaseUrl
const API_ENDPOINT_BASE = hasApiSuffix ? rawBaseUrl : (apiRootUrl ? `${apiRootUrl}/api` : '/api')

const buildApiUrl = (path = '') => `${API_ENDPOINT_BASE}${path}`

const resolveMaxFileSize = () => {
  const fromEnv = Number(import.meta.env.VITE_MAX_FILE_SIZE)
  if (Number.isFinite(fromEnv) && fromEnv > 0) {
    return fromEnv
  }
  return 500 * 1024 * 1024 // fallback to 500MB
}

const MAX_FILE_SIZE = resolveMaxFileSize()
const FILE_SIZE_MB = 500

const RECENT_REBOOT_THRESHOLD_HOURS = 1

const extractHostLabel = (raw = '') => {
  if (!raw) return 'Unknown'
  const withoutSlash = raw.split('/')[0] || raw
  const hcaSplitIndex = withoutSlash.indexOf(' HCA')
  if (hcaSplitIndex >= 0) {
    return withoutSlash.slice(0, hcaSplitIndex).trim() || withoutSlash.trim()
  }
  return withoutSlash.trim() || raw
}

const buildFrequentRebootHosts = (rows = []) => {
  const hosts = new Map()
  ensureArray(rows).forEach(row => {
    const flagged = row?.RecentlyRebooted ?? row?.recentlyRebooted
    if (!flagged) return
    const nodeName = row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown Node'
    const hostLabel = extractHostLabel(nodeName)
    const uptime = row['Up Time'] || row.UpTime || row.HWInfo_UpTime || 'N/A'
    const seconds = Number(row?.UptimeSeconds ?? row?.uptimeSeconds ?? 0)
    const entry = hosts.get(hostLabel) || { host: hostLabel, nodes: [], minSeconds: Number.isFinite(seconds) ? seconds : Infinity }
    entry.nodes.push({
      nodeName,
      guid: row.NodeGUID,
      uptime,
      seconds,
    })
    if (Number.isFinite(seconds)) {
      entry.minSeconds = Math.min(entry.minSeconds, seconds)
    }
    hosts.set(hostLabel, entry)
  })
  return Array.from(hosts.values()).sort((a, b) => (a.minSeconds || Infinity) - (b.minSeconds || Infinity))
}

const TAB_ICON_MAP = {
  overview: Activity,
  cable: Server,
  link_oscillation: AlertTriangle,
  xmit: AlertTriangle,
  latency: Clock3,
  per_lane_performance: Layers,
  ber: ShieldCheck,
  hca: Cpu,
  system_info: Info,
  sm_info: Settings,
  fan: FanIcon,
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

const resolveTabMeta = (key) => TAB_LOOKUP[key] || { label: key, icon: Activity }

const summarizeBerHealth = (berData = []) => {
  const rows = ensureArray(berData)
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

function App() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [navCollapsedGroups, setNavCollapsedGroups] = useState({})

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
      link_oscillation_data,
      ber_data,
      hca_data,
      fan_data,
      histogram_data,
      switch_data,
      routing_data,
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
      per_lane_performance_data,
      n2n_security_data,
      cable_summary,
      link_oscillation_summary,
      xmit_summary,
      histogram_summary,
      fan_summary,
      switch_summary,
      routing_summary,
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
      per_lane_performance_summary,
      n2n_security_summary,
      warnings_by_category,
      warnings_summary,
      health,
      data_total_rows,
      cable_total_rows,
      xmit_total_rows,
      link_oscillation_total_rows,
      ber_total_rows,
      hca_total_rows,
      fan_total_rows,
      histogram_total_rows,
      switch_total_rows,
      routing_total_rows,
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
      per_lane_performance_total_rows,
      n2n_security_total_rows,
    } = result.data

    // Extract warnings by category for merging into tabs
    const firmwareWarnings = warnings_by_category?.firmware || []
    const pciWarnings = warnings_by_category?.pci || []

    switch (activeTab) {
      case 'overview': {
        const actionPlan = buildActionPlan(health?.issues || [])
        const berSnapshot = summarizeBerHealth(ber_data)
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
        const frequentReboots = buildFrequentRebootHosts(hca_data)
        const totalRebootHcas = frequentReboots.reduce((sum, host) => sum + host.nodes.length, 0)

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

            {frequentReboots.length > 0 && (
              <div className="card">
                <div className="card-header-row">
                  <h2>?? Frequent Rebooting Servers</h2>
                  <button type="button" className="ghost-link" onClick={() => setActiveTab('hca')}>
                    查看 HCA 标签
                  </button>
                </div>
                <p className="card-subtitle">
                  最近 {RECENT_REBOOT_THRESHOLD_HOURS} 小时内重启的主机（依据 HWInfo_UpTime）
                </p>
                <div className="overview-stat-row">
                  <div className="overview-stat">
                    <span className="overview-stat-label">受影响主机</span>
                    <span className="overview-stat-value">{frequentReboots.length}</span>
                  </div>
                  <div className="overview-stat">
                    <span className="overview-stat-label">关联 HCA</span>
                    <span className="overview-stat-value">{totalRebootHcas}</span>
                  </div>
                </div>
                <ul className="overview-alert-list">
                  {frequentReboots.slice(0, 5).map(host => {
                    const preview = host.nodes.slice(0, 3)
                    return (
                      <li key={host.host}>
                        <div>
                          <strong>{host.host}</strong> · {host.nodes.length} HCA
                        </div>
                        <div className="overview-alert-metadata">
                          {preview.map(node => {
                            const suffix = node.nodeName?.startsWith(host.host)
                              ? node.nodeName.slice(host.host.length).replace(/^[/\-\s]+/, '') || node.nodeName
                              : node.nodeName
                            return (
                              <span key={`${node.guid || node.nodeName}-uptime`}>
                                {suffix || node.nodeName || node.guid} · {node.uptime}
                              </span>
                            )
                          })}
                          {host.nodes.length > preview.length && (
                            <span>+{host.nodes.length - preview.length} 更多</span>
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
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
                <DataTable
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
            <CableAnalysis cableData={cable_data} summary={cable_summary} />
          </div>
        )
      }
      case 'link_oscillation': {
        return (
          <div className="scroll-area">
            <LinkOscillation
              paths={link_oscillation_data}
              summary={link_oscillation_summary}
            />
          </div>
        )
      }
      case 'xmit': {
        return (
          <div className="scroll-area">
            <CongestionAnalysis xmitData={xmit_data} summary={xmit_summary} />
          </div>
        )
      }
      case 'ber': {
        return (
          <div className="scroll-area">
            <BERAnalysis
              berData={ber_data}
            />
          </div>
        )
      }
      case 'hca': {
        return (
          <div className="scroll-area">
              <HcaAnalysis
                hcaData={hca_data}
                firmwareWarnings={firmwareWarnings}
                pciWarnings={pciWarnings}
                summary={null}
              />
          </div>
        )
      }
      case 'latency': {
        return (
          <div className="scroll-area">
              <LatencyAnalysis
                histogramData={histogram_data}
                summary={histogram_summary}
              />
          </div>
        )
      }
      case 'fan': {
        return (
          <div className="scroll-area">
              <FanAnalysis fanData={fan_data} summary={fan_summary} />
          </div>
        )
      }
      case 'switches': {
        return (
          <div className="scroll-area">
              <SwitchesAnalysis switchData={switch_data} summary={switch_summary} />
          </div>
        )
      }
      case 'routing': {
        return (
          <div className="scroll-area">
              <RoutingAnalysis routingData={routing_data} summary={routing_summary} />
          </div>
        )
      }
      case 'qos': {
        return (
          <div className="scroll-area">
              <QosAnalysis qosData={qos_data} summary={qos_summary} />
          </div>
        )
      }
      case 'sm_info': {
        return (
          <div className="scroll-area">
              <SmInfoAnalysis smInfoData={sm_info_data} summary={sm_info_summary} />
          </div>
        )
      }
      case 'port_hierarchy': {
        return (
          <div className="scroll-area">
              <PortHierarchyAnalysis portHierarchyData={port_hierarchy_data} summary={port_hierarchy_summary} />
          </div>
        )
      }
      case 'mlnx_counters': {
        return (
          <div className="scroll-area">
              <MlnxCountersAnalysis mlnxCountersData={mlnx_counters_data} summary={mlnx_counters_summary} />
          </div>
        )
      }
      case 'pm_delta': {
        return (
          <div className="scroll-area">
              <PmDeltaAnalysis pmDeltaData={pm_delta_data} summary={pm_delta_summary} />
          </div>
        )
      }
      case 'vports': {
        return (
          <div className="scroll-area">
              <VportsAnalysis vportsData={vports_data} summary={vports_summary} />
          </div>
        )
      }
      case 'pkey': {
        return (
          <div className="scroll-area">
              <PkeyAnalysis pkeyData={pkey_data} summary={pkey_summary} />
          </div>
        )
      }
      case 'system_info': {
        return (
          <div className="scroll-area">
              <SystemInfoAnalysis systemInfoData={system_info_data} summary={system_info_summary} />
          </div>
        )
      }
      case 'extended_port_info': {
        return (
          <div className="scroll-area">
              <ExtendedPortInfoAnalysis extendedPortInfoData={extended_port_info_data} summary={extended_port_info_summary} />
          </div>
        )
      }
      case 'ar_info': {
        return (
          <div className="scroll-area">
              <ArInfoAnalysis arInfoData={ar_info_data} summary={ar_info_summary} />
          </div>
        )
      }
      case 'sharp': {
        return (
          <div className="scroll-area">
              <SharpAnalysis sharpData={sharp_data} summary={sharp_summary} />
          </div>
        )
      }
      case 'fec_mode': {
        return (
          <div className="scroll-area">
              <FecModeAnalysis fecModeData={fec_mode_data} summary={fec_mode_summary} />
          </div>
        )
      }
      case 'phy_diagnostics': {
        return (
          <div className="scroll-area">
              <PhyDiagnosticsAnalysis phyDiagnosticsData={phy_diagnostics_data} summary={phy_diagnostics_summary} />
          </div>
        )
      }
      case 'neighbors': {
        return (
          <div className="scroll-area">
              <NeighborsAnalysis neighborsData={neighbors_data} summary={neighbors_summary} />
          </div>
        )
      }
      case 'buffer_histogram': {
        return (
          <div className="scroll-area">
              <BufferHistogramAnalysis bufferHistogramData={buffer_histogram_data} summary={buffer_histogram_summary} />
          </div>
        )
      }
      case 'extended_node_info': {
        return (
          <div className="scroll-area">
              <ExtendedNodeInfoAnalysis extendedNodeInfoData={extended_node_info_data} summary={extended_node_info_summary} />
          </div>
        )
      }
      case 'extended_switch_info': {
        return (
          <div className="scroll-area">
              <ExtendedSwitchInfoAnalysis extendedSwitchInfoData={extended_switch_info_data} summary={extended_switch_info_summary} />
          </div>
        )
      }
      case 'power_sensors': {
        return (
          <div className="scroll-area">
              <PowerSensorsAnalysis powerSensorsData={power_sensors_data} summary={power_sensors_summary} />
          </div>
        )
      }
      case 'routing_config': {
        return (
          <div className="scroll-area">
              <RoutingConfigAnalysis routingConfigData={routing_config_data} summary={routing_config_summary} />
          </div>
        )
      }
      case 'temp_alerts': {
        return (
          <div className="scroll-area">
              <TempAlertsAnalysis tempAlertsData={temp_alerts_data} summary={temp_alerts_summary} />
          </div>
        )
      }
      case 'credit_watchdog': {
        return (
          <div className="scroll-area">
              <CreditWatchdogAnalysis creditWatchdogData={credit_watchdog_data} summary={credit_watchdog_summary} />
          </div>
        )
      }
      case 'pci_performance': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>PCIe Performance</h2>
              <p>PCIe generation, bandwidth, and degradation analysis.</p>
              <PciPerformanceAnalysis pciPerformanceData={pci_performance_data} summary={pci_performance_summary} />
            </div>
          </div>
        )
      }
      case 'per_lane_performance': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Per-Lane Performance</h2>
              <p>Per-lane signal quality and error distribution analysis.</p>
              <PerLanePerformanceAnalysis perLanePerformanceData={per_lane_performance_data} summary={per_lane_performance_summary} />
            </div>
          </div>
        )
      }
      case 'n2n_security': {
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>N2N Security</h2>
              <p>Node-to-node encryption and security configuration status.</p>
              <N2nSecurityAnalysis n2nSecurityData={n2n_security_data} summary={n2n_security_summary} />
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
          <aside className="tab-panel">
            {result && result.type === 'ibdiagnet' ? (
              <>
                <div className="tab-panel-header">
                  <div>
                    <p className="tab-panel-caption">健康分组导航</p>
                    <h3>分析标签</h3>
                  </div>
                </div>
                <div className="tabs grouped-tabs">
                  <div
                    className={`tab overview-tab ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                  >
                    <Activity size={16} /> 总览
                  </div>
                  {TAB_GROUPS.map(group => {
                    const collapsed = !!navCollapsedGroups[group.key]
                    return (
                      <div key={group.key} className="tab-group">
                        <div className="tab-group-header">
                          <div>
                            <h4>{group.label}</h4>
                            <span>{group.description}</span>
                          </div>
                          <button
                            type="button"
                            className="tab-group-toggle"
                            onClick={() => toggleNavGroup(group.key)}
                            aria-label="Toggle group"
                          >
                            {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                          </button>
                        </div>
                        {!collapsed && (
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
                        )}
                      </div>
                    )
                  })}
                </div>
              </>
            ) : (
              <div className="tab-panel-placeholder">
                <p>上传 ibdiagnet 结果后即可浏览各类检查分组。</p>
              </div>
            )}
          </aside>

          <div className="workspace">
            <div className="content-inner">
              {result ? (
                <>
                  {result.type === 'ibdiagnet' && renderIbdiagnetContent()}

                  {result.type === 'csv' && (
                    <div className="scroll-area">
                      <div className="card">
                        <h2>{result.data.filename}</h2>
                        <p>Total Rows: {result.data.row_count}</p>
                        <DataTable
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
  const toggleNavGroup = (groupKey) => {
    setNavCollapsedGroups(prev => ({
      ...prev,
      [groupKey]: !prev[groupKey],
    }))
  }
