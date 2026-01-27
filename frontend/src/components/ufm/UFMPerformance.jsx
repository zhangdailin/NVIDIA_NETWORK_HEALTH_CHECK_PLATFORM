import { useState } from 'react'
import { Zap, ChevronUp, ChevronDown } from 'lucide-react'
import DataTable from '../../DataTable'

function UFMPerformance({ performanceData }) {
    const [expandedSections, setExpandedSections] = useState({
        perfCongestion: true,
    })

    // Helper function to format large numbers
    const formatNumber = (value) => {
        if (!value) return '0'
        if (value >= 1e12) return `${(value / 1e12).toFixed(2)}T`
        if (value >= 1e9) return `${(value / 1e9).toFixed(2)}G`
        if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`
        if (value >= 1e3) return `${(value / 1e3).toFixed(2)}K`
        return value.toLocaleString()
    }

    const toggleSection = (section) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }))
    }

    if (!performanceData) return null

    return (
        <div className="analysis-section">
            <h2 className="section-title">
                <Zap size={20} />
                Performance Analysis
            </h2>

            {/* Traffic Statistics */}
            {performanceData.traffic_stats && Object.keys(performanceData.traffic_stats).length > 0 && (
                <div className="traffic-stats-section">
                    <h3>Traffic Statistics</h3>
                    <div className="traffic-grid">
                        {Object.entries(performanceData.traffic_stats).map(([key, stats]) => (
                            <div key={key} className="traffic-card">
                                <h4>{key}</h4>
                                <div className="traffic-metrics">
                                    <div className="traffic-metric">
                                        <span className="metric-label">Total:</span>
                                        <span className="metric-value">{formatNumber(stats.total)}</span>
                                    </div>
                                    <div className="traffic-metric">
                                        <span className="metric-label">Average:</span>
                                        <span className="metric-value">{formatNumber(stats.average)}</span>
                                    </div>
                                    <div className="traffic-metric">
                                        <span className="metric-label">Max:</span>
                                        <span className="metric-value">{formatNumber(stats.max)}</span>
                                    </div>
                                    <div className="traffic-metric">
                                        <span className="metric-label">P95:</span>
                                        <span className="metric-value">{formatNumber(stats.p95)}</span>
                                    </div>
                                    <div className="traffic-metric">
                                        <span className="metric-label">P99:</span>
                                        <span className="metric-value">{formatNumber(stats.p99)}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Top Bandwidth Ports */}
            {performanceData.top_bandwidth_ports?.length > 0 && (
                <div className="bandwidth-section">
                    <h3 style={{ color: '#3b82f6' }}>Top Bandwidth Ports ({performanceData.top_bandwidth_ports.length})</h3>
                    <DataTable
                        data={performanceData.top_bandwidth_ports}
                        title="Top Bandwidth Ports"
                    />
                </div>
            )}

            {/* Congestion Ports */}
            {performanceData.congestion_ports?.length > 0 && (
                <div className="congestion-section">
                    <div
                        className="subsection-header"
                        onClick={() => toggleSection('perfCongestion')}
                        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}
                    >
                        <h3 style={{ color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                            <Zap size={18} />
                            拥塞端口 ({performanceData.congestion_ports.length})
                        </h3>
                        {expandedSections.perfCongestion ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>

                    {expandedSections.perfCongestion && (
                        <DataTable
                            data={performanceData.congestion_ports}
                            title="Congestion Ports"
                        />
                    )}
                </div>
            )}
        </div>
    )
}

export default UFMPerformance
