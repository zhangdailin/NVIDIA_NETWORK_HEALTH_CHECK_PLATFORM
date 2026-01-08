import { useState } from 'react'
import { BarChart3, AlertTriangle, XCircle, Search } from 'lucide-react'

/**
 * BER (误码率) 健康分析 - 重新设计版
 * 先显示问题摘要,再显示完整数据表
 */
function BERAnalysis({ berData, berAdvancedData, perLaneData, berAdvancedSummary }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const ITEMS_PER_PAGE = 20

  // Helper to safely convert to number
  const toNumber = (value) => {
    const num = Number(value)
    return Number.isFinite(num) ? num : 0
  }

  // Combine all BER data sources
  const allBerData = []

  // Add basic BER data
  if (berData && Array.isArray(berData)) {
    allBerData.push(...berData.map(row => ({ ...row, source: 'basic' })))
  }

  // Add advanced BER data if available
  if (berAdvancedData && Array.isArray(berAdvancedData)) {
    berAdvancedData.forEach(row => {
      // Check if not already in basic data
      const existingIndex = allBerData.findIndex(
        item => item.NodeGUID === row.NodeGUID && item.PortNumber === row.PortNumber
      )
      if (existingIndex === -1) {
        allBerData.push({ ...row, source: 'advanced' })
      } else {
        // Merge advanced data into existing
        allBerData[existingIndex] = { ...allBerData[existingIndex], ...row, source: 'merged' }
      }
    })
  }

  if (allBerData.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <p>无BER数据</p>
      </div>
    )
  }

  // Analyze BER data
  const analyzeBER = () => {
    const criticalBER = []
    const warningBER = []
    const noThresholdPorts = []

    allBerData.forEach((row, index) => {
      const nodeName = row['Node Name'] || row.NodeName || 'Unknown'
      const nodeGuid = row.NodeGUID || row['Node GUID'] || 'N/A'
      const portNumber = row.PortNumber || row['Port Number'] || 'N/A'
      // Support both field names: SymbolBERSeverity (basic) and Severity (advanced)
      const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
      const eventName = String(row.EventName || '').toLowerCase()
      const log10Value = toNumber(row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10)
      // 🆕 优先使用后端返回的科学计数法字符串
      const symbolBER = row.SymbolBER || row['Symbol BER'] || null
      const effectiveBER = row.EffectiveBER || row['Effective BER'] || 'N/A'
      const rawBER = row.RawBER || row['Raw BER'] || 'N/A'

      // Advanced data - support multiple field names
      const fecCorrected = toNumber(row.FECCorrectedCW || row.FECCorrected || row.FECCorrectedBlocks || 0)
      const fecUncorrected = toNumber(row.FECUncorrectedCW || row.FECUncorrected || row.FECUncorrectableBlocks || 0)
      const laneCount = toNumber(row.NumLanes || row.TotalLanes || row.LanesAnalyzed || 0)

      const item = {
        nodeName,
        nodeGuid,
        portNumber,
        severity,
        log10Value,
        symbolBER,  // 🆕 添加科学计数法字符串
        effectiveBER,
        rawBER,
        eventName,
        fecCorrected,
        fecUncorrected,
        laneCount,
        source: row.source,
        index
      }

      if (severity === 'critical') {
        criticalBER.push(item)
      } else if (severity === 'warning') {
        warningBER.push(item)
      } else if (eventName.includes('no_threshold') || eventName.includes('no threshold')) {
        noThresholdPorts.push(item)
      }
    })

    return { criticalBER, warningBER, noThresholdPorts }
  }

  const { criticalBER, warningBER, noThresholdPorts } = analyzeBER()

  // Filter data for the table
  const filteredData = allBerData.filter(row => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      String(row['Node Name'] || row.NodeName || '').toLowerCase().includes(term) ||
      String(row.NodeGUID || '').toLowerCase().includes(term) ||
      String(row.PortNumber || '').toLowerCase().includes(term) ||
      String(row.EventName || row.Issues || '').toLowerCase().includes(term)
    )
  })

  const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE)
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE
  const pageData = filteredData.slice(startIdx, startIdx + ITEMS_PER_PAGE)

  // Get status for a row
  const getRowStatus = (row) => {
    // Support both SymbolBERSeverity (basic) and Severity (advanced)
    const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
    if (severity === 'critical') return 'critical'
    if (severity === 'warning') return 'warning'
    return 'ok'
  }

  const totalPorts = allBerData.length
  const criticalCount = criticalBER.length
  const warningCount = warningBER.length
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
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>严重超标</div>
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
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>BER偏高</div>
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

      {/* 🆕 BER分布统计 (如果backend提供) */}
      {berAdvancedSummary?.ber_distribution && Object.keys(berAdvancedSummary.ber_distribution).length > 0 && (
        <div style={{
          marginBottom: '24px',
          padding: '16px',
          background: 'white',
          borderRadius: '8px',
          border: '1px solid #e5e7eb'
        }}>
          <h4 style={{
            margin: '0 0 12px 0',
            fontSize: '1rem',
            color: '#1f2937',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <BarChart3 size={18} />
            📊 BER 分布统计
          </h4>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '12px'
          }}>
            {Object.entries(berAdvancedSummary.ber_distribution)
              .sort((a, b) => b[1] - a[1])  // Sort by count descending
              .map(([range, count]) => (
                <div key={range} style={{
                  padding: '12px',
                  background: '#f9fafb',
                  borderRadius: '6px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  border: '1px solid #e5e7eb'
                }}>
                  <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>{range}</span>
                  <span style={{ fontWeight: '600', fontSize: '1.1rem', color: '#1f2937' }}>
                    {count.toLocaleString()}
                  </span>
                </div>
              ))}
          </div>
          {/* 🆕 数据源标识 */}
          {berAdvancedSummary?.data_source && (
            <div style={{
              marginTop: '12px',
              paddingTop: '12px',
              borderTop: '1px solid #e5e7eb',
              fontSize: '0.85rem',
              color: '#6b7280'
            }}>
              ℹ️ 数据源: <span style={{ fontWeight: '500', color: '#3b82f6' }}>{berAdvancedSummary.data_source}</span>
            </div>
          )}
        </div>
      )}

      {/* 严重BER问题 */}
      {criticalBER.length > 0 && (
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
            🔴 误码率严重超标 ({criticalBER.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>
            BER应保持在1e-12或更低。这些端口的误码率远超安全阈值,可能导致数据损坏。
          </p>
          <div style={{ display: 'grid', gap: '12px' }}>
            {criticalBER.map((item, idx) => (
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
                  <strong>Symbol BER:</strong>{' '}
                  <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
                    {Number.isFinite(item.log10Value) ? `10^${item.log10Value.toFixed(1)}` : 'N/A'}
                  </span>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                    (阈值: 10^-12)
                  </div>
                </div>
                <div>
                  <strong>Effective BER:</strong> {item.effectiveBER}
                </div>
                {item.fecUncorrected > 0 && (
                  <div>
                    <strong>FEC不可纠正块:</strong>{' '}
                    <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
                      {item.fecUncorrected.toLocaleString()}
                    </span>
                  </div>
                )}
                {item.fecCorrected > 0 && (
                  <div>
                    <strong>FEC已纠正:</strong> {item.fecCorrected.toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* BER警告 */}
      {warningBER.length > 0 && (
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
            ⚠️ 误码率偏高 ({warningBER.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>
            BER在1e-15到1e-12之间。建议检查光纤清洁度、光功率和模块温度。
          </p>
          <div style={{ display: 'grid', gap: '12px' }}>
            {warningBER.slice(0, 5).map((item, idx) => (
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
                  <strong>Symbol BER:</strong>{' '}
                  <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>
                    {Number.isFinite(item.log10Value) ? `10^${item.log10Value.toFixed(1)}` : 'N/A'}
                  </span>
                </div>
                <div>
                  <strong>Raw BER:</strong> {item.rawBER}
                </div>
                {item.fecCorrected > 0 && (
                  <div>
                    <strong>FEC纠正活动:</strong> {item.fecCorrected.toLocaleString()}
                  </div>
                )}
              </div>
            ))}
            {warningBER.length > 5 && (
              <div style={{ textAlign: 'center', color: '#6b7280', fontSize: '0.9rem' }}>
                ...还有 {warningBER.length - 5} 个端口BER偏高 (见下方完整数据表)
              </div>
            )}
          </div>
        </div>
      )}

      {/* 无阈值监控端口提示 */}
      {noThresholdPorts.length > 0 && criticalBER.length === 0 && warningBER.length === 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#3b82f6',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <BarChart3 size={20} />
            ℹ️ BER阈值监控不可用 ({noThresholdPorts.length}个端口)
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#6b7280', marginBottom: '12px' }}>
            这些端口不支持BER阈值监控,取决于设备型号和固件版本。
          </p>
        </div>
      )}

      {/* 搜索栏 */}
      <div style={{ marginTop: '32px', marginBottom: '16px' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#1f2937' }}>
          📋 完整BER数据表 (可搜索/可排序)
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
            placeholder="搜索节点名、GUID、端口号、事件名..."
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
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Symbol BER</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Effective BER</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>Raw BER</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>事件名称</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>FEC纠正</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>FEC不可纠正</th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, idx) => {
              const status = getRowStatus(row)
              // Support multiple field names for log10 value
              const log10Value = toNumber(row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10)

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
                    color: status === 'critical' ? '#dc2626' : status === 'warning' ? '#f59e0b' : '#1f2937',
                    fontWeight: status !== 'ok' ? '600' : '400',
                    fontFamily: 'monospace'
                  }}>
                    {/* 优先显示后端返回的科学计数法字符串 (如 "1.5e-254"), 否则使用Log10格式 */}
                    {row.SymbolBER || row['Symbol BER'] || (Number.isFinite(log10Value) ? `10^${log10Value.toFixed(1)}` : 'N/A')}
                  </td>
                  <td style={{ padding: '10px', fontSize: '0.8rem' }}>{row.EffectiveBER || row['Effective BER'] || 'N/A'}</td>
                  <td style={{ padding: '10px', fontSize: '0.8rem' }}>{row.RawBER || row['Raw BER'] || 'N/A'}</td>
                  <td style={{ padding: '10px', fontSize: '0.8rem' }}>{row.EventName || row.Issues || 'N/A'}</td>
                  <td style={{ padding: '10px' }}>
                    {toNumber(row.FECCorrectedCW || row.FECCorrected || row.FECCorrectedBlocks || 0).toLocaleString()}
                  </td>
                  <td style={{
                    padding: '10px',
                    color: toNumber(row.FECUncorrectedCW || row.FECUncorrected || row.FECUncorrectableBlocks || 0) > 0 ? '#dc2626' : '#1f2937',
                    fontWeight: toNumber(row.FECUncorrectedCW || row.FECUncorrected || row.FECUncorrectableBlocks || 0) > 0 ? '600' : '400'
                  }}>
                    {toNumber(row.FECUncorrectedCW || row.FECUncorrected || row.FECUncorrectableBlocks || 0).toLocaleString()}
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

export default BERAnalysis
