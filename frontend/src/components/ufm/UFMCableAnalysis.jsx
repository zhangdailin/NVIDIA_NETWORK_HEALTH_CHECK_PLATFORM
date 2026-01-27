import { Cable } from 'lucide-react'

function UFMCableAnalysis({ cableData }) {
    if (!cableData) return null

    return (
        <div className="analysis-section">
            <h2 className="section-title">
                <Cable size={20} />
                Cable Information
            </h2>

            <div className="cable-summary">
                {cableData.summary?.cables_identified && (
                    <div className="cable-stat">
                        <span className="cable-label">Cables Identified</span>
                        <span className="cable-value">{cableData.summary.cables_identified.toLocaleString()}</span>
                    </div>
                )}
            </div>

            {/* Cable Types */}
            {cableData.cable_types?.length > 0 && (
                <div className="cable-types">
                    <h3>Cable Types Distribution</h3>
                    <div className="cable-type-list">
                        {cableData.cable_types.map((item, idx) => (
                            <div key={idx} className="cable-type-item">
                                <span className="cable-type-name">{item.type || 'Unknown'}</span>
                                <span className="cable-type-count">{item.count.toLocaleString()}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Cable Lengths */}
            {cableData.cable_lengths?.length > 0 && (
                <div className="cable-lengths">
                    <h3>Cable Lengths Distribution</h3>
                    <div className="cable-length-list">
                        {cableData.cable_lengths.map((item, idx) => (
                            <div key={idx} className="cable-length-item">
                                <span className="cable-length-name">{item.length || 'Unknown'}</span>
                                <span className="cable-length-count">{item.count.toLocaleString()}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

export default UFMCableAnalysis
