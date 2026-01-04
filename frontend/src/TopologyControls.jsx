import { useState } from 'react'
import { Filter, Layers, Info } from 'lucide-react'
import './TopologyControls.css'

function TopologyControls({ onFilterChange }) {
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState({
    nodeTypes: {
      HCA: true,
      LEAF: true,
      SPINE: true,
      CORE: true,
      GPU: true
    },
    healthLevels: {
      healthy: true,
      warning: true,
      critical: true
    }
  })

  const handleNodeTypeChange = (type) => {
    const newFilters = {
      ...filters,
      nodeTypes: {
        ...filters.nodeTypes,
        [type]: !filters.nodeTypes[type]
      }
    }
    setFilters(newFilters)
    onFilterChange?.(newFilters)
  }

  const handleHealthLevelChange = (level) => {
    const newFilters = {
      ...filters,
      healthLevels: {
        ...filters.healthLevels,
        [level]: !filters.healthLevels[level]
      }
    }
    setFilters(newFilters)
    onFilterChange?.(newFilters)
  }

  return (
    <div className="topology-controls">
      <button
        className="control-toggle"
        onClick={() => setShowFilters(!showFilters)}
      >
        <Filter size={16} />
        Filters
      </button>

      {showFilters && (
        <div className="filters-panel">
          <div className="filter-section">
            <h4><Layers size={14} /> Node Types</h4>
            {Object.entries(filters.nodeTypes).map(([type, enabled]) => (
              <label key={type} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={() => handleNodeTypeChange(type)}
                />
                <span>{type}</span>
              </label>
            ))}
          </div>

          <div className="filter-section">
            <h4><Info size={14} /> Health Status</h4>
            {Object.entries(filters.healthLevels).map(([level, enabled]) => (
              <label key={level} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={() => handleHealthLevelChange(level)}
                />
                <span className={`health-${level}`}>
                  {level.charAt(0).toUpperCase() + level.slice(1)}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="legend">
        <h4>Health Legend</h4>
        <div className="legend-items">
          <div className="legend-item">
            <span className="legend-color" style={{backgroundColor: '#22c55e'}}></span>
            <span>Healthy (80-100)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{backgroundColor: '#eab308'}}></span>
            <span>Warning (60-79)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{backgroundColor: '#f97316'}}></span>
            <span>Degraded (40-59)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color" style={{backgroundColor: '#ef4444'}}></span>
            <span>Critical (&lt;40)</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TopologyControls
