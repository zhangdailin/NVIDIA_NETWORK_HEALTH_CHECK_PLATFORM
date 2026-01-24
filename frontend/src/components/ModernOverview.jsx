import { useState, useMemo } from 'react'
import {
  Activity, Server, Wifi, AlertTriangle, CheckCircle2, XCircle,
  Clock, Zap, TrendingUp, TrendingDown, Eye, Network,
  Cpu, HardDrive, Thermometer, Shield
} from 'lucide-react'

const ModernOverview = ({ analysisData, onSelectTab }) => {
  const [timeRange, setTimeRange] = useState('24h')

  // 从分析数据中提取关键指标
  const metrics = useMemo(() => {
    if (!analysisData) return null

    const {
      health,
      cable_data = [],
      ber_data = [],
      hca_data = [],
      switch_data = [],
      xmit_data = [],
      link_oscillation_data = [],
    } = analysisData

    // 计算在线设备数
    const totalDevices = (hca_data?.length || 0) + (switch_data?.length || 0)
    const healthyDevices = totalDevices - (health?.summary?.critical || 0) - (health?.summary?.warning || 0)

    // 计算异常告警
    const totalAlerts = (health?.summary?.critical || 0) + (health?.summary?.warning || 0)
    const criticalAlerts = health?.summary?.critical || 0

    // 估算网络吞吐量（这里用端口数量模拟）
    const totalPorts = health?.total_ports || 0
    const estimatedThroughput = (totalPorts * 0.4).toFixed(1) // 模拟数据

    // 计算平均延迟（从histogram或其他数据）
    const avgLatency = 23 // 模拟数据，实际应从数据中计算

    return {
      totalDevices,
      healthyDevices,
      deviceHealthRate: totalDevices > 0 ? ((healthyDevices / totalDevices) * 100).toFixed(1) : 0,
      totalAlerts,
      criticalAlerts,
      alertTrend: -2, // 模拟数据
      throughput: estimatedThroughput,
      throughputTrend: +1.2, // 模拟数据
      avgLatency,
      latencyTrend: -5, // 模拟数据
      healthScore: health?.score || 0,
      healthStatus: health?.status || 'Unknown',
      totalNodes: health?.total_nodes || 0,
      totalPorts,
    }
  }, [analysisData])

  if (!analysisData || !metrics) {
    return (
      <div className="modern-overview-empty">
        <Activity size={48} className="empty-icon" />
        <p>暂无数据，请上传网络诊断文件</p>
      </div>
    )
  }

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'healthy': return '#22c55e'
      case 'warning': return '#f59e0b'
      case 'critical': return '#ef4444'
      default: return '#64748b'
    }
  }

  const getScoreGrade = (score) => {
    if (score >= 90) return { grade: 'A', color: '#22c55e' }
    if (score >= 80) return { grade: 'B', color: '#84cc16' }
    if (score >= 70) return { grade: 'C', color: '#f59e0b' }
    if (score >= 60) return { grade: 'D', color: '#fb923c' }
    return { grade: 'F', color: '#ef4444' }
  }

  const scoreInfo = getScoreGrade(metrics.healthScore)

  // 主要指标卡片
  const metricCards = [
    {
      id: 'devices',
      label: '在线设备',
      value: metrics.totalDevices,
      subtitle: `${metrics.healthyDevices} 健康`,
      trend: null,
      icon: Server,
      color: '#3b82f6',
      onClick: () => onSelectTab?.('hca'),
    },
    {
      id: 'latency',
      label: '网络延迟',
      value: `${metrics.avgLatency}ms`,
      subtitle: '平均响应时间',
      trend: metrics.latencyTrend,
      icon: Zap,
      color: '#10b981',
      onClick: () => onSelectTab?.('latency'),
    },
    {
      id: 'throughput',
      label: '数据吞吐',
      value: `${metrics.throughput} Gb/s`,
      subtitle: '实时流量',
      trend: metrics.throughputTrend,
      icon: Activity,
      color: '#8b5cf6',
      onClick: () => onSelectTab?.('xmit'),
    },
    {
      id: 'alerts',
      label: '异常告警',
      value: metrics.totalAlerts,
      subtitle: `${metrics.criticalAlerts} 严重`,
      trend: metrics.alertTrend,
      icon: AlertTriangle,
      color: metrics.criticalAlerts > 0 ? '#ef4444' : '#f59e0b',
      onClick: () => onSelectTab?.('overview'),
    },
  ]

  // 系统概况卡片
  const systemCards = [
    {
      label: 'GPU 服务器',
      value: analysisData.hca_data?.length || 0,
      icon: Cpu,
      color: '#06b6d4',
    },
    {
      label: '交换机',
      value: analysisData.switch_data?.length || 0,
      icon: Network,
      color: '#ec4899',
    },
    {
      label: '总端口数',
      value: metrics.totalPorts,
      icon: HardDrive,
      color: '#f59e0b',
    },
    {
      label: '网络节点',
      value: metrics.totalNodes,
      icon: Wifi,
      color: '#14b8a6',
    },
  ]

  return (
    <div className="modern-overview">
      {/* 顶部横幅 - 健康度评分 */}
      <div className="health-banner">
        <div className="health-banner-left">
          <div className="health-score-ring" style={{ borderColor: scoreInfo.color }}>
            <div className="health-score-value" style={{ color: scoreInfo.color }}>
              {metrics.healthScore}
            </div>
            <div className="health-score-grade" style={{ color: scoreInfo.color }}>
              {scoreInfo.grade}
            </div>
          </div>
          <div className="health-banner-info">
            <h2 className="health-banner-title">网络健康度评分</h2>
            <p className="health-banner-status" style={{ color: getStatusColor(metrics.healthStatus) }}>
              {metrics.healthStatus === 'Healthy' && <CheckCircle2 size={20} />}
              {metrics.healthStatus === 'Warning' && <AlertTriangle size={20} />}
              {metrics.healthStatus === 'Critical' && <XCircle size={20} />}
              <span>{metrics.healthStatus}</span>
            </p>
            <div className="health-banner-meta">
              <span><Network size={14} /> {metrics.totalNodes} 节点</span>
              <span><HardDrive size={14} /> {metrics.totalPorts} 端口</span>
              <span><Clock size={14} /> 实时监控</span>
            </div>
          </div>
        </div>
        <div className="health-banner-right">
          <div className="time-range-selector">
            <button
              className={timeRange === '1h' ? 'active' : ''}
              onClick={() => setTimeRange('1h')}
            >
              1小时
            </button>
            <button
              className={timeRange === '24h' ? 'active' : ''}
              onClick={() => setTimeRange('24h')}
            >
              24小时
            </button>
            <button
              className={timeRange === '7d' ? 'active' : ''}
              onClick={() => setTimeRange('7d')}
            >
              7天
            </button>
          </div>
        </div>
      </div>

      {/* 主要指标卡片网格 */}
      <div className="metrics-grid">
        {metricCards.map((card) => (
          <div
            key={card.id}
            className="metric-card"
            onClick={card.onClick}
            style={{ '--accent-color': card.color }}
          >
            <div className="metric-card-header">
              <span className="metric-label">{card.label}</span>
              <div className="metric-icon" style={{ backgroundColor: `${card.color}15`, color: card.color }}>
                <card.icon size={20} />
              </div>
            </div>
            <div className="metric-value">{card.value}</div>
            <div className="metric-footer">
              <span className="metric-subtitle">{card.subtitle}</span>
              {card.trend !== null && (
                <div className={`metric-trend ${card.trend >= 0 ? 'positive' : 'negative'}`}>
                  {card.trend >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  <span>{Math.abs(card.trend)}</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* 系统概况 */}
      <div className="overview-section">
        <div className="section-header">
          <h3>系统概况</h3>
          <button className="view-details-btn" onClick={() => onSelectTab?.('overview')}>
            <Eye size={16} />
            <span>查看详情</span>
          </button>
        </div>
        <div className="system-cards-grid">
          {systemCards.map((card, index) => (
            <div key={index} className="system-card">
              <div className="system-card-icon" style={{ backgroundColor: `${card.color}15`, color: card.color }}>
                <card.icon size={24} />
              </div>
              <div className="system-card-content">
                <div className="system-card-label">{card.label}</div>
                <div className="system-card-value">{card.value}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 快速诊断面板 */}
      <div className="overview-section">
        <div className="section-header">
          <h3>快速诊断</h3>
        </div>
        <div className="diagnostic-grid">
          <div className="diagnostic-card" onClick={() => onSelectTab?.('cable')}>
            <div className="diagnostic-icon">
              <Network size={20} />
            </div>
            <div className="diagnostic-content">
              <div className="diagnostic-label">电缆分析</div>
              <div className="diagnostic-value">
                {analysisData.cable_data?.length || 0} 条目
              </div>
            </div>
            <div className="diagnostic-arrow">→</div>
          </div>

          <div className="diagnostic-card" onClick={() => onSelectTab?.('ber')}>
            <div className="diagnostic-icon">
              <Shield size={20} />
            </div>
            <div className="diagnostic-content">
              <div className="diagnostic-label">误码率检查</div>
              <div className="diagnostic-value">
                {analysisData.ber_data?.length || 0} 端口
              </div>
            </div>
            <div className="diagnostic-arrow">→</div>
          </div>

          <div className="diagnostic-card" onClick={() => onSelectTab?.('fan')}>
            <div className="diagnostic-icon">
              <Thermometer size={20} />
            </div>
            <div className="diagnostic-content">
              <div className="diagnostic-label">温度监控</div>
              <div className="diagnostic-value">
                {analysisData.fan_data?.length || 0} 设备
              </div>
            </div>
            <div className="diagnostic-arrow">→</div>
          </div>

          <div className="diagnostic-card" onClick={() => onSelectTab?.('link_oscillation')}>
            <div className="diagnostic-icon">
              <Activity size={20} />
            </div>
            <div className="diagnostic-content">
              <div className="diagnostic-label">链路振荡</div>
              <div className="diagnostic-value">
                {analysisData.link_oscillation_data?.length || 0} 路径
              </div>
            </div>
            <div className="diagnostic-arrow">→</div>
          </div>
        </div>
      </div>

      {/* 告警面板 */}
      {metrics.totalAlerts > 0 && (
        <div className="overview-section">
          <div className="section-header">
            <h3>最近告警</h3>
            <span className="alert-count-badge">{metrics.totalAlerts}</span>
          </div>
          <div className="alerts-panel">
            {metrics.criticalAlerts > 0 && (
              <div className="alert-item critical">
                <div className="alert-icon">
                  <XCircle size={20} />
                </div>
                <div className="alert-content">
                  <div className="alert-title">严重告警</div>
                  <div className="alert-desc">{metrics.criticalAlerts} 个关键问题需要立即处理</div>
                </div>
                <button className="alert-btn" onClick={() => onSelectTab?.('overview')}>
                  处理
                </button>
              </div>
            )}
            {(metrics.totalAlerts - metrics.criticalAlerts) > 0 && (
              <div className="alert-item warning">
                <div className="alert-icon">
                  <AlertTriangle size={20} />
                </div>
                <div className="alert-content">
                  <div className="alert-title">警告</div>
                  <div className="alert-desc">{metrics.totalAlerts - metrics.criticalAlerts} 个警告需要关注</div>
                </div>
                <button className="alert-btn" onClick={() => onSelectTab?.('overview')}>
                  查看
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ModernOverview
