import { useState } from 'react'
import { Thermometer, Zap, AlertTriangle, CheckCircle, Search } from 'lucide-react'

/**
 * 线缆与光模块健康分析 - 重新设计版
 * 先显示问题摘要,再显示完整数据表
 */
function CableAnalysis({ cableData }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const ITEMS_PER_PAGE = 20

  if (!cableData || !Array.isArray(cableData) || cableData.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <p>无线缆数据</p>
      </div>
    )
  }

  // Helper functions
  const toNumber = (value) => {
    const num = Number(value)
    return Number.isFinite(num) ? num : 0
  }

  const hasAlarmFlag = (value) => {
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

  // Analyze cable data
  const analyzeData = () => {
    const tempCritical = []
    const tempWarning = []
    const powerAlarms = []
    const complianceIssues = []

    cableData.forEach((row, index) => {
      const temp = toNumber(row['Temperature (c)'] || row.Temperature)
      const nodeName = row['Node Name'] || row.NodeName || 'Unknown'
      const portNumber = row.PortNumber || row['Port Number'] || 'N/A'
      const vendor = row.Vendor || row['Vendor Name'] || 'N/A'
      // Backend returns 'PN' and 'SN', not 'Part Number' and 'Serial Number'
      const partNumber = row.PN || row['Part Number'] || row.PartNumber || 'N/A'
      const serialNumber = row.SN || row['Serial Number'] || row.SerialNumber || 'N/A'

      // Temperature check
      if (temp >= 80) {
        tempCritical.push({ ...row, temp, nodeName, portNumber, vendor, partNumber, index })
      } else if (temp >= 70) {
        tempWarning.push({ ...row, temp, nodeName, portNumber, vendor, partNumber, index })
      }

      // Power alarms check
      const alarms = []
      if (hasAlarmFlag(row['TX Bias Alarm and Warning'])) alarms.push('TX Bias')
      if (hasAlarmFlag(row['TX Power Alarm and Warning'])) alarms.push('TX Power')
      if (hasAlarmFlag(row['RX Power Alarm and Warning'])) alarms.push('RX Power')
      if (hasAlarmFlag(row['Latched Voltage Alarm and Warning'])) alarms.push('Voltage')

      if (alarms.length > 0) {
        powerAlarms.push({ ...row, alarms, nodeName, portNumber, vendor, partNumber, index })
      }

      // Compliance check
      const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
      const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()

      if ((complianceStatus !== 'ok' && complianceStatus !== '') ||
          (speedStatus !== 'ok' && speedStatus !== '')) {
        complianceIssues.push({
          ...row,
          complianceStatus,
          speedStatus,
          nodeName,
          portNumber,
          vendor,
          partNumber,
          index
        })
      }
    })

    return { tempCritical, tempWarning, powerAlarms, complianceIssues }
  }

  const { tempCritical, tempWarning, powerAlarms, complianceIssues } = analyzeData()

  //Filter data for the table
  const filteredData = cableData.filter(row => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      String(row['Node Name'] || row.NodeName || '').toLowerCase().includes(term) ||
      String(row.NodeGUID || '').toLowerCase().includes(term) ||
      String(row.PortNumber || '').toLowerCase().includes(term) ||
      String(row.Vendor || '').toLowerCase().includes(term) ||
      String(row.PN || row['Part Number'] || '').toLowerCase().includes(term)
    )
  })

  const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE)
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE
  const pageData = filteredData.slice(startIdx, startIdx + ITEMS_PER_PAGE)

  // Get status for a row
  const getRowStatus = (row) => {
    const temp = toNumber(row['Temperature (c)'] || row.Temperature)
    if (temp >= 80) return 'critical'

    const alarms = [
      row['TX Bias Alarm and Warning'],
      row['TX Power Alarm and Warning'],
      row['RX Power Alarm and Warning'],
      row['Latched Voltage Alarm and Warning']
    ]
    if (alarms.some(hasAlarmFlag)) return 'critical'

    if (temp >= 70) return 'warning'

    const complianceStatus = String(row.CableComplianceStatus || '').toLowerCase()
    const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
    if ((complianceStatus !== 'ok' && complianceStatus !== '') ||
        (speedStatus !== 'ok' && speedStatus !== '')) {
      return 'warning'
    }

    return 'ok'
  }

  const totalPorts = cableData.length
  const criticalCount = tempCritical.length + powerAlarms.length
  const warningCount = tempWarning.length + complianceIssues.length

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
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>严重问题</div>
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
          <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '8px' }}>警告</div>
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
            {totalPorts - criticalCount - warningCount}
          </div>
        </div>
      </div>

      {/* 温度严重问题 */}
      {tempCritical.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#dc2626',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Thermometer size={20} />
            🔴 温度严重过高 ({tempCritical.length}个端口)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {tempCritical.map((item, idx) => (
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
                    {item.NodeGUID || 'N/A'}
                  </div>
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>温度:</strong>{' '}
                  <span style={{ color: '#dc2626', fontWeight: 'bold' }}>{item.temp.toFixed(1)}°C</span>
                  <span style={{ color: '#6b7280' }}> (临界: 80°C)</span>
                </div>
                <div><strong>厂商:</strong> {item.vendor}</div>
                <div><strong>型号:</strong> {item.partNumber}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 光功率告警 */}
      {powerAlarms.length > 0 && (
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{
            margin: '0 0 12px 0',
            fontSize: '1.1rem',
            color: '#dc2626',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Zap size={20} />
            🔴 光功率告警 ({powerAlarms.length}个端口)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {powerAlarms.map((item, idx) => (
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
                    {item.NodeGUID || 'N/A'}
                  </div>
                </div>
                <div><strong>端口:</strong> {item.portNumber}</div>
                <div>
                  <strong>告警类型:</strong>{' '}
                  <span style={{ color: '#dc2626', fontWeight: 'bold' }}>
                    {item.alarms.join(', ')}
                  </span>
                </div>
                <div><strong>厂商:</strong> {item.vendor}</div>
                <div><strong>型号:</strong> {item.partNumber}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 温度警告 */}
      {tempWarning.length > 0 && (
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
            ⚠️ 温度偏高 ({tempWarning.length}个端口)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {tempWarning.slice(0, 5).map((item, idx) => (
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
                  <strong>温度:</strong>{' '}
                  <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>{item.temp.toFixed(1)}°C</span>
                  <span style={{ color: '#6b7280' }}> (警告: 70°C)</span>
                </div>
                <div><strong>厂商:</strong> {item.vendor}</div>
              </div>
            ))}
            {tempWarning.length > 5 && (
              <div style={{ textAlign: 'center', color: '#6b7280', fontSize: '0.9rem' }}>
                ...还有 {tempWarning.length - 5} 个端口温度偏高 (见下方完整数据表)
              </div>
            )}
          </div>
        </div>
      )}

      {/* 规格问题 */}
      {complianceIssues.length > 0 && (
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
            ⚠️ 线缆规格问题 ({complianceIssues.length}条)
          </h3>
          <div style={{ display: 'grid', gap: '12px' }}>
            {complianceIssues.slice(0, 3).map((item, idx) => (
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
                  <strong>规格状态:</strong>{' '}
                  <span style={{ color: '#f59e0b' }}>{item.complianceStatus || 'N/A'}</span>
                </div>
                <div>
                  <strong>速度状态:</strong>{' '}
                  <span style={{ color: '#f59e0b' }}>{item.speedStatus || 'N/A'}</span>
                </div>
              </div>
            ))}
            {complianceIssues.length > 3 && (
              <div style={{ textAlign: 'center', color: '#6b7280', fontSize: '0.9rem' }}>
                ...还有 {complianceIssues.length - 3} 条线缆有规格问题 (见下方完整数据表)
              </div>
            )}
          </div>
        </div>
      )}

      {/* 搜索栏 */}
      <div style={{ marginTop: '32px', marginBottom: '16px' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem', color: '#1f2937' }}>
          📋 完整线缆数据表 (可搜索/可排序)
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
            placeholder="搜索节点名、GUID、端口号、厂商..."
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
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>温度</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>厂商</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>型号</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>序列号</th>
              <th style={{ padding: '10px', textAlign: 'left', fontWeight: '600' }}>长度</th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((row, idx) => {
              const status = getRowStatus(row)
              const temp = toNumber(row['Temperature (c)'] || row.Temperature)

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
                    {status === 'critical' && <span style={{ color: '#dc2626' }}>🔴 异常</span>}
                    {status === 'warning' && <span style={{ color: '#f59e0b' }}>⚠️ 警告</span>}
                    {status === 'ok' && <span style={{ color: '#10b981' }}>✅ 正常</span>}
                  </td>
                  <td style={{ padding: '10px', fontWeight: '500' }}>{row['Node Name'] || row.NodeName || 'N/A'}</td>
                  <td style={{ padding: '10px' }}>{row.PortNumber || row['Port Number'] || 'N/A'}</td>
                  <td style={{
                    padding: '10px',
                    color: temp >= 80 ? '#dc2626' : temp >= 70 ? '#f59e0b' : '#1f2937',
                    fontWeight: temp >= 70 ? '600' : '400'
                  }}>
                    {temp > 0 ? `${temp.toFixed(1)}°C` : 'N/A'}
                  </td>
                  <td style={{ padding: '10px' }}>{row.Vendor || 'N/A'}</td>
                  <td style={{ padding: '10px', fontSize: '0.8rem' }}>{row.PN || row['Part Number'] || 'N/A'}</td>
                  <td style={{ padding: '10px', fontSize: '0.8rem', fontFamily: 'monospace' }}>
                    {row.SN || row['Serial Number'] || 'N/A'}
                  </td>
                  <td style={{ padding: '10px' }}>{row.LengthCopperOrActive || row.LengthSMFiber || row.Length || 'N/A'}</td>
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

export default CableAnalysis
