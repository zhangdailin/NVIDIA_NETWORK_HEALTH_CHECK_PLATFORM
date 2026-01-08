import { useState } from 'react'
import {
  ERROR_KNOWLEDGE_BASE,
  SEVERITY_LEVELS,
  ISSUE_CATEGORIES,
  getErrorExplanation,
  getSeverityInfo,
  getCategoryInfo,
  identifyIssueType,
  searchKnowledgeBase,
  getIssueTypesByCategory
} from './ErrorExplanations'
import {
  AlertCircle,
  AlertTriangle,
  XCircle,
  CheckCircle,
  Info,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Clock,
  Wrench,
  BookOpen,
  Search
} from 'lucide-react'

const getSeverityIcon = (severity) => {
  switch (severity) {
    case 'critical': return <XCircle size={16} color="#ef4444" />
    case 'warning': return <AlertTriangle size={16} color="#f59e0b" />
    case 'info': return <Info size={16} color="#3b82f6" />
    default: return <CheckCircle size={16} color="#22c55e" />
  }
}

/**
 * 问题详情卡片组件
 * Issue Detail Card Component
 */
export function IssueDetailCard({ issueType, isExpanded = false, onToggle, showActions = true }) {
  const [expanded, setExpanded] = useState(isExpanded)
  const kb = getErrorExplanation(issueType)
  const severityInfo = getSeverityInfo(kb.severity)
  const categoryInfo = getCategoryInfo(kb.category)

  const handleToggle = () => {
    const newState = !expanded
    setExpanded(newState)
    if (onToggle) onToggle(newState)
  }

  return (
    <div
      className="issue-detail-card"
      style={{
        border: `1px solid ${severityInfo.borderColor}`,
        background: severityInfo.bgColor,
        borderRadius: '8px',
        marginBottom: '12px',
        overflow: 'hidden'
      }}
    >
      {/* Header */}
      <div
        onClick={handleToggle}
        style={{
          padding: '12px 16px',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: expanded ? `1px solid ${severityInfo.borderColor}` : 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {getSeverityIcon(kb.severity)}
          <div>
            <h4 style={{ margin: 0, fontSize: '1rem', color: '#1f2937' }}>
              {kb.title}
            </h4>
            <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
              {kb.titleEn}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              background: severityInfo.color,
              color: '#fff'
            }}
          >
            {severityInfo.label}
          </span>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div style={{ padding: '16px', background: '#fff' }}>
          {/* Why it matters */}
          <div style={{ marginBottom: '16px' }}>
            <h5 style={{ margin: '0 0 8px 0', color: '#374151', fontSize: '0.9rem' }}>
              <AlertCircle size={14} style={{ marginRight: '6px' }} />
              为什么重要 / Why it Matters
            </h5>
            <p style={{ margin: 0, color: '#4b5563', fontSize: '0.9rem', lineHeight: '1.6' }}>
              {kb.why_it_matters}
            </p>
            <p style={{ margin: '4px 0 0 0', color: '#6b7280', fontSize: '0.85rem', fontStyle: 'italic' }}>
              {kb.why_it_matters_en}
            </p>
          </div>

          {/* Threshold */}
          {kb.threshold && (
            <div style={{
              marginBottom: '16px',
              padding: '8px 12px',
              background: '#f3f4f6',
              borderRadius: '4px',
              fontSize: '0.85rem'
            }}>
              <strong>阈值 / Threshold:</strong> {kb.threshold}
            </div>
          )}

          {/* Likely Causes */}
          <div style={{ marginBottom: '16px' }}>
            <h5 style={{ margin: '0 0 8px 0', color: '#374151', fontSize: '0.9rem' }}>
              可能原因 / Likely Causes
            </h5>
            <ul style={{ margin: 0, paddingLeft: '20px', color: '#4b5563', fontSize: '0.85rem' }}>
              {kb.likely_causes?.map((cause, idx) => (
                <li key={idx} style={{ marginBottom: '4px' }}>
                  {cause}
                  {kb.likely_causes_en?.[idx] && (
                    <span style={{ color: '#9ca3af', marginLeft: '8px' }}>
                      ({kb.likely_causes_en[idx]})
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>

          {/* Recommended Actions */}
          {showActions && kb.recommended_actions && (
            <div style={{ marginBottom: '16px' }}>
              <h5 style={{ margin: '0 0 8px 0', color: '#374151', fontSize: '0.9rem' }}>
                <Wrench size={14} style={{ marginRight: '6px' }} />
                建议操作 / Recommended Actions
              </h5>
              <ol style={{ margin: 0, paddingLeft: '20px', color: '#4b5563', fontSize: '0.85rem' }}>
                {kb.recommended_actions.map((action, idx) => (
                  <li key={idx} style={{ marginBottom: '6px' }}>
                    {action}
                    {kb.recommended_actions_en?.[idx] && (
                      <div style={{ color: '#9ca3af', fontSize: '0.8rem' }}>
                        {kb.recommended_actions_en[idx]}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* Impact */}
          {kb.impact && (
            <div style={{ marginBottom: '16px' }}>
              <h5 style={{ margin: '0 0 8px 0', color: '#374151', fontSize: '0.9rem' }}>
                影响分析 / Impact Analysis
              </h5>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {Object.entries(kb.impact).map(([key, value]) => (
                  <span
                    key={key}
                    style={{
                      padding: '4px 8px',
                      background: value === 'critical' ? '#fef2f2' :
                        value === 'high' ? '#fffbeb' :
                          value === 'medium' ? '#f3f4f6' : '#f0fdf4',
                      border: `1px solid ${value === 'critical' ? '#fecaca' :
                        value === 'high' ? '#fed7aa' :
                          value === 'medium' ? '#d1d5db' : '#bbf7d0'}`,
                      borderRadius: '4px',
                      fontSize: '0.8rem'
                    }}
                  >
                    {key}: {value}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* MTTR & Tools */}
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', marginBottom: '16px' }}>
            {kb.mttr_estimate && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#6b7280' }}>
                <Clock size={14} />
                <span>预计修复时间: {kb.mttr_estimate}</span>
              </div>
            )}
            {kb.tools_needed?.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: '#6b7280' }}>
                <Wrench size={14} />
                <span>所需工具: {kb.tools_needed.join(', ')}</span>
              </div>
            )}
          </div>

          {/* Reference */}
          {kb.reference && (
            <div style={{
              padding: '8px 12px',
              background: '#f3f4f6',
              borderRadius: '4px',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <BookOpen size={14} />
              <span>参考文档: {kb.reference}</span>
              {kb.reference_url && (
                <a
                  href={kb.reference_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#3b82f6', display: 'flex', alignItems: 'center' }}
                >
                  <ExternalLink size={14} />
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * 问题摘要卡片（简洁版）
 * Issue Summary Card (Compact version)
 */
export function IssueSummaryCard({ issueType, onClick }) {
  const kb = getErrorExplanation(issueType)
  const severityInfo = getSeverityInfo(kb.severity)

  return (
    <div
      onClick={onClick}
      style={{
        padding: '12px',
        border: `1px solid ${severityInfo.borderColor}`,
        borderLeft: `4px solid ${severityInfo.color}`,
        borderRadius: '4px',
        cursor: 'pointer',
        marginBottom: '8px',
        background: '#fff',
        transition: 'box-shadow 0.2s'
      }}
      onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)'}
      onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {getSeverityIcon(kb.severity)}
          <span style={{ fontWeight: 500, color: '#1f2937' }}>{kb.title}</span>
        </div>
        <span style={{
          padding: '2px 6px',
          borderRadius: '3px',
          fontSize: '0.7rem',
          background: severityInfo.color,
          color: '#fff'
        }}>
          {severityInfo.labelCn}
        </span>
      </div>
      <p style={{ margin: '8px 0 0 24px', fontSize: '0.85rem', color: '#6b7280' }}>
        {kb.why_it_matters?.substring(0, 100)}...
      </p>
    </div>
  )
}

/**
 * 知识库浏览器组件
 * Knowledge Base Browser Component
 */
export function KnowledgeBaseBrowser() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [expandedIssue, setExpandedIssue] = useState(null)

  const groupedIssues = getIssueTypesByCategory()
  const searchResults = searchQuery ? searchKnowledgeBase(searchQuery) : []

  const displayIssues = searchQuery
    ? searchResults
    : selectedCategory
      ? groupedIssues[selectedCategory] || []
      : Object.values(groupedIssues).flat()

  return (
    <div style={{ padding: '16px' }}>
      {/* Search Bar */}
      <div style={{ marginBottom: '16px', display: 'flex', gap: '12px' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }} />
          <input
            type="text"
            placeholder="搜索问题... / Search issues..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 12px 10px 36px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '0.9rem'
            }}
          />
        </div>
      </div>

      {/* Category Filters */}
      <div style={{ marginBottom: '16px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button
          onClick={() => setSelectedCategory(null)}
          style={{
            padding: '6px 12px',
            border: `1px solid ${selectedCategory === null ? '#3b82f6' : '#d1d5db'}`,
            background: selectedCategory === null ? '#eff6ff' : '#fff',
            borderRadius: '16px',
            fontSize: '0.85rem',
            cursor: 'pointer',
            color: selectedCategory === null ? '#3b82f6' : '#4b5563'
          }}
        >
          全部 ({Object.values(groupedIssues).flat().length})
        </button>
        {Object.entries(ISSUE_CATEGORIES).map(([key, cat]) => (
          <button
            key={key}
            onClick={() => setSelectedCategory(key)}
            style={{
              padding: '6px 12px',
              border: `1px solid ${selectedCategory === key ? '#3b82f6' : '#d1d5db'}`,
              background: selectedCategory === key ? '#eff6ff' : '#fff',
              borderRadius: '16px',
              fontSize: '0.85rem',
              cursor: 'pointer',
              color: selectedCategory === key ? '#3b82f6' : '#4b5563'
            }}
          >
            {cat.labelCn} ({groupedIssues[key]?.length || 0})
          </button>
        ))}
      </div>

      {/* Issue List */}
      <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
        {displayIssues.length === 0 ? (
          <p style={{ color: '#9ca3af', textAlign: 'center', padding: '24px' }}>
            未找到匹配的问题 / No matching issues found
          </p>
        ) : (
          displayIssues.map((issue) => (
            <IssueDetailCard
              key={issue.key}
              issueType={issue.key}
              isExpanded={expandedIssue === issue.key}
              onToggle={(expanded) => setExpandedIssue(expanded ? issue.key : null)}
            />
          ))
        )}
      </div>
    </div>
  )
}

/**
 * 数据行问题提示组件
 * Data Row Issue Tooltip Component
 */
export function DataRowIssueTooltip({ row, dataType }) {
  const issueType = identifyIssueType(row, dataType)

  if (!issueType) return null

  const kb = getErrorExplanation(issueType)
  const severityInfo = getSeverityInfo(kb.severity)

  return (
    <div style={{
      padding: '8px',
      background: severityInfo.bgColor,
      border: `1px solid ${severityInfo.borderColor}`,
      borderRadius: '4px',
      fontSize: '0.8rem'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
        {getSeverityIcon(kb.severity)}
        <strong>{kb.title}</strong>
      </div>
      <p style={{ margin: 0, color: '#4b5563' }}>{kb.why_it_matters}</p>
    </div>
  )
}

export default KnowledgeBaseBrowser
