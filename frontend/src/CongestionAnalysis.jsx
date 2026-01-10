import { useMemo, useState } from 'react'
import { AlertTriangle, XCircle, Clock } from 'lucide-react'
import DataTable from './DataTable'

const TABLE_PRIORITY = [
  'Issue',
  'Severity',
  'Node Name',
  'NodeGUID',
  'PortNumber',
  'WaitRatioPct',
  'WaitSeconds',
  'XmitCongestionPct',
  'FECNCount',
  'BECNCount',
  'LinkDownedCounter',
  'LinkDownedCounterExt',
  'CongestionLevel',
]

const toNumber = (value) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const analyzeCongestion = (rows = []) => {
  const severeCongestion = []
  const moderateCongestion = []
  const fecnBecnIssues = []
  const linkDownIssues = []

  rows.forEach((row, index) => {
    const nodeName = row['Node Name'] || row.NodeName || row.NodeGUID || 'Unknown'
    const nodeGuid = row.NodeGUID || row['Node GUID'] || 'N/A'
    const portNumber = row.PortNumber || row['Port Number'] || 'N/A'
    const waitRatio = toNumber(row.WaitRatioPct)
    const waitSeconds = toNumber(row.WaitSeconds)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const fecnCount = toNumber(row.FECNCount)
    const becnCount = toNumber(row.BECNCount)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)

    const item = {
      nodeName,
      nodeGuid,
      portNumber,
      waitRatio,
      waitSeconds,
      congestionPct,
      fecnCount,
      becnCount,
      linkDowned,
      index,
    }

    if (waitRatio >= 5 || congestionPct >= 5) {
      severeCongestion.push(item)
    } else if (waitRatio >= 1 || congestionPct >= 1) {
      moderateCongestion.push(item)
    }

    if (fecnCount > 0 || becnCount > 0) {
      fecnBecnIssues.push(item)
    }
    if (linkDowned > 0) {
      linkDownIssues.push(item)
    }
  })

  return { severeCongestion, moderateCongestion, fecnBecnIssues, linkDownIssues }
}

