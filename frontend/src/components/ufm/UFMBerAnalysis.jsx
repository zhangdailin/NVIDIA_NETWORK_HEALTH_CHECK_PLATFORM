import { useState } from 'react'
import { TrendingUp, XCircle, AlertTriangle, ChevronUp, ChevronDown } from 'lucide-react'
import DataTable from '../../DataTable'

function UFMBerAnalysis({ berData }) {
    const [expandedSections, setExpandedSections] = useState({
        berCritical: true,
        berWarning: true,
    })

    // Helper function to format BER values
    const formatBER = (value) => {
        if (!value || value === 0) return 'N/A'
        return value.toExponential(2)
    }

    const toggleSection = (section) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }))
    }

    if (!berData) return null

    return (
        <div className="analysis-section">
            <h2 className="section-title">
                <TrendingUp size={20} />
                Bit Error Rate (BER) Analysis
            </h2>

            <div className="ber-summary">
                {Object.entries(berData.summary).map(([key, value]) => (
                    <div key={key} className="ber-metric">
                        <h3>{key}</h3>
                        <div className="metric-stats">
                            <div className="metric-item">
                                <span className="metric-label">Ports with Errors:</span>
                                <span className="metric-value">{value.ports_with_errors}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Max BER:</span>
                                <span className="metric-value">{formatBER(value.max_value)}</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Avg BER:</span>
                                <span className="metric-value">{formatBER(value.avg_value)}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Critical Ports */}
            {berData.critical_ports?.length > 0 && (
                <div className="critical-section">
                    <div
                        className="subsection-header"
                        onClick={() => toggleSection('berCritical')}
                        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}
                    >
                        <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                            <XCircle size={18} />
                            严重 BER 错误端口 ({berData.critical_ports.length} 个)
                        </h3>
                        {expandedSections.berCritical ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>

                    {expandedSections.berCritical && (
                        <DataTable
                            data={berData.critical_ports}
                            title="Critical BER Ports"
                        />
                    )}
                </div>
            )}

            {/* Warning Ports */}
            {berData.warning_ports?.length > 0 && (
                <div className="warning-section">
                    <div
                        className="subsection-header"
                        onClick={() => toggleSection('berWarning')}
                        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}
                    >
                        <h3 style={{ color: '#eab308', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                            <AlertTriangle size={18} />
                            BER 警告端口 ({berData.warning_ports.length} 个)
                        </h3>
                        {expandedSections.berWarning ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>

                    {expandedSections.berWarning && (
                        <DataTable
                            data={berData.warning_ports}
                            title="Warning BER Ports"
                        />
                    )}
                </div>
            )}
        </div>
    )
}

export default UFMBerAnalysis
