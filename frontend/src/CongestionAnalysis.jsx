import { useState } from 'react'
import { AlertTriangle, XCircle, Clock, Search } from 'lucide-react'

/**
 * 拥塞分析 - 重新设计版
 * 先显示问题摘要,再显示完整数据表
 */
function CongestionAnalysis({ xmitData }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const ITEMS_PER_PAGE = 20

  if (!xmitData || !Array.isArray(xmitData) || xmitData.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <p>无拥塞数据</p>
      </div>
    )
  }

  // Helper to safely convert to number
  const toNumber = (value) => {
    const num = Number(value)
    return Number.isFinite(num) ? num : 0
  }

  // Analyze congestion data
  const analyzeCongestion = () => {
    const severeCongestion = []
    const moderateCongestion = []
    const fecnBecnIssues = []
    const linkDownIssues = []

    xmitData.forEach((row, index) => {
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
        index
      }

      // Severe congestion (≥5%)
      if (waitRatio >= 5 || congestionPct >= 5) {
        severeCongestion.push(item)
      }
      // Moderate congestion (1-5%)
      else if (waitRatio >= 1 || congestionPct >= 1) {
        moderateCongestion.push(item)
      }

      // FECN/BECN issues
      if (fecnCount > 0 || becnCount > 0) {
        fecnBecnIssues.push(item)
      }

      // Link down issues
      if (linkDowned > 0) {
        linkDownIssues.push(item)
      }
    })

    return { severeCongestion, moderateCongestion, fecnBecnIssues, linkDownIssues }
  }

  const { severeCongestion, moderateCongestion, fecnBecnIssues, linkDownIssues } = analyzeCongestion()

  // Filter data for the table
  const filteredData = xmitData.filter(row => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      String(row['Node Name'] || row.NodeName || '').toLowerCase().includes(term) ||
      String(row.NodeGUID || '').toLowerCase().includes(term) ||
      String(row.PortNumber || row['Port Number'] || '').toLowerCase().includes(term)
    )
  })

  const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE)
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE
  const pageData = filteredData.slice(startIdx, startIdx + ITEMS_PER_PAGE)

  // Get status for a row
  const getRowStatus = (row) => {
    const waitRatio = toNumber(row.WaitRatioPct)
    const congestionPct = toNumber(row.XmitCongestionPct)
    const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)

    if (waitRatio >= 5 || congestionPct >= 5 || linkDowned > 10) return 'critical'
    if (waitRatio >= 1 || congestionPct >= 1 || linkDowned > 0) return 'warning'
    return 'ok'
  }

  const totalPorts = xmitData.length
  const criticalCount = severeCongestion.length
  const warningCount = moderateCongestion.length
  const healthyCount = totalPorts - criticalCount - warningCount

  return (
    <div>
      {/* 快速统计 */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <div style={{
          padding: '16px',
          background: 'white',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>总端口数</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#1f2937' }}>{totalPorts}</div>
        </div>

        <div style={{
          padding: '16px',
          background: criticalCount > 0 ? '#fee2e2' : 'white',
          borderRadius: '8px',
          border: `1px solid ${criticalCount > 0 ? '#dc2626' : '#e5e7eb'}`,
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>严重拥塞</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: criticalCount > 0 ? '#dc2626' : '#10b981' }}>
            {criticalCount}
          </div>
        </div>

        <div style={{
          padding: '16px',
          background: warningCount > 0 ? '#fef3c7' : 'white',
          borderRadius: '8px',
          border: `1px solid ${warningCount > 0 ? '#f59e0b' : '#e5e7eb'}`,
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>中度拥塞</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: warningCount > 0 ? '#f59e0b' : '#10b981' }}>
            {warningCount}
          </div>
        </div>

        <div style={{
          padding: '16px',
          background: 'white',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          textAlign: 'center'
        }}>
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>健康端口</div>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#10b981' }}>
            {healthyCount}
          </div>
        </div>
      </div>

      {/* 严重拥塞 */}
      {severeCongestion.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#dc2626',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <XCircle size={20} />
            🔴 严重拥塞 ({severeCongestion.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>
            等待比例 ≥5%。需立即优化路由或增加带宽。
          </p>
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
                fontSize: '0.9rem'
              }}>
                <div>
                  <strong>节点:</strong> {item.nodeName}
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', fontFamily: 'monospace' }}>
                    {item.nodeGuid}
                  </div>
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>等待比例:</strong>{' '}
                  <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
                    {item.waitRatio.toFixed(2)}%
                  </span>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                    (阈值: 5%)
                  </div>
                </div>
                <div>
                  <strong>等待时间:</strong> {item.waitSeconds.toFixed(2)}秒
                </div>
                {item.congestionPct > 0 && (
                  <div>
                    <strong>XmitTimeCong:</strong>{' '}
                    <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
                      {item.congestionPct.toFixed(2)}%
                    </span>
                  </div>
                )}
                {(item.fecnCount > 0 || item.becnCount > 0) && (
                  <div>
                    <strong>FECN/BECN:</strong> {item.fecnCount}/{item.becnCount}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 中度拥塞 */}
      {moderateCongestion.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#f59e0b',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle size={20} />
            ⚠️ 中度拥塞 ({moderateCongestion.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>
            等待比例 1-5%。建议监控并考虑优化。
          </p>
          <div style={{ display: 'grid', gap: '12px' }}>
            {moderateCongestion.slice(0, 5).map((item, idx) => (
              <div key={idx} style={{
                padding: '12px 16px',
                background: '#fef3c7',
                borderRadius: '6px',
                border: '1px solid #f59e0b',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
                fontSize: '0.9rem'
              }}>
                <div>
                  <strong>节点:</strong> {item.nodeName}
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>等待比例:</strong>{' '}
                  <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>
                    {item.waitRatio.toFixed(2)}%
                  </span>
                </div>
                <div>
                  <strong>等待时间:</strong> {item.waitSeconds.toFixed(2)}秒
                </div>
              </div>
            ))}
            {moderateCongestion.length > 5 && (
              <div style={{ textAlign: 'center', color: '#6b7280', fontSize: '0.9rem' }}>
                ...还有 {moderateCongestion.length - 5} 个端口有中度拥塞 (见下方完整数据表)
              </div>
            )}
          </div>
        </div>
      )}

      {/* FECN/BECN检测 */}
      {fecnBecnIssues.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#3b82f6',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Clock size={20} />
            ℹ️ FECN/BECN拥塞通知 ({fecnBecnIssues.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>
            检测到Forward/Backward显式拥塞通知计数器。
          </p>
        </div>
      )}

      {/* 链路断开记录 */}
      {linkDownIssues.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#f59e0b',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle size={20} />
            ⚠️ 链路断开记录 ({linkDownIssues.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>
            这些端口有链路断开记录,可能不稳定。
          </p>
        </div>
      )}

      {/* 搜索栏 */}
      <div style={{ marginTop: '32px', marginBottom: '16px' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#1f2937' }}>
          📋 完整拥塞数据表 (可搜索/可排序)
        </h3>
        <div style={{ position: 'relative' }}>
          <Search size={18} style={{
            position: 'absolute',
            left: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            color: '#6b7280'
          }} />
          <input
            type="text"
            placeholder="搜索节点名、GUID、端口号..."
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value)
              setCurrentPage(1)
            }}
            style={{
              width: '100%',
              padding: '10px 12px 10px 40px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '0.95rem'
            }}
          />
        </div>
      </div>

      {/* 完整数据表 */}
      <div style={{ overflowX: 'auto', marginBottom: '16px' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.85rem',
          background: 'white'
        }}>
          <thead>
            <tr style={{ background: '#f3f4f6', borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>状态</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>节点名</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>端口</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>等待比例</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>等待时间</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>XmitTimeCong</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>FECN</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>BECN</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>链路断开</th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, idx) => {
              const status = getRowStatus(row)
              const waitRatio = toNumber(row.WaitRatioPct)
              const congestionPct = toNumber(row.XmitCongestionPct)
              const linkDowned = toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt)

              return (
                <tr
                  key={idx}
                  style={{
                    borderBottom: '1px solid #e5e7eb',
                    background: status === 'critical' ? '#fee2e2' :
                               status === 'warning' ? '#fef3c7' : 'white'
                  }}
                >
                  <td style={{ padding: '10px' }}>
                    {status === 'critical' && <span style={{ color: '#dc2626' }}>🔴 严重</span>}
                    {status === 'warning' && <span style={{ color: '#f59e0b' }}>⚠️ 警告</span>}
                    {status === 'ok' && <span style={{ color: '#10b981' }}>✅ 正常</span>}
                  </td>
                  <td style={{ padding: '10px', fontWeight: '500' }}>{row['Node Name'] || row.NodeName || 'N/A'}</td>
                  <td style={{ padding: '10px' }}>{row.PortNumber || row['Port Number'] || 'N/A'}</td>
                  <td style={{
                    padding: '10px',
                    color: waitRatio >= 5 ? '#dc2626' : waitRatio >= 1 ? '#f59e0b' : '#1f2937',
                    fontWeight: waitRatio >= 1 ? '600' : '400'
                  }}>
                    {waitRatio > 0 ? `${waitRatio.toFixed(2)}%` : '0%'}
                  </td>
                  <td style={{ padding: '10px' }}>
                    {toNumber(row.WaitSeconds).toFixed(2)}s
                  </td>
                  <td style={{
                    padding: '10px',
                    color: congestionPct >= 5 ? '#dc2626' : congestionPct >= 1 ? '#f59e0b' : '#1f2937',
                    fontWeight: congestionPct >= 1 ? '600' : '400'
                  }}>
                    {congestionPct > 0 ? `${congestionPct.toFixed(2)}%` : 'N/A'}
                  </td>
                  <td style={{ padding: '10px' }}>
                    {toNumber(row.FECNCount).toLocaleString() || '0'}
                  </td>
                  <td style={{ padding: '10px' }}>
                    {toNumber(row.BECNCount).toLocaleString() || '0'}
                  </td>
                  <td style={{
                    padding: '10px',
                    color: linkDowned > 0 ? '#f59e0b' : '#1f2937',
                    fontWeight: linkDowned > 0 ? '600' : '400'
                  }}>
                    {linkDowned > 0 ? linkDowned.toLocaleString() : '0'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '12px',
          padding: '12px'
        }}>
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            style={{
              padding: '6px 12px',
              background: currentPage === 1 ? '#e5e7eb' : '#3b82f6',
              color: currentPage === 1 ? '#9ca3af' : 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
            }}
          >
            上一页
          </button>

          <span style={{ fontSize: '0.9rem', color: '#4b5563' }}>
            第 {currentPage} / {totalPages} 页 (共 {filteredData.length} 条)
          </span>

          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: '6px 12px',
              background: currentPage === totalPages ? '#e5e7eb' : '#3b82f6',
              color: currentPage === totalPages ? '#9ca3af' : 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
            }}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  )
}

export default CongestionAnalysis
