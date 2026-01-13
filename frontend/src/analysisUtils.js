/**
 * 通用分析工具函数
 * 用于统一所有分析页面的数据处理逻辑
 */

export const ensureArray = (value) => (Array.isArray(value) ? value : [])

/**
 * 安全转换为数字
 * @param {*} value - 要转换的值
 * @param {number} fallback - 转换失败时的默认值
 * @returns {number} 转换后的数字
 */
export const toNumber = (value, fallback = 0) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

// 向后兼容的别名
export const toFiniteNumber = toNumber

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
 * 严重度配置（统一的配置对象）
 */
export const SEVERITY_CONFIG = {
  critical: {
    label: '严重',
    order: 0,
    color: '#b91c1c',
    background: '#fee2e2',
    dotClass: 'severity-critical',
  },
  warning: {
    label: '警告',
    order: 1,
    color: '#92400e',
    background: '#fef3c7',
    dotClass: 'severity-warning',
  },
  info: {
    label: '信息',
    order: 2,
    color: '#1e40af',
    background: '#dbeafe',
    dotClass: 'severity-info',
  },
  ok: {
    label: '健康',
    order: 3,
    color: '#166534',
    background: '#d1fae5',
    dotClass: 'severity-ok',
  },
  normal: {
    label: '正常',
    order: 3,
    color: '#166534',
    background: '#d1fae5',
    dotClass: 'severity-ok',
  },
}

// 向后兼容的导出
export const SEVERITY_ORDER = Object.fromEntries(
  Object.entries(SEVERITY_CONFIG).map(([key, value]) => [key, value.order])
)

export const SEVERITY_LABEL = Object.fromEntries(
  Object.entries(SEVERITY_CONFIG).map(([key, value]) => [key, value.label])
)

export const SEVERITY_CHIP_STYLES = SEVERITY_CONFIG

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
 * 创建标准的严重度判断函数
 *
 * 这个工厂函数用于减少34个分析组件中重复的 getSeverity 逻辑
 *
 * @param {Function} customLogic - 自定义逻辑函数，返回 'critical' | 'warning' | 'info' | 'ok' | null
 *                                  如果返回 null，则继续使用标准逻辑
 * @returns {Function} getSeverity 函数
 *
 * @example
 * // 简单使用（只使用标准逻辑）
 * const getSeverity = createSeverityChecker()
 *
 * @example
 * // 带自定义逻辑
 * const getSeverity = createSeverityChecker((row) => {
 *   const hasSymbolErrors = toNumber(row['Symbol Err']) > 0
 *   const anomaly = row['IBH Anomaly']
 *   if (hasSymbolErrors && anomaly) return 'warning'
 *   return null  // 返回 null 继续使用标准逻辑
 * })
 */
export const createSeverityChecker = (customLogic = null) => {
  return (row) => {
    // 标准逻辑：检查 Severity 字段
    const severity = String(row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') return 'critical'
    if (severity === 'warning' || severity === 'warn') return 'warning'
    if (severity === 'info') return 'info'
    if (severity === 'ok' || severity === 'normal') return 'ok'

    // 自定义逻辑
    if (customLogic) {
      const result = customLogic(row)
      if (result) return result
    }

    return 'ok'
  }
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
  // 'issues' 表示只显示 critical 和 warning
  if (selectedSeverity === 'issues') {
    return ensureArray(rows).filter(row =>
      row.__severity === 'critical' || row.__severity === 'warning'
    )
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
