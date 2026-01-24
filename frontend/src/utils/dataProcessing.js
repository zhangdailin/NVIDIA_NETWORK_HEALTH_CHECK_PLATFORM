/**
 * 数据处理工具函数
 * 从组件中提取的纯函数
 */

import { ensureArray } from '../analysisUtils'

/**
 * 提取主机标签
 */
export const extractHostLabel = (raw = '') => {
  if (!raw) return 'Unknown'
  const withoutSlash = raw.split('/')[0] || raw
  const hcaSplitIndex = withoutSlash.indexOf(' HCA')
  if (hcaSplitIndex >= 0) {
    return withoutSlash.slice(0, hcaSplitIndex).trim() || withoutSlash.trim()
  }
  return withoutSlash.trim() || raw
}

/**
 * 构建频繁重启的主机列表
 */
export const buildFrequentRebootHosts = (rows = []) => {
  const hosts = new Map()
  ensureArray(rows).forEach(row => {
    const flagged = row?.RecentlyRebooted ?? row?.recentlyRebooted
    if (!flagged) return
    const nodeName = row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown Node'
    const hostLabel = extractHostLabel(nodeName)
    const uptime = row['Up Time'] || row.UpTime || row.HWInfo_UpTime || 'N/A'
    const seconds = Number(row?.UptimeSeconds ?? row?.uptimeSeconds ?? 0)
    const entry = hosts.get(hostLabel) || {
      host: hostLabel,
      nodes: [],
      minSeconds: Number.isFinite(seconds) ? seconds : Infinity
    }
    entry.nodes.push({
      nodeName,
      guid: row.NodeGUID,
      uptime,
      seconds,
    })
    if (Number.isFinite(seconds)) {
      entry.minSeconds = Math.min(entry.minSeconds, seconds)
    }
    hosts.set(hostLabel, entry)
  })
  return Array.from(hosts.values()).sort((a, b) => (a.minSeconds || Infinity) - (b.minSeconds || Infinity))
}

/**
 * 构建推荐操作计划
 */
export const buildActionPlan = (issues = []) => {
  const safeIssues = ensureArray(issues)
  const dedup = new Set()
  const actions = []

  safeIssues.forEach(issue => {
    const kb = issue.details?.kb
    if (!kb || !Array.isArray(kb.recommended_actions)) return

    kb.recommended_actions.forEach(action => {
      if (dedup.has(action)) return
      dedup.add(action)
      actions.push({
        text: action,
        severity: issue.severity,
        category: issue.category,
        reference: kb.reference,
      })
    })
  })

  return actions
}

/**
 * 获取健康度评分颜色
 */
export const getScoreColor = (score) => {
  if (score >= 80) return '#22c55e'  // green
  if (score >= 60) return '#eab308'  // yellow
  return '#ef4444'  // red
}

/**
 * 获取状态图标颜色
 */
export const getStatusColor = (status) => {
  switch (status?.toLowerCase()) {
    case 'healthy': return '#22c55e'
    case 'warning': return '#f59e0b'
    case 'critical': return '#ef4444'
    default: return '#64748b'
  }
}
