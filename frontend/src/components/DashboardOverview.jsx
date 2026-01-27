/**
 * 健康检查看板 - 全新总览页面
 *
 * 特点：
 * 1. 所有数据来自统一的数据处理层
 * 2. 与各分析标签页数据完全一致
 * 3. 实时数据，无模拟数据
 * 4. 清晰的层次结构和视觉设计
 */

import { useMemo } from 'react'
import {
  Activity, Server, AlertTriangle, CheckCircle2, XCircle,
  Shield, Thermometer, Zap, Network, TrendingUp, Eye,
  ArrowRight, ChevronRight
} from 'lucide-react'
import { processAnalysisData } from '../core/dataProcessor'
import './DashboardOverview.css'

const DashboardOverview = ({ analysisData, onSelectTab }) => {
  // 使用统一数据处理层
  const metrics = useMemo(() => {
    if (!analysisData) return null
    return processAnalysisData(analysisData)
  }, [analysisData])

  if (!metrics) {
    return (
      <div className="dashboard-empty">
        <Activity size={64} strokeWidth={1} />
        <h3>暂无数据</h3>
        <p>请上传 IBDiagnet 诊断文件开始分析</p>
      </div>
    )
  }

  const { health, checks, summary, topology } = metrics

  // 健康状态配置
  const getHealthConfig = () => {
    const score = health.score || 0
    const status = health.status || 'Unknown'

    if (score >= 90) return { color: '#22c55e', grade: 'A', text: '优秀', icon: CheckCircle2 }
    if (score >= 80) return { color: '#84cc16', grade: 'B', text: '良好', icon: CheckCircle2 }
    if (score >= 70) return { color: '#f59e0b', grade: 'C', text: '一般', icon: AlertTriangle }
    if (score >= 60) return { color: '#fb923c', grade: 'D', text: '较差', icon: AlertTriangle }
    return { color: '#ef4444', grade: 'F', text: '危险', icon: XCircle }
  }

  const healthConfig = getHealthConfig()
  const HealthIcon = healthConfig.icon

  // 关键指标卡片配置（使用真实数据）
  const keyMetrics = [
    {
      id: 'devices',
      label: '设备总数',
      value: summary.totalDevices,
      subtitle: `${summary.healthyDevices} 健康`,
      change: null,
      icon: Server,
      color: '#3b82f6',
      severity: summary.unhealthyDevices > 0 ? 'warning' : 'ok',
      onClick: () => onSelectTab?.('hca')
    },
    {
      id: 'ports',
      label: '端口总数',
      value: topology.totalPorts,
      subtitle: `${topology.totalNodes} 节点`,
      change: null,
      icon: Network,
      color: '#8b5cf6',
      severity: 'ok',
      onClick: () => onSelectTab?.('cable')
    },
    {
      id: 'critical',
      label: '严重告警',
      value: summary.criticalCount,
      subtitle: summary.criticalCount > 0 ? '需要立即处理' : '无严重问题',
      change: null,
      icon: XCircle,
      color: '#ef4444',
      severity: summary.criticalCount > 0 ? 'critical' : 'ok',
      onClick: () => onSelectTab?.('overview')
    },
    {
      id: 'warnings',
      label: '警告',
      value: summary.warningCount,
      subtitle: summary.warningCount > 0 ? '需要关注' : '无警告',
      change: null,
      icon: AlertTriangle,
      color: '#f59e0b',
      severity: summary.warningCount > 0 ? 'warning' : 'ok',
      onClick: () => onSelectTab?.('overview')
    }
  ]

  // 快速检查卡片（显示有问题的检查项）
  const problemChecks = useMemo(() => {
    const problems = []

    // 遍历所有检查项，找出有问题的
    Object.entries(checks).forEach(([key, check]) => {
      if (check.criticalCount > 0 || check.warningCount > 0) {
        problems.push({
          key,
          ...check,
          severity: check.criticalCount > 0 ? 'critical' : 'warning',
          totalIssues: check.criticalCount + check.warningCount
        })
      }
    })

    // 按严重程度和问题数量排序
    problems.sort((a, b) => {
      if (a.severity !== b.severity) {
        return a.severity === 'critical' ? -1 : 1
      }
      return b.totalIssues - a.totalIssues
    })

    return problems.slice(0, 6) // 只显示前6个
  }, [checks])

  // 健康分布数据
  const healthDistribution = useMemo(() => {
    const total = Object.keys(checks).length
    const critical = Object.values(checks).filter(c => c.status === 'critical').length
    const warning = Object.values(checks).filter(c => c.status === 'warning').length
    const ok = total - critical - warning

    return { total, critical, warning, ok }
  }, [checks])

  return (
    <div className="dashboard-overview">
      {/* 顶部健康评分横幅 */}
      <div className="health-banner">
        <div className="health-score-section">
          <div className="health-score-circle" style={{ borderColor: healthConfig.color }}>
            <span className="score-value" style={{ color: healthConfig.color }}>
              {health.score}
            </span>
            <span className="score-grade">{healthConfig.grade}</span>
          </div>
          <div className="health-info">
            <h2>网络健康评分</h2>
            <div className="health-status" style={{ color: healthConfig.color }}>
              <HealthIcon size={20} />
              <span>{healthConfig.text}</span>
            </div>
            <p className="health-desc">
              {topology.totalNodes} 节点 · {topology.totalPorts} 端口
            </p>
          </div>
        </div>

        <div className="health-summary-section">
          <div className="summary-stat critical">
            <XCircle size={16} />
            <div>
              <span className="stat-value">{summary.criticalCount}</span>
              <span className="stat-label">严重</span>
            </div>
          </div>
          <div className="summary-stat warning">
            <AlertTriangle size={16} />
            <div>
              <span className="stat-value">{summary.warningCount}</span>
              <span className="stat-label">警告</span>
            </div>
          </div>
          <div className="summary-stat ok">
            <CheckCircle2 size={16} />
            <div>
              <span className="stat-value">{healthDistribution.ok}</span>
              <span className="stat-label">正常</span>
            </div>
          </div>
        </div>
      </div>

      {/* 关键指标网格 */}
      <div className="metrics-grid">
        {keyMetrics.map((metric) => (
          <div
            key={metric.id}
            className={`metric-card severity-${metric.severity}`}
            onClick={metric.onClick}
            style={{ '--accent-color': metric.color }}
          >
            <div className="metric-header">
              <div className="metric-icon" style={{ backgroundColor: `${metric.color}15`, color: metric.color }}>
                <metric.icon size={24} />
              </div>
              <span className="metric-label">{metric.label}</span>
            </div>
            <div className="metric-value">{metric.value}</div>
            <div className="metric-subtitle">{metric.subtitle}</div>
          </div>
        ))}
      </div>

      {/* 问题检查项 */}
      {problemChecks.length > 0 && (
        <div className="section">
          <div className="section-header">
            <h3>
              <AlertTriangle size={20} />
              需要关注的检查项
            </h3>
            <span className="badge">{problemChecks.length}</span>
          </div>
          <div className="problem-checks-grid">
            {problemChecks.map((check) => (
              <div
                key={check.key}
                className={`problem-check-card severity-${check.severity}`}
                onClick={() => onSelectTab?.(check.key)}
              >
                <div className="check-header">
                  <span className="check-label">{check.label}</span>
                  <span className={`check-badge severity-${check.severity}`}>
                    {check.severity === 'critical' ? '严重' : '警告'}
                  </span>
                </div>
                <div className="check-stats">
                  {check.criticalCount > 0 && (
                    <span className="stat critical">
                      {check.criticalCount} 严重
                    </span>
                  )}
                  {check.warningCount > 0 && (
                    <span className="stat warning">
                      {check.warningCount} 警告
                    </span>
                  )}
                </div>
                <div className="check-footer">
                  <span className="check-desc">{check.description}</span>
                  <ChevronRight size={16} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 所有检查项快速视图 */}
      <div className="section">
        <div className="section-header">
          <h3>
            <Activity size={20} />
            全部检查项
          </h3>
          <button
            className="view-all-btn"
            onClick={() => onSelectTab?.('overview')}
          >
            查看详细看板
            <ArrowRight size={16} />
          </button>
        </div>

        <div className="checks-summary">
          <div className="check-groups">
            {Object.entries(checks).map(([key, check]) => {
              const statusClass = check.status || 'ok'
              const StatusIcon = statusClass === 'critical' ? XCircle :
                                statusClass === 'warning' ? AlertTriangle : CheckCircle2

              return (
                <div
                  key={key}
                  className={`check-item status-${statusClass}`}
                  onClick={() => onSelectTab?.(key)}
                >
                  <StatusIcon size={16} />
                  <span className="check-name">{check.label}</span>
                  {(check.criticalCount > 0 || check.warningCount > 0) && (
                    <span className="check-count">
                      {check.criticalCount + check.warningCount}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* 快速操作 */}
      <div className="section">
        <div className="section-header">
          <h3>
            <Eye size={20} />
            快速诊断
          </h3>
        </div>
        <div className="quick-actions">
          {[
            { key: 'cable', icon: Network, label: '电缆分析', count: checks.cable?.totalRows || 0 },
            { key: 'ber', icon: Shield, label: 'BER 误码率', count: checks.ber?.totalRows || 0 },
            { key: 'xmit', icon: Activity, label: '拥塞分析', count: checks.xmit?.totalRows || 0 },
            { key: 'fan', icon: Thermometer, label: '温度监控', count: checks.fan?.totalRows || 0 },
          ].map((action) => (
            <div
              key={action.key}
              className="quick-action-card"
              onClick={() => onSelectTab?.(action.key)}
            >
              <div className="action-icon">
                <action.icon size={24} />
              </div>
              <div className="action-content">
                <span className="action-label">{action.label}</span>
                <span className="action-count">{action.count} 条目</span>
              </div>
              <ArrowRight size={16} className="action-arrow" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default DashboardOverview
