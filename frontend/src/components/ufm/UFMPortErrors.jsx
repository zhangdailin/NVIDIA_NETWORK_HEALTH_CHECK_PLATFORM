import { useState } from 'react'
import { AlertTriangle, ChevronUp, ChevronDown } from 'lucide-react'
import DataTable from '../../DataTable'

function UFMPortErrors({ portErrorData }) {
    const [expandedSections, setExpandedSections] = useState({
        errorPorts: true,
    })

    const toggleSection = (section) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }))
    }

    if (!portErrorData) return null

    return (
        <div className="analysis-section">
            <h2 className="section-title">
                <AlertTriangle size={20} />
                Port Error Counters
            </h2>

            <div className="error-summary">
                {Object.entries(portErrorData.summary).map(([key, value]) => (
                    <div key={key} className="error-metric">
                        <h3>{key}</h3>
                        <div className="error-stats">
                            <div className="error-stat-item">
                                <span className="error-label">Ports with Errors:</span>
                                <span className="error-value">{value.ports_with_errors}</span>
                            </div>
                            <div className="error-stat-item">
                                <span className="error-label">Total Errors:</span>
                                <span className="error-value">{value.total_errors.toLocaleString()}</span>
                            </div>
                            <div className="error-stat-item">
                                <span className="error-label">Max Errors:</span>
                                <span className="error-value">{value.max_errors.toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Error Ports Table */}
            {portErrorData.error_ports?.length > 0 && (
                <div className="error-ports-section">
                    <div
                        className="subsection-header"
                        onClick={() => toggleSection('errorPorts')}
                        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}
                    >
                        <h3 style={{ color: '#eab308', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                            <AlertTriangle size={18} />
                            错误端口 ({portErrorData.error_ports.length} 个)
                        </h3>
                        {expandedSections.errorPorts ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>

                    {expandedSections.errorPorts && (
                        <DataTable
                            data={portErrorData.error_ports}
                            title="Error Ports"
                        />
                    )}
                </div>
            )}
        </div>
    )
}

export default UFMPortErrors
