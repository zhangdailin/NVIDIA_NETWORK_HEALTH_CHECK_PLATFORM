import { useState } from 'react'
import { AlertTriangle, CheckCircle, XCircle, Thermometer, Cable, Activity, TrendingUp, Award, Zap, BarChart3, ChevronDown, ChevronUp } from 'lucide-react'
import DataTable from '../../DataTable'

function UFMOverview({ data, onSelectTab }) {
    const [expandedSections, setExpandedSections] = useState({
        issues: true,
        health: true,
        overview: true,
    })

    // Helper function to get health color
    const getHealthColor = (score) => {
        if (score >= 90) return '#22c55e'
        if (score >= 80) return '#84cc16'
        if (score >= 70) return '#eab308'
        if (score >= 60) return '#f97316'
        return '#ef4444'
    }

    const toggleSection = (section) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }))
    }

    // Export data as JSON
    const exportData = () => {
        const dataStr = JSON.stringify(data, null, 2)
        const dataBlob = new Blob([dataStr], { type: 'application/json' })
        const url = URL.createObjectURL(dataBlob)
        const link = document.createElement('a')
        link.href = url
        link.download = `ufm-analysis-${new Date().toISOString()}.json`
        link.click()
        URL.revokeObjectURL(url)
    }

    if (!data || !data.analysis) return null
    const { analysis, load_info } = data

    const navigateToTab = (tab) => {
        if (onSelectTab) onSelectTab(tab)
    }

    return (
        <div className="ufm-analysis">
            {/* Issues Summary */}
            <div className="analysis-section issues-summary">
                <div className="section-header" onClick={() => toggleSection('issues')}>
                    <h2 className="section-title">
                        <AlertTriangle size={20} />
                        问题汇总 (Issues Summary)
                    </h2>
                    {expandedSections.issues ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </div>

                {expandedSections.issues && (
                    <div className="section-content">
                        {/* Critical Issues */}
                        <div className="issues-critical">
                            <h3 style={{ color: '#ef4444', marginBottom: '16px' }}>
                                <XCircle size={18} style={{ marginRight: '8px' }} />
                                严重问题 (Critical Issues)
                            </h3>
                            <div className="issue-cards">
                                {/* Critical BER Ports */}
                                {analysis.ber_analysis?.critical_ports?.length > 0 && (
                                    <div className="issue-card critical">
                                        <div className="issue-header">
                                            <TrendingUp size={18} />
                                            <span>严重 BER 错误</span>
                                        </div>
                                        <div className="issue-count">{analysis.ber_analysis.critical_ports.length}</div>
                                        <div className="issue-desc">端口 BER &gt; 1e-6</div>
                                        <button onClick={() => navigateToTab('ber')} className="view-details-btn">
                                            查看详情
                                        </button>
                                    </div>
                                )}

                                {/* Links Down */}
                                {analysis.link_status?.summary?.links_down > 0 && (
                                    <div className="issue-card critical">
                                        <div className="issue-header">
                                            <Activity size={18} />
                                            <span>链路中断</span>
                                        </div>
                                        <div className="issue-count">{analysis.link_status.summary.links_down}</div>
                                        <div className="issue-desc">链路处于 Down 状态</div>
                                        <button onClick={() => navigateToTab('link')} className="view-details-btn">
                                            查看详情
                                        </button>
                                    </div>
                                )}

                                {/* Hot Ports */}
                                {analysis.temperature?.hot_ports?.length > 0 && (
                                    <div className="issue-card critical">
                                        <div className="issue-header">
                                            <Thermometer size={18} />
                                            <span>高温告警</span>
                                        </div>
                                        <div className="issue-count">{analysis.temperature.hot_ports.length}</div>
                                        <div className="issue-desc">端口温度 &gt; 60°C</div>
                                        <button onClick={() => navigateToTab('temp')} className="view-details-btn">
                                            查看详情
                                        </button>
                                    </div>
                                )}

                                {/* No Critical Issues */}
                                {!analysis.ber_analysis?.critical_ports?.length &&
                                    !analysis.link_status?.summary?.links_down &&
                                    !analysis.temperature?.hot_ports?.length && (
                                        <div className="no-issues">
                                            <CheckCircle size={24} color="#22c55e" />
                                            <span>未发现严重问题</span>
                                        </div>
                                    )}
                            </div>
                        </div>

                        {/* Warning Issues */}
                        <div className="issues-warning">
                            <h3 style={{ color: '#eab308', marginBottom: '16px' }}>
                                <AlertTriangle size={18} style={{ marginRight: '8px' }} />
                                警告问题 (Warning Issues)
                            </h3>
                            <div className="issue-cards">
                                {/* Warning BER Ports */}
                                {analysis.ber_analysis?.warning_ports?.length > 0 && (
                                    <div className="issue-card warning">
                                        <div className="issue-header">
                                            <TrendingUp size={18} />
                                            <span>BER 警告</span>
                                        </div>
                                        <div className="issue-count">{analysis.ber_analysis.warning_ports.length}</div>
                                        <div className="issue-desc">端口 BER &gt; 1e-9</div>
                                        <button onClick={() => navigateToTab('ber')} className="view-details-btn">
                                            查看详情
                                        </button>
                                    </div>
                                )}

                                {/* Error Recovery Events */}
                                {analysis.link_status?.summary?.error_recovery_events > 0 && (
                                    <div className="issue-card warning">
                                        <div className="issue-header">
                                            <Activity size={18} />
                                            <span>错误恢复事件</span>
                                        </div>
                                        <div className="issue-count">{analysis.link_status.summary.error_recovery_events}</div>
                                        <div className="issue-desc">链路错误恢复计数器 &gt; 0</div>
                                        <button onClick={() => navigateToTab('link')} className="view-details-btn">
                                            查看详情
                                        </button>
                                    </div>
                                )}

                                {/* Congested Ports */}
                                {analysis.performance?.summary?.congested_ports > 0 && (
                                    <div className="issue-card warning">
                                        <div className="issue-header">
                                            <Zap size={18} />
                                            <span>网络拥塞</span>
                                        </div>
                                        <div className="issue-count">{analysis.performance.summary.congested_ports}</div>
                                        <div className="issue-desc">端口发送等待时间过高</div>
                                        <button onClick={() => navigateToTab('performance')} className="view-details-btn">
                                            查看详情
                                        </button>
                                    </div>
                                )}

                                {/* Port Errors */}
                                {analysis.port_errors?.error_ports?.length > 0 && (
                                    <div className="issue-card warning">
                                        <div className="issue-header">
                                            <AlertTriangle size={18} />
                                            <span>端口错误</span>
                                        </div>
                                        <div className="issue-count">{analysis.port_errors.error_ports.length}</div>
                                        <div className="issue-desc">多种错误类型</div>
                                        <button onClick={() => navigateToTab('errors')} className="view-details-btn">
                                            查看详情
                                        </button>
                                    </div>
                                )}

                                {/* No Warning Issues */}
                                {!analysis.ber_analysis?.warning_ports?.length &&
                                    !analysis.link_status?.summary?.error_recovery_events &&
                                    !analysis.performance?.summary?.congested_ports &&
                                    !analysis.port_errors?.error_ports?.length && (
                                        <div className="no-issues">
                                            <CheckCircle size={24} color="#22c55e" />
                                            <span>未发现警告问题</span>
                                        </div>
                                    )}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Health Score Dashboard */}
            {analysis.health_score && (
                <div className="analysis-section health-dashboard">
                    <div className="section-header" onClick={() => toggleSection('health')}>
                        <h2 className="section-title">
                            <Award size={20} />
                            Network Health Score
                        </h2>
                        {expandedSections.health ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                    </div>

                    {expandedSections.health && (
                        <div className="section-content">
                            <div className="health-overview">
                                <div className="health-score-card">
                                    <div className="score-circle" style={{ borderColor: getHealthColor(analysis.health_score.overall_score) }}>
                                        <div className="score-value" style={{ color: getHealthColor(analysis.health_score.overall_score) }}>
                                            {analysis.health_score.overall_score}
                                        </div>
                                        <div className="score-label">Overall Score</div>
                                    </div>
                                    <div className="score-details">
                                        <div className="score-grade" style={{ color: getHealthColor(analysis.health_score.overall_score) }}>
                                            Grade: {analysis.health_score.grade}
                                        </div>
                                        <div className="score-status">{analysis.health_score.status}</div>
                                    </div>
                                </div>

                                <div className="health-breakdown">
                                    {Object.entries(analysis.health_score.scores).map(([key, value]) => (
                                        <div key={key} className="health-metric">
                                            <div className="metric-header">
                                                <span className="metric-name">{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                                                <span className="metric-score" style={{ color: getHealthColor(value) }}>{value.toFixed(1)}</span>
                                            </div>
                                            <div className="metric-bar">
                                                <div
                                                    className="metric-bar-fill"
                                                    style={{
                                                        width: `${value}%`,
                                                        backgroundColor: getHealthColor(value)
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Overview Section */}
            <div className="analysis-section">
                <div className="section-header" onClick={() => toggleSection('overview')}>
                    <h2 className="section-title">
                        <Activity size={20} />
                        UFM Network Overview
                    </h2>
                    {expandedSections.overview ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </div>

                {expandedSections.overview && (
                    <div className="section-content">
                        <div className="stats-grid">
                            <div className="stat-card">
                                <div className="stat-icon" style={{ backgroundColor: '#3b82f620' }}>
                                    <Activity size={24} color="#3b82f6" />
                                </div>
                                <div className="stat-info">
                                    <div className="stat-label">Total Ports</div>
                                    <div className="stat-value">{load_info?.rows?.toLocaleString() || 0}</div>
                                </div>
                            </div>
                            <div className="stat-card">
                                <div className="stat-icon" style={{ backgroundColor: '#8b5cf620' }}>
                                    <BarChart3 size={24} color="#8b5cf6" />
                                </div>
                                <div className="stat-info">
                                    <div className="stat-label">Unique Nodes</div>
                                    <div className="stat-value">{load_info?.unique_nodes?.toLocaleString() || 0}</div>
                                </div>
                            </div>
                            <div className="stat-card">
                                <div className="stat-icon" style={{ backgroundColor: '#10b98120' }}>
                                    <Zap size={24} color="#10b981" />
                                </div>
                                <div className="stat-info">
                                    <div className="stat-label">Unique Hosts</div>
                                    <div className="stat-value">{load_info?.unique_hosts?.toLocaleString() || 0}</div>
                                </div>
                            </div>
                            <div className="stat-card">
                                <div className="stat-icon" style={{ backgroundColor: '#f59e0b20' }}>
                                    <Cable size={24} color="#f59e0b" />
                                </div>
                                <div className="stat-info">
                                    <div className="stat-label">Data Fields</div>
                                    <div className="stat-value">{load_info?.columns || 0}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}

export default UFMOverview