function CongestionAnalysis({ xmitData, summary }) {
  const [showAllModerate, setShowAllModerate] = useState(false)
  const [showAllTopWaiters, setShowAllTopWaiters] = useState(false)

  if (!xmitData || !Array.isArray(xmitData) || xmitData.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <p>无拥塞数据</p>
      </div>
    )
  }

  const { severeCongestion, moderateCongestion, fecnBecnIssues, linkDownIssues } = analyzeCongestion(xmitData)

  const getRowStatus = (row) => {
    const waitRatio = toNumber(row.WaitRatioPct)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)

    if (waitRatio >= 5 || congestionPct >= 5 || linkDowned > 10) return 'critical'
    if (waitRatio >= 1 || congestionPct >= 1 || linkDowned > 0) return 'warning'
    return 'ok'
  }

  const buildIssueDetail = (row, status) => {
    const waitRatio = toNumber(row.WaitRatioPct)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)
    const fecn = toNumber(row.FECNCount)
    const becn = toNumber(row.BECNCount)
    const reasons = []

    if (waitRatio >= 5) {
      reasons.push(`等待比例 ${waitRatio.toFixed(2)}% ≥ 5%`)
    } else if (waitRatio >= 1) {
      reasons.push(`等待比例 ${waitRatio.toFixed(2)}% ≥ 1%`)
    }
    if (congestionPct >= 5) {
      reasons.push(`XmitTimeCong ${congestionPct.toFixed(2)}% ≥ 5%`)
    } else if (congestionPct >= 1) {
      reasons.push(`XmitTimeCong ${congestionPct.toFixed(2)}% ≥ 1%`)
    }
    if (linkDowned > 10) {
      reasons.push(`链路断开 ${linkDowned} 次`)
    } else if (linkDowned > 0) {
      reasons.push(`链路断开 ${linkDowned} 次`)
    }
    if (fecn > 0 || becn > 0) {
      reasons.push(`FECN/BECN ${fecn}/${becn}`)
    }

    if (!reasons.length) {
      reasons.push(status === 'ok' ? '无异常' : '存在轻微波动')
    }

    const severityWeight = status === 'critical' ? 3 : status === 'warning' ? 2 : 1
    const priority = severityWeight * 1_000_000 + waitRatio * 1_000 + congestionPct * 100 + linkDowned
    return { issue: reasons.join(' / '), priority }
  }

  const severityLabel = {
    critical: '严重',
    warning: '警告',
    ok: '正常',
  }

  const tableRows = useMemo(() => {
    return xmitData.map(row => {
      const status = getRowStatus(row)
      const detail = buildIssueDetail(row, status)
      return {
        ...row,
        Severity: severityLabel[status] || '正常',
        Issue: detail.issue,
        __priority: detail.priority,
      }
    })
  }, [xmitData])

  const totalPorts = summary?.total_ports ?? xmitData.length
  const criticalCount = summary?.severe_ports ?? severeCongestion.length
  const warningCount = summary?.warning_ports ?? moderateCongestion.length
  const healthyCount = Math.max(totalPorts - criticalCount - warningCount, 0)

  const avgWaitRatio = summary?.avg_wait_ratio_pct
  const avgCongestion = summary?.avg_congestion_pct
  const fecnPorts = summary?.fecn_ports
  const becnPorts = summary?.becn_ports
  const linkDownPorts = summary?.link_down_ports
  const creditWatchdogPorts = summary?.credit_watchdog_ports

  const visibleModerate = showAllModerate ? moderateCongestion : moderateCongestion.slice(0, 5)

  return (
    <div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '16px',
        marginBottom: '24px',
      }}>
        <div style={{ padding: '16px', background: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>总端口数</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#1f2937' }}>{totalPorts}</div>
        </div>
        <div style={{ padding: '16px', background: criticalCount > 0 ? '#fee2e2' : 'white', borderRadius: '8px', border: `1px solid ${criticalCount > 0 ? '#dc2626' : '#e5e7eb'}`, textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>严重拥塞</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: criticalCount > 0 ? '#dc2626' : '#10b981' }}>{criticalCount}</div>
        </div>
        <div style={{ padding: '16px', background: warningCount > 0 ? '#fef3c7' : 'white', borderRadius: '8px', border: `1px solid ${warningCount > 0 ? '#f59e0b' : '#e5e7eb'}`, textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>中度拥塞</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: warningCount > 0 ? '#f59e0b' : '#10b981' }}>{warningCount}</div>
        </div>
        <div style={{ padding: '16px', background: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', textAlign: 'center' }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>健康端口</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#10b981' }}>{healthyCount}</div>
        </div>
      </div>

      {summary && summary.total_ports > 0 && (
        <div style={{ marginBottom: '24px', padding: '16px', border: '1px solid #e5e7eb', borderRadius: '8px', background: '#f8fafc' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
            {typeof avgWaitRatio === 'number' && <div><strong>平均等待比例:</strong> {avgWaitRatio.toFixed(2)}%</div>}
            {typeof avgCongestion === 'number' && <div><strong>平均 XmitTimeCong:</strong> {avgCongestion.toFixed(2)}%</div>}
            {typeof fecnPorts === 'number' && <div><strong>FECN 端口:</strong> {fecnPorts}</div>}
            {typeof becnPorts === 'number' && <div><strong>BECN 端口:</strong> {becnPorts}</div>}
            {typeof linkDownPorts === 'number' && <div><strong>链路断开端口:</strong> {linkDownPorts}</div>}
            {typeof creditWatchdogPorts === 'number' && creditWatchdogPorts > 0 && <div><strong>Credit Watchdog:</strong> {creditWatchdogPorts}</div>}
          </div>
        </div>
      )}

      {summary?.top_waiters?.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#1d4ed8', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={20} />
            TOP 等待端口
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {(showAllTopWaiters ? summary.top_waiters : summary.top_waiters.slice(0, 5)).map((item, idx) => (
              <div key={`${item.node_guid}-${item.port_number}-${idx}`} style={{
                padding: '12px 16px',
                borderRadius: '6px',
                border: '1px solid #cbd5f5',
                background: '#e0e7ff',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem',
              }}>
                <div>
                  <strong>节点:</strong> {item.node_name}
                  <div style={{ fontSize: '0.8rem', color: '#475569', fontFamily: 'monospace' }}>{item.node_guid}</div>
                </div>
                <div><strong>端口:</strong> {item.port_number}</div>
                <div><strong>等待比例:</strong> {item.wait_ratio_pct?.toFixed(2)}%</div>
                <div><strong>等待时间:</strong> {item.wait_seconds?.toFixed(2)}秒</div>
                <div><strong>XmitTimeCong:</strong> {item.xmit_congestion_pct?.toFixed(2)}%</div>
              </div>
            ))}
          </div>
          {summary.top_waiters.length > 5 && (
            <button
              type="button"
              onClick={() => setShowAllTopWaiters(value => !value)}
              style={{
                marginTop: '12px',
                border: 'none',
                background: 'transparent',
                color: '#2563eb',
                cursor: 'pointer',
              }}
            >
              {showAllTopWaiters ? '收起部分端口' : `展开剩余 ${summary.top_waiters.length - 5} 个端口`}
            </button>
          )}
        </div>
      )}

      {severeCongestion.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#dc2626', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <XCircle size={20} />
            严重拥塞 ({severeCongestion.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>等待比例 ≥5%。需立即优化路由或增加带宽。</p>
          <div style={{ display: 'grid', gap: '12px' }}>
            {severeCongestion.map((item, idx) => (
              <div key={idx} style={{
                padding: '12px 16px',
                background: '#fee2e2',
                borderRadius: '6px',
                border: '1px solid #dc2626',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem',
              }}>
                <div>
                  <strong>节点:</strong> {item.nodeName}
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', fontFamily: 'monospace' }}>{item.nodeGuid}</div>
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>等待比例:</strong>{' '}
                  <span style={{ color: '#dc2626', fontWeight: 'bold' }}>{item.waitRatio.toFixed(2)}%</span>
                  <span style={{ color: '#6b7280' }}> (阈值: 5%)</span>
                </div>
                <div><strong>等待时间:</strong> {item.waitSeconds.toFixed(2)}秒</div>
                {item.congestionPct > 0 && (
                  <div>
                    <strong>XmitTimeCong:</strong>{' '}
                    <span style={{ color: '#dc2626', fontWeight: 'bold' }}>{item.congestionPct.toFixed(2)}%</span>
                  </div>
                )}
                {(item.fecnCount > 0 || item.becnCount > 0) && (
                  <div><strong>FECN/BECN:</strong> {item.fecnCount}/{item.becnCount}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {moderateCongestion.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={20} />
            中度拥塞 ({moderateCongestion.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>等待比例 1-5%。建议持续监控并适度优化。</p>
          <div style={{ display: 'grid', gap: '12px' }}>
            {visibleModerate.map((item, idx) => (
              <div key={`${item.nodeGuid}-${item.portNumber}-${idx}`} style={{
                padding: '12px 16px',
                background: '#fef3c7',
                borderRadius: '6px',
                border: '1px solid #f59e0b',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem',
              }}>
                <div><strong>节点:</strong> {item.nodeName}</div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>等待比例:</strong>{' '}
                  <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>{item.waitRatio.toFixed(2)}%</span>
                </div>
                <div><strong>等待时间:</strong> {item.waitSeconds.toFixed(2)}秒</div>
              </div>
            ))}
          </div>
          {moderateCongestion.length > 5 && (
            <button
              type="button"
              onClick={() => setShowAllModerate(value => !value)}
              style={{
                marginTop: '12px',
                border: 'none',
                background: 'transparent',
                color: '#2563eb',
                cursor: 'pointer',
              }}
            >
              {showAllModerate ? '收起部分端口' : `展开剩余 ${moderateCongestion.length - 5} 个端口`}
            </button>
          )}
        </div>
      )}

      {fecnBecnIssues.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#3b82f6', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={20} />
            FECN/BECN 拥塞通知 ({fecnBecnIssues.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>检测到 Forward/Backward 显式拥塞通知计数器。</p>
        </div>
      )}

      {linkDownIssues.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={20} />
            链路断开记录 ({linkDownIssues.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>这些端口有链路断开记录, 可能存在不稳定链路。</p>
        </div>
      )}

      <div style={{ marginTop: '32px' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#1f2937' }}>
          📋 完整拥塞数据表 (可搜索/可排序)
        </h3>
        <DataTable
          rows={tableRows}
          hiddenColumns={['__priority']}
          totalRows={summary?.total_ports ?? xmitData.length}
          searchPlaceholder="搜索节点名、GUID、端口号..."
          pageSize={20}
          preferredColumns={TABLE_PRIORITY}
          defaultSortKey="__priority"
        />
      </div>
    </div>
  )
}

export default CongestionAnalysis
