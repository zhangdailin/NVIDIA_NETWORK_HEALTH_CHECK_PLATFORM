import { useState, useMemo } from 'react'
import { Database, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import DataTable from './DataTable'
import {
  ensureArray,
  formatCount,
  SEVERITY_ORDER,
  SEVERITY_LABEL,
  SEVERITY_CHIP_STYLES,
  annotateRows,
  extractTopRows,
  filterBySeverity,
  countBySeverity,
} from './analysisUtils'

/**
 * 通用分析页面组件
 * 统一所有标签页的布局和交互模式
 */
function UnifiedAnalysisPage({
  // 页面信息
  title,
  description,
  emptyMessage = '暂无数据',
  emptyHint = '请确认采集的数据包中包含相关信息表格。',

  // 数据
  data = [],
  summary = null,
  totalRows = null,

  // 指标卡片配置
  metricCards = [],

  // 严重度分析函数
  getSeverity = null,
  getIssueReason = null,

  // 是否显示信息级别
  showInfoLevel = false,

  // Top N 预览配置
  topPreviewLimit = 10,
  previewColumns = null, // [{key, label, render?}]
  defaultPreviewColumns = ['IssueSeverity', 'IssueReason', 'Node Name', 'PortNumber'],

  // DataTable 配置
  preferredColumns = [],
  searchPlaceholder = '搜索节点名、GUID、端口号...',
  pageSize = 20,

  // 自定义渲染
  renderCustomSection = null,
  renderBeforeTable = null,
  extraSummary = null, // 额外的摘要信息（JSX）
}) {
  const [selectedSeverity, setSelectedSeverity] = useState('all')

  const rows = useMemo(() => ensureArray(data), [data])

  // 添加严重度标注
  const annotatedRows = useMemo(() => {
    return annotateRows(rows, getSeverity, getIssueReason)
  }, [rows, getSeverity, getIssueReason])

  // 统计各严重度数量
  const severityCounts = useMemo(() => {
    return countBySeverity(annotatedRows, (row) => row.__severity)
  }, [annotatedRows])

  // 筛选后的行
  const filteredRows = useMemo(() => {
    return filterBySeverity(annotatedRows, selectedSeverity)
  }, [annotatedRows, selectedSeverity])

  // Top N 预览行
  const topCriticalRows = useMemo(() => extractTopRows(annotatedRows, 'critical', topPreviewLimit), [annotatedRows, topPreviewLimit])
  const topWarningRows = useMemo(() => extractTopRows(annotatedRows, 'warning', topPreviewLimit), [annotatedRows, topPreviewLimit])
  const topInfoRows = useMemo(() => extractTopRows(annotatedRows, 'info', topPreviewLimit), [annotatedRows, topPreviewLimit])

  // 处理筛选条点击
  const handleChipClick = (severity) => {
    setSelectedSeverity(prev => prev === severity ? 'all' : severity)
  }

  // 空数据状态
  if (rows.length === 0) {
    return (
      <div className="osc-empty">
        <p>{emptyMessage}</p>
        <p style={{ margin: 0, color: '#6b7280' }}>{emptyHint}</p>
      </div>
    )
  }

  // 构建默认指标卡片
  const displayMetricCards = metricCards.length > 0 ? metricCards : [
    {
      key: 'total',
      label: '总数',
      value: totalRows ?? rows.length,
      description: '全部检测项',
      icon: Database,
    },
    {
      key: 'critical',
      label: '严重问题',
      value: severityCounts.critical,
      description: '需要立即处理',
      icon: AlertTriangle,
    },
    {
      key: 'warning',
      label: '警告',
      value: severityCounts.warning,
      description: '建议关注',
      icon: AlertTriangle,
    },
    {
      key: 'healthy',
      label: '健康',
      value: severityCounts.ok + (showInfoLevel ? 0 : severityCounts.info),
      description: '无异常',
      icon: CheckCircle,
    },
  ]

  // 构建严重度筛选条
  const severityChips = [
    {
      key: 'critical',
      ...SEVERITY_CHIP_STYLES.critical,
      count: severityCounts.critical,
      previewCount: topCriticalRows.length,
    },
    {
      key: 'warning',
      ...SEVERITY_CHIP_STYLES.warning,
      count: severityCounts.warning,
      previewCount: topWarningRows.length,
    },
  ]

  if (showInfoLevel) {
    severityChips.push({
      key: 'info',
      ...SEVERITY_CHIP_STYLES.info,
      count: severityCounts.info,
      previewCount: topInfoRows.length,
    })
  }

  severityChips.push({
    key: 'ok',
    ...SEVERITY_CHIP_STYLES.ok,
    count: severityCounts.ok + (showInfoLevel ? 0 : severityCounts.info),
    previewCount: null,
  })

  // 获取预览列配置
  const getPreviewCols = () => {
    if (previewColumns) return previewColumns
    return defaultPreviewColumns.map(key => ({
      key,
      label: key === 'IssueSeverity' ? '严重度' :
             key === 'IssueReason' ? '问题描述' :
             key === 'Node Name' ? '节点' :
             key === 'PortNumber' ? '端口' : key,
    }))
  }

  const previewCols = getPreviewCols()

  // 渲染预览行单元格
  const renderPreviewCell = (row, col) => {
    if (col.render) return col.render(row)
    const value = row[col.key]
    if (value === null || value === undefined) return 'N/A'
    return String(value)
  }

  // 渲染 Top N 预览表
  const renderTopPreview = (topRows, severity, totalCount) => {
    if (topRows.length === 0) return null

    const style = SEVERITY_CHIP_STYLES[severity]
    const labelMap = { critical: '严重问题', warning: '警告问题', info: '信息提示' }

    return (
      <div className="osc-section">
        <div className="osc-section-header">
          <div>
            <h3>{labelMap[severity]}预览 (Top {topRows.length})</h3>
            <p>按严重程度排序显示的前 {topPreviewLimit} 条记录</p>
          </div>
          <span className="osc-section-tag">
            展示 {topRows.length} / 总计 {formatCount(totalCount)}
          </span>
        </div>
        <div className="osc-table-wrapper">
          <table className="osc-table">
            <thead>
              <tr>
                {previewCols.map(col => (
                  <th key={col.key}>{col.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {topRows.map((row, idx) => (
                <tr key={`${severity}-${row.__originalIndex ?? idx}`}>
                  {previewCols.map((col, colIdx) => (
                    <td
                      key={col.key}
                      style={
                        col.key === 'IssueSeverity'
                          ? {}
                          : col.key === 'IssueReason'
                            ? { color: style.color, fontWeight: 'bold' }
                            : {}
                      }
                    >
                      {col.key === 'IssueSeverity' ? (
                        <>
                          <span className={`osc-severity-dot ${style.dotClass}`} />
                          {row.IssueSeverity}
                        </>
                      ) : (
                        renderPreviewCell(row, col)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return (
    <div className="link-oscillation">
      {/* 指标卡片网格 */}
      <div className="osc-metric-grid">
        {displayMetricCards.map(card => {
          const Icon = card.icon || Database
          return (
            <div key={card.key} className="osc-metric-card">
              <div className="osc-metric-top">
                <div className="osc-metric-icon">
                  <Icon size={18} />
                </div>
                <span className="osc-metric-label">{card.label}</span>
              </div>
              <div className="osc-metric-value">{formatCount(card.value)}</div>
              <p className="osc-metric-desc">{card.description}</p>
            </div>
          )
        })}
      </div>

      {/* 额外摘要信息 */}
      {extraSummary}

      {/* 严重度筛选条 */}
      <div className="osc-chip-row">
        {severityChips.map(chip => (
          <div
            key={chip.key}
            className={`osc-chip ${selectedSeverity === chip.key ? 'osc-chip-selected' : ''}`}
            style={{ background: chip.background, color: chip.color, cursor: 'pointer' }}
            onClick={() => handleChipClick(chip.key)}
          >
            <div className="osc-chip-label">{chip.label}</div>
            <div className="osc-chip-value">{formatCount(chip.count)}</div>
            {chip.previewCount !== null && (
              <div className="osc-chip-sub">预览 {chip.previewCount}</div>
            )}
          </div>
        ))}
      </div>

      {/* 自定义区域 */}
      {renderCustomSection && renderCustomSection({ annotatedRows, severityCounts, summary })}

      {/* Top N 预览表 */}
      {renderTopPreview(topCriticalRows, 'critical', severityCounts.critical)}
      {renderTopPreview(topWarningRows, 'warning', severityCounts.warning)}
      {showInfoLevel && renderTopPreview(topInfoRows, 'info', severityCounts.info)}

      {/* 表格前自定义内容 */}
      {renderBeforeTable && renderBeforeTable({ annotatedRows, severityCounts, summary })}

      {/* 完整数据表 */}
      <div className="osc-section">
        <div className="osc-section-header">
          <div>
            <h3>
              完整数据表 (可搜索/可排序)
              {selectedSeverity !== 'all' && (
                <span style={{ marginLeft: '8px', fontSize: '0.85rem', color: '#6b7280' }}>
                  - 已筛选: {SEVERITY_LABEL[selectedSeverity] || selectedSeverity}
                </span>
              )}
            </h3>
            <p>包含完整信息，便于深入分析。点击上方标签可筛选。</p>
          </div>
          <span className="osc-section-tag">
            展示 {filteredRows.length} / 总计 {formatCount(totalRows ?? rows.length)}
          </span>
        </div>
        <DataTable
          rows={filteredRows}
          totalRows={totalRows ?? rows.length}
          searchPlaceholder={searchPlaceholder}
          pageSize={pageSize}
          preferredColumns={['IssueSeverity', 'IssueReason', ...preferredColumns]}
          defaultSortKey="__severityOrder"
        />
      </div>
    </div>
  )
}

export default UnifiedAnalysisPage
