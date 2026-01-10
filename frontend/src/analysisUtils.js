/**
 * 通用分析工具函数
 * 用于统一所有分析页面的数据处理逻辑
 */

export const ensureArray = (value) => (Array.isArray(value) ? value : [])

export const toNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

export const toFiniteNumber = (value, fallback = null) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

export const formatCount = (value) => {
  const num = toNumber(value)
  return num.toLocaleString('en-US')
}

/**
 * 构建端口唯一键
 */
export const buildPortKey = (row) => {
  const guid = row?.NodeGUID || row?.NodeGuid || row?.['Node GUID'] || row?.['Node Name'] || 'unknown'
  const port = row?.PortNumber || row?.['Port Number'] || row?.port || '0'
  return `${guid}:${port}`
}

/**
 * 严重度配置
 */
export const SEVERITY_ORDER = { critical: 0, warning: 1, info: 2, ok: 3, normal: 3 }
export const SEVERITY_LABEL = { critical: '严重', warning: '警告', info: '信息', ok: '正常', normal: '正常' }

/**
 * 严重度筛选条颜色配置
 */
export const SEVERITY_CHIP_STYLES = {
  critical: {
    label: '严重',
    color: '#b91c1c',
    background: '#fee2e2',
    dotClass: 'severity-critical',
  },
  warning: {
    label: '警告',
    color: '#92400e',
    background: '#fef3c7',
    dotClass: 'severity-warning',
  },
  info: {
    label: '信息',
    color: '#1e40af',
    background: '#dbeafe',
    dotClass: 'severity-info',
  },
  ok: {
    label: '健康',
    color: '#166534',
    background: '#d1fae5',
    dotClass: 'severity-ok',
  },
}

/**
 * 从行数据中提取严重度
 */
export const extractSeverityFromRow = (row, severityFields = null) => {
  const defaultFields = [
    'Severity',
    'severity',
    'SymbolBERSeverity',
    'EffectiveBERSeverity',
    'CongestionLevel',
    'Status',
    'status',
    'Level',
    'AlertLevel',
  ]
  const fields = severityFields || defaultFields

  for (const field of fields) {
    const value = row?.[field]
    if (value != null) {
      const text = String(value).toLowerCase().trim()
      if (text === 'critical' || text === 'severe' || text === 'error' || text === 'failed') {
        return 'critical'
      }
      if (text === 'warning' || text === 'warn' || text === 'alert' || text === 'degraded') {
        return 'warning'
      }
      if (text === 'info' || text === 'notice') {
        return 'info'
      }
      if (text === 'ok' || text === 'healthy' || text === 'normal' || text === 'good') {
        return 'ok'
      }
    }
  }
  return null
}

/**
 * 统计各严重度数量
 */
export const countBySeverity = (rows, getSeverityFn) => {
  const counts = { critical: 0, warning: 0, info: 0, ok: 0 }
  ensureArray(rows).forEach(row => {
    const severity = getSeverityFn ? getSeverityFn(row) : extractSeverityFromRow(row)
    if (severity && counts[severity] !== undefined) {
      counts[severity] += 1
    } else {
      counts.ok += 1
    }
  })
  return counts
}

/**
 * 为行数据添加严重度标注
 */
export const annotateRows = (rows, getSeverityFn, getReasonFn) => {
  return ensureArray(rows)
    .map((row, index) => {
      const severity = getSeverityFn ? getSeverityFn(row) : (extractSeverityFromRow(row) || 'ok')
      const reason = getReasonFn ? getReasonFn(row) : ''
      return {
        __originalIndex: index,
        __severity: severity,
        __severityOrder: SEVERITY_ORDER[severity] ?? 3,
        IssueSeverity: SEVERITY_LABEL[severity] || severity,
        IssueReason: reason,
        ...row,
      }
    })
    .sort((a, b) => (a.__severityOrder ?? 3) - (b.__severityOrder ?? 3))
}

/**
 * 提取 Top N 问题行
 */
export const extractTopRows = (annotatedRows, severity, limit = 10) => {
  const order = SEVERITY_ORDER[severity]
  if (order === undefined) return []
  return annotatedRows.filter(row => row.__severityOrder === order).slice(0, limit)
}

/**
 * 根据严重度筛选行
 */
export const filterBySeverity = (rows, selectedSeverity) => {
  if (!selectedSeverity || selectedSeverity === 'all') {
    return rows
  }
  return ensureArray(rows).filter(row => row.__severity === selectedSeverity)
}

/**
 * 检查是否有告警标记
 */
export const hasAlarmFlag = (value) => {
  if (value === null || value === undefined) return false
  const text = String(value).trim()
  if (!text || text.toLowerCase() === 'n/a') return false
  const token = text.split(/\s+/)[0]
  if (!token) return false
  try {
    if (token.toLowerCase().startsWith('0x')) {
      return parseInt(token, 16) !== 0
    }
    const parsed = Number(token)
    return Number.isFinite(parsed) && parsed !== 0
  } catch {
    return false
  }
}
