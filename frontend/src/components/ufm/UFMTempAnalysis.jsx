import { useState } from 'react'
import { Thermometer, ChevronUp, ChevronDown } from 'lucide-react'
import DataTable from '../../DataTable'

function UFMTempAnalysis({ tempData }) {
    const [expandedSections, setExpandedSections] = useState({
        tempHot: true,
    })

    const toggleSection = (section) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }))
    }

    if (!tempData || !tempData.summary) return null

    return (
        <div className="analysis-section">
            <h2 className="section-title">
                <Thermometer size={20} />
                Temperature Monitoring
            </h2>

            <div className="temp-summary">
                <div className="temp-stat">
                    <span className="temp-label">Average Temperature</span>
                    <span className="temp-value">{tempData.summary.avg_temp?.toFixed(1)}°C</span>
                </div>
                <div className="temp-stat">
                    <span className="temp-label">Maximum Temperature</span>
                    <span className="temp-value" style={{ color: tempData.summary.max_temp > 60 ? '#ef4444' : '#22c55e' }}>
                        {tempData.summary.max_temp?.toFixed(1)}°C
                    </span>
                </div>
                <div className="temp-stat">
                    <span className="temp-label">Minimum Temperature</span>
                    <span className="temp-value">{tempData.summary.min_temp?.toFixed(1)}°C</span>
                </div>
                <div className="temp-stat">
                    <span className="temp-label">Ports Monitored</span>
                    <span className="temp-value">{tempData.summary.ports_monitored?.toLocaleString()}</span>
                </div>
            </div>

            {/* Hot Ports */}
            {tempData.hot_ports?.length > 0 && (
                <div className="hot-ports-section">
                    <div
                        className="subsection-header"
                        onClick={() => toggleSection('tempHot')}
                        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}
                    >
                        <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                            <Thermometer size={18} />
                            高温端口详情 ({tempData.hot_ports.length} 个端口)
                        </h3>
                        {expandedSections.tempHot ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>

                    {expandedSections.tempHot && (
                        <DataTable
                            data={tempData.hot_ports}
                            title="Hot Ports"
                        />
                    )}
                </div>
            )}
        </div>
    )
}

export default UFMTempAnalysis
