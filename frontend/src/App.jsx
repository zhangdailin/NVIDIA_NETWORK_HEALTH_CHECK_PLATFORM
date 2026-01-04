import { useState } from 'react'
import axios from 'axios'
import { Upload, FileText, Activity, Server, Network, AlertTriangle, ShieldCheck, Cpu, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import TopologyControls from './TopologyControls'
import './App.css'

// Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const MAX_FILE_SIZE = 500 * 1024 * 1024 // 500MB

const ensureArray = (value) => (Array.isArray(value) ? value : [])

const toNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

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
      const severity =
        level === 'severe'
          ? 'critical'
          : level === 'warning'
            ? 'warning'
            : ratio >= 5
              ? 'critical'
              : ratio >= 1
                ? 'warning'
                : 'info'
      return {
        title: `${row['Node Name'] || row.NodeGUID || 'Unknown'} - Port ${row.PortNumber}`,
        ratio,
        waitSeconds,
        severity,
      }
    })
    .filter(item => item.ratio >= 1)
    .sort((a, b) => b.ratio - a.ratio)
    .slice(0, 3)
    .map(item => ({
      ...item,
      subtitle: `PortXmitWait ratio ${item.ratio.toFixed(1)}%`,
      description: `Approx. ${item.waitSeconds.toFixed(2)}s of the sample window was spent waiting. The ibdiagnet guide (Section 5.2) classifies ${
        item.ratio >= 5 ? '>=5%' : '1-5%'
      } as ${item.ratio >= 5 ? 'severe' : 'warning'} congestion, so rebalance flows or add bandwidth.`,
      reference: 'doc/ibdiagnet_health_check_guide.md:338-345',
    }))
}

