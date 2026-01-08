import { useMemo, useState } from 'react'
import { CheckCircle, AlertTriangle, XCircle, ArrowRight, Filter } from 'lucide-react'
import { HEALTH_CHECK_GROUPS, HEALTH_CHECK_DEFINITIONS, evaluateHealthChecks } from './healthCheckDefinitions'

const STATUS_META = {
  ok: {
    text: 'OK',
    icon: CheckCircle,
    className: 'ok',
    helper: '未检测到异常',
  },
  warning: {
    text: '警告',
    icon: AlertTriangle,
    className: 'warning',
    helper: '存在需关注的问题',
  },
  critical: {
    text: '严重',
    icon: XCircle,
    className: 'critical',
    helper: '存在阻塞或严重故障',
  },
}

const HealthCheckBoard = ({ payload, onSelectTab, resolveTabMeta }) => {
  const [filterMode, setFilterMode] = useState('all')
  const [groupFilter, setGroupFilter] = useState('all')
  const evaluations = useMemo(() => (payload ? evaluateHealthChecks(payload) : {}), [payload])

  if (!payload) {
    return null
  }

  const renderCard = (definition, evaluation) => {
    if (!definition || !evaluation) return null
    const status = STATUS_META[evaluation.status] || STATUS_META.ok
    const Icon = status.icon
    const tabMeta = typeof resolveTabMeta === 'function' ? resolveTabMeta(definition.key) : null
    const TabIcon = tabMeta?.icon

    return (
      <div key={definition.key} className={`health-card status-${status.className}`}>
        <div className="health-card-header">
          <div className="health-card-title">
            {TabIcon && <TabIcon size={16} className="health-card-title-icon" />}
            <div>
              <div className="health-card-name">{definition.label}</div>
              <p className="health-card-desc">{definition.description}</p>
            </div>
          </div>
          <div className={`status-pill status-pill-${status.className}`}>
            <Icon size={16} />
            <span>{status.text}</span>
          </div>
        </div>
        <div className="health-card-body">
          <div className="health-card-stat">
            <span className="stat-label">异常计数</span>
            <strong>{evaluation.issueCount || 0}</strong>
          </div>
          <div className="health-card-stat critical">
            <span className="stat-label">严重</span>
            <strong>{evaluation.criticalCount || 0}</strong>
          </div>
          <div className="health-card-stat warning">
            <span className="stat-label">警告</span>
            <strong>{evaluation.warningCount || 0}</strong>
          </div>
          <div className="health-card-stat muted">
            <span className="stat-label">记录</span>
            <strong>{evaluation.totalRows || 0}</strong>
          </div>
        </div>
        <div className="health-card-footer">
          <span className="status-helper">{status.helper}</span>
          <button
            type="button"
            className="ghost-link"
            onClick={() => onSelectTab?.(definition.key)}
          >
            查看详情 <ArrowRight size={14} />
          </button>
        </div>
      </div>
    )
  }

  const availableGroups = HEALTH_CHECK_GROUPS.filter(group => groupFilter === 'all' || group.key === groupFilter)

  const renderedGroups = availableGroups
    .map(group => {
      const cards = group.checks
        .map(checkKey => {
          const def = HEALTH_CHECK_DEFINITIONS[checkKey]
          const evaluation = evaluations[checkKey]
          if (!def || !evaluation) return null
          if (filterMode === 'issues' && evaluation.status === 'ok') {
            return null
          }
          return renderCard(def, evaluation)
        })
        .filter(Boolean)

      if (!cards.length) {
        return null
      }

      return (
        <div key={group.key} className="health-board-group">
          <div className="health-board-group-header">
            <div>
              <h3>{group.label}</h3>
              <p>{group.description}</p>
            </div>
            <div className="health-board-count">
              {cards.length}/{group.checks.length}
            </div>
          </div>
          <div className="health-card-grid">{cards}</div>
        </div>
      )
    })
    .filter(Boolean)

  return (
    <div className="health-board">
      <div className="health-board-toolbar">
        <div className="toolbar-left">
          <Filter size={16} />
          <span>检查筛选</span>
          <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}>
            <option value="all">全部分组</option>
            {HEALTH_CHECK_GROUPS.map(group => (
              <option key={group.key} value={group.key}>{group.label}</option>
            ))}
          </select>
        </div>
        <div className="toolbar-right">
          <button
            type="button"
            className={filterMode === 'all' ? 'active' : ''}
            onClick={() => setFilterMode('all')}
          >
            全部检查
          </button>
          <button
            type="button"
            className={filterMode === 'issues' ? 'active' : ''}
            onClick={() => setFilterMode('issues')}
          >
            仅异常
          </button>
        </div>
      </div>

      {renderedGroups.length > 0 ? (
        renderedGroups
      ) : (
        <div className="health-board-empty">
          <CheckCircle size={28} />
          <p>所选条件下没有需要关注的问题。</p>
        </div>
      )}
    </div>
  )
}

export default HealthCheckBoard
