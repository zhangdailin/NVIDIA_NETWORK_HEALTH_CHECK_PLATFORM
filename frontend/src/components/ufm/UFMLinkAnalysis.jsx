import { useState } from 'react'
import { Activity, XCircle, AlertTriangle, CheckCircle, ChevronUp, ChevronDown } from 'lucide-react'
import DataTable from '../../DataTable'

function UFMLinkAnalysis({ linkData }) {
    const [expandedSections, setExpandedSections] = useState({
        linkDown: true,
    })

    const toggleSection = (section) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }))
    }

    if (!linkData) return null

    return (
        <div className="analysis-section">
            <h2 className="section-title">
                <Activity size={20} />
                Link Status
            </h2>

            <div className="link-summary">
                {linkData.summary.links_down > 0 && (
                    <div className="alert-box" style={{ borderLeftColor: '#ef4444' }}>
                        <XCircle size={20} color="#ef4444" />
                        <div>
                            <strong>{linkData.summary.links_down} Links Down</strong>
                            <p>Network connectivity issues detected</p>
                        </div>
                    </div>
                )}

                {linkData.summary.error_recovery_events > 0 && (
                    <div className="alert-box" style={{ borderLeftColor: '#eab308' }}>
                        <AlertTriangle size={20} color="#eab308" />
                        <div>
                            <strong>{linkData.summary.error_recovery_events} Error Recovery Events</strong>
                            <p>Links experienced recovery events</p>
                        </div>
                    </div>
                )}

                {linkData.summary.links_down === 0 &&
                    linkData.summary.error_recovery_events === 0 && (
                        <div className="alert-box" style={{ borderLeftColor: '#22c55e' }}>
                            <CheckCircle size={20} color="#22c55e" />
                            <div>
                                <strong>All Links Operational</strong>
                                <p>No link issues detected</p>
                            </div>
                        </div>
                    )}
            </div>

            {/* Down Links Table */}
            {linkData.down_links?.length > 0 && (
                <div className="down-links-section">
                    <div
                        className="subsection-header"
                        onClick={() => toggleSection('linkDown')}
                        style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}
                    >
                        <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
                            <XCircle size={18} />
                            中断链路 ({linkData.down_links.length} 个)
                        </h3>
                        {expandedSections.linkDown ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>

                    {expandedSections.linkDown && (
                        <DataTable
                            data={linkData.down_links}
                            title="Down Links"
                        />
                    )}
                </div>
            )}
        </div>
    )
}

export default UFMLinkAnalysis