const buildBerInsights = (rows = []) => {
  const safeRows = ensureArray(rows)
  return safeRows
    .map(row => {
      const log10 = toNumber(row.SymbolBERLog10Value)
      const severity = row.SymbolBERSeverity || 'info'
      return {
        title: `${row['Node Name'] || row.NodeGUID || 'Node'} - Port ${row.PortNumber}`,
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

const buildCableInsights = (rows = []) => {
  const safeRows = ensureArray(rows)
  return safeRows
    .map(row => {
      const temp = toNumber(row['Temperature (c)'] ?? row.Temperature)
      const vendor = row.Vendor || row['Vendor Name'] || 'Optic'
      const linkDown = toNumber(row.LinkDownedCounter ?? row.LinkDownedCounterExt)
      const redFlagCounters = ['PortRcvErrors', 'PortXmitDiscards', 'PortRcvRemotePhysicalErrors']
      const hasErrors = redFlagCounters.some(key => toNumber(row[key]) > 0)
      const severity = temp >= 80 || linkDown > 0 || hasErrors ? 'critical' : temp >= 70 ? 'warning' : 'info'

      return {
        vendor,
        title: `${vendor} - Port ${row.PortNumber ?? 'N/A'}`,
        temp,
        linkDown,
        hasErrors,
        severity,
      }
    })
    .filter(item => item.temp >= 70 || item.linkDown > 0 || item.hasErrors)
    .sort((a, b) => b.temp - a.temp)
    .slice(0, 3)
    .map(item => ({
      ...item,
      subtitle: item.temp ? `Module temperature ${item.temp.toFixed(1)}C` : 'Optical issue detected',
      description:
        item.temp >= 80
          ? 'Optic temperature is in the critical zone. Improve cooling and consider swapping the module.'
          : item.temp >= 70
            ? 'Optic temperature is trending high; clean airflow paths and monitor closely.'
            : 'Error counters exceeded zero; inspect the cable/optic and clear counters before retesting.',
      reference: 'doc/ibdiagnet_health_check_guide.md:170-233,320-357',
      actions:
        item.temp >= 70
          ? ['Check rack airflow or blocked filters', 'Schedule optic replacement if temperature keeps rising']
          : ['Inspect cable seating and clean the connector', 'Reset counters and verify whether errors reappear'],
    }))
}
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

  // Group issues by category
  const groupedIssues = issues.reduce((acc, issue) => {
    if (!acc[issue.category]) acc[issue.category] = []
    acc[issue.category].push(issue)
    return acc
  }, {})

  return (
    <div className="issues-list">
      {Object.entries(groupedIssues).map(([category, categoryIssues]) => (
        <div key={category} className="issue-category">
          <h4 className="issue-category-title">{category.toUpperCase()}</h4>
          {categoryIssues.slice(0, 10).map((issue, idx) => (
            <div key={idx} className="issue-item" style={{ borderLeftColor: getSeverityColor(issue.severity) }}>
              <div className="issue-header">
                <span className="issue-severity" style={{ color: getSeverityColor(issue.severity) }}>
                  {issue.severity.toUpperCase()}
                </span>
                <span className="issue-description">{issue.description}</span>
              </div>
              <div className="issue-details">
                <span>Node: {issue.node_guid ? String(issue.node_guid).slice(0, 16) + '...' : 'N/A'}</span>
                <span>Port: {issue.port_number}</span>
              </div>
              {issue.details?.kb && (
                <div className="issue-knowledge">
                  <p className="issue-knowledge-title">{issue.details.kb.title}</p>
                  <p className="issue-knowledge-text">{issue.details.kb.why_it_matters}</p>
                  {issue.details.kb.likely_causes?.length > 0 && (
                    <div className="issue-knowledge-section">
                      <strong>Possible causes</strong>
                      <ul>
                        {issue.details.kb.likely_causes.slice(0, 3).map((cause, idx2) => (
                          <li key={idx2}>{cause}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {issue.details.kb.recommended_actions?.length > 0 && (
                    <div className="issue-knowledge-section">
                      <strong>Recommended actions</strong>
                      <ul>
                        {issue.details.kb.recommended_actions.slice(0, 3).map((action, idx3) => (
                          <li key={idx3}>{action}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {issue.details.kb.reference && (
                    <p className="issue-knowledge-reference">Reference: {issue.details.kb.reference}</p>
                  )}
                </div>
              )}
            </div>
          ))}
          {categoryIssues.length > 10 && (
            <p className="more-issues">... and {categoryIssues.length - 10} more</p>
          )}
        </div>
      ))}
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
    if (err.response?.status === 413) {
      return 'File too large. Maximum size is 500MB'
    }
    if (err.response?.status === 400) {
      return err.response?.data?.detail || 'Invalid file format'
    }
    if (err.response?.status === 500) {
      return `Server error: ${err.response?.data?.detail || 'Analysis failed'}`
    }
    if (err.code === 'ECONNABORTED') {
      return 'Request timeout. File may be too large or server is busy'
    }
    if (err.code === 'ERR_NETWORK') {
      return 'Network error. Please check if the backend server is running'
    }
    return err.response?.data?.detail || err.message || 'Unknown error occurred'
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

      const response = await axios.post(`${API_BASE_URL}/api/upload/ibdiagnet`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 300000, // 5 minutes timeout
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

      const response = await axios.post(`${API_BASE_URL}/api/upload/ufm-csv`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        timeout: 120000, // 2 minutes timeout
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

const renderJsonTable = (data) => {
  const rows = ensureArray(data)
  if (!rows.length) {
      // Try to show debug info if available in result
      if (result && result.data && (result.data.debug_stdout || result.data.debug_stderr)) {
          return (
                <div>
                    <p>No structured data available.</p>
                    {result.data.debug_stderr && (
                        <div style={{marginTop: '20px'}}>
                            <h4>Debug Error Log:</h4>
                            <pre style={{color: 'red'}}>{result.data.debug_stderr}</pre>
                        </div>
                    )}
                    {result.data.debug_stdout && (
                        <div style={{marginTop: '20px'}}>
                            <h4>Debug Output Log:</h4>
                            <pre>{result.data.debug_stdout}</pre>
                        </div>
                    )}
                </div>
            )
        }
        return <p>No data available.</p>
    }
    const columns = Object.keys(rows[0] || {})
    if (columns.length === 0) {
      return <p>No structured columns available.</p>
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
            {rows.map((row, i) => (
              <tr key={i}>
                {columns.map(col => <td key={col}>{
                  typeof row[col] === 'object' ? JSON.stringify(row[col]) : row[col]
                }</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  const renderIbdiagnetContent = () => {
    const { data, cable_data, xmit_data, ber_data, hca_data, topo_url, health } = result.data

    switch (activeTab) {
      case 'overview': {
        const actionPlan = buildActionPlan(health?.issues || [])
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Network Health Score</h2>
              <HealthScore health={health} />
            </div>
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
              {Array.isArray(data) ? renderJsonTable(data) : (
                  <pre>{JSON.stringify(data, null, 2)}</pre>
              )}
            </div>
          </div>
        )
      }
      case 'topology':
        return (
          <div className="iframe-container" style={{position: 'relative'}}>
            <TopologyControls onFilterChange={(filters) => console.log('Filters:', filters)} />
            {topo_url ? (
              <iframe
                src={`${API_BASE_URL}${topo_url}`}
                title="Network Topology"
                width="100%"
                height="100%"
                style={{border: 'none'}}
              />
            ) : (
              <div style={{padding: '2rem'}}>
                <p>Topology map not available.</p>
              </div>
            )}
          </div>
        )
      case 'cable': {
        const cableInsights = buildCableInsights(cable_data || [])
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Cable Health Check</h2>
              <p>Optics temperature, vendor, and error counter summary.</p>
              {cableInsights.length > 0 && (
                <div className="insight-grid">
                  {cableInsights.map((insight, idx) => (
                    <InsightCard
                      key={`cable-${idx}`}
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
              {renderJsonTable(cable_data)}
            </div>
          </div>
        )
      }
      case 'xmit': {
        const congestionInsights = buildCongestionInsights(xmit_data || [])
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Congestion & Errors (Xmit)</h2>
              <p>Port transmission wait times and congestion counters.</p>
              {congestionInsights.length > 0 && (
                <div className="insight-grid">
                  {congestionInsights.map((insight, idx) => (
                    <InsightCard
                      key={`xmit-${idx}`}
                      title={insight.title}
                      subtitle={insight.subtitle}
                      description={insight.description}
                      severity={insight.severity}
                      reference={insight.reference}
                    />
                  ))}
                </div>
              )}
              {renderJsonTable(xmit_data)}
            </div>
          </div>
        )
      }
      case 'ber': {
        const berInsights = buildBerInsights(ber_data || [])
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Bit Error Rate (BER) Analysis</h2>
              <p>Signal integrity issues and high bit error rates.</p>
              {berInsights.length > 0 && (
                <div className="insight-grid">
                  {berInsights.map((insight, idx) => (
                    <InsightCard
                      key={`ber-${idx}`}
                      title={insight.title}
                      subtitle={insight.subtitle}
                      description={insight.description}
                      severity={insight.severity}
                      reference={insight.reference}
                    />
                  ))}
                </div>
              )}
              {renderJsonTable(ber_data)}
            </div>
          </div>
        )
      }
      case 'hca':
        return (
          <div className="scroll-area">
            <div className="card">
              <h2>Device & Firmware Analysis</h2>
              <p>Firmware version inconsistencies and device anomalies.</p>
              {renderJsonTable(hca_data)}
            </div>
          </div>
        )
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
            <div className="tabs">
              <div className={`tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
                <Activity size={16} /> Overview
              </div>
              <div className={`tab ${activeTab === 'topology' ? 'active' : ''}`} onClick={() => setActiveTab('topology')}>
                <Network size={16} /> Topology
              </div>
              <div className={`tab ${activeTab === 'cable' ? 'active' : ''}`} onClick={() => setActiveTab('cable')}>
                <Server size={16} /> Cable Issues
              </div>
              <div className={`tab ${activeTab === 'xmit' ? 'active' : ''}`} onClick={() => setActiveTab('xmit')}>
                <AlertTriangle size={16} /> Congestion
              </div>
              <div className={`tab ${activeTab === 'ber' ? 'active' : ''}`} onClick={() => setActiveTab('ber')}>
                <ShieldCheck size={16} /> BER
              </div>
              <div className={`tab ${activeTab === 'hca' ? 'active' : ''}`} onClick={() => setActiveTab('hca')}>
                <Cpu size={16} /> Firmware
              </div>
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
                      {renderJsonTable(result.data.data)}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="placeholder">
                <Network size={48} style={{opacity: 0.2, marginBottom: '20px'}} />
                <p>Select a file from the sidebar to start analysis.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <p>Processing Analysis... This may take a moment.</p>
          {uploadProgress > 0 && uploadProgress < 100 && (
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
                Uploading: {uploadProgress}%
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
