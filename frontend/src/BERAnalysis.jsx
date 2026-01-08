import { useMemo, useState } from 'react'

const ITEMS_PER_PAGE = 20

const normalizeValue = (value, fallback = 'N/A') => {
  if (value === null || value === undefined) {
    return fallback
  }
  const str = String(value).trim()
  return str.length ? str : fallback
}

const formatExponent = (exp) => {
  const sign = exp >= 0 ? '+' : '-'
  const absValue = Math.abs(exp)
  return `${sign}${String(absValue).padStart(3, '0')}`
}

const formatBer = (value) => {
  const num = Number(value)
  if (!Number.isFinite(num) || num < 0) {
    return 'N/A'
  }
  if (num === 0) {
    return '0.00E+00'
  }
  const exponent = Math.floor(Math.log10(num))
  const mantissa = num / Math.pow(10, exponent)
  return `${mantissa.toFixed(2)}E${formatExponent(exponent)}`
}

const pickFormattedBer = (directCandidates = [], numericCandidates = [], logCandidates = []) => {
  for (const candidate of directCandidates) {
    if (candidate === null || candidate === undefined) continue
    const text = String(candidate).trim()
    if (text.length && text !== 'nan') {
      return text
    }
  }
  for (const candidate of numericCandidates) {
    const num = Number(candidate)
    if (Number.isFinite(num)) {
      return formatBer(num)
    }
  }
  for (const candidate of logCandidates) {
    const logValue = Number(candidate)
    if (Number.isFinite(logValue)) {
      return formatBer(Math.pow(10, logValue))
    }
  }
  return 'N/A'
}

const extractSymbolBer = (row) => {
  return pickFormattedBer(
    [row['Symbol BER'], row.SymbolBER, row.symbolBer],
    [row.SymbolBERValue],
    [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
  )
}

const mergeRows = (berData, berAdvancedData) => {
  const combined = []
  if (Array.isArray(berData)) {
    combined.push(...berData.map(row => ({ ...row })))
  }
  if (Array.isArray(berAdvancedData)) {
    berAdvancedData.forEach(row => {
      const guid = row.NodeGUID || row['Node GUID']
      const port = row.PortNumber || row['Port Number']
      const existingIndex = combined.findIndex(
        item => (item.NodeGUID || item['Node GUID']) === guid && (item.PortNumber || item['Port Number']) === port
      )
      if (existingIndex === -1) {
        combined.push({ ...row })
      } else {
        combined[existingIndex] = { ...combined[existingIndex], ...row }
      }
    })
  }
  return combined
}

const buildDisplayRows = (rows) => rows.map((row, index) => {
  const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
  const fallbackAnomaly = ['critical', 'warning'].includes(severity) ? 'High Symbol BER' : ''

  return {
    id: `${row.NodeGUID || row['Node GUID'] || index}-${row.PortNumber || row['Port Number'] || ''}`,
    nodeGuid: normalizeValue(row.NodeGUID || row['Node GUID'], 'N/A'),
    portNumber: normalizeValue(row.PortNumber || row['Port Number'], 'N/A'),
    nodeName: normalizeValue(row['Node Name'] || row.NodeName, 'N/A'),
    attachedTo: normalizeValue(row['Attached To'] || row.AttachedTo, 'N/A'),
    rawBer: pickFormattedBer(
      [row['Raw BER'], row.RawBER, row.rawBer],
      [row.RawBERValue],
      [row['Log10 Raw BER']]
    ),
    effectiveBer: pickFormattedBer(
      [row['Effective BER'], row.EffectiveBER, row.effectiveBer],
      [row.EffectiveBERValue],
      [row['Log10 Effective BER']]
    ),
    symbolBer: pickFormattedBer(
      [row['Symbol BER'], row.SymbolBER, row.symbolBer],
      [row.SymbolBERValue],
      [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
    ),
    ibhAnomaly: normalizeValue(row['IBH Anomaly'] || row.IBHAnomaly || fallbackAnomaly, ''),
  }
})

function BERAnalysis({ berData = [], berAdvancedData = [], showOnlyProblematic = false }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [showProblemsOnly, setShowProblemsOnly] = useState(showOnlyProblematic)

  const displayRows = useMemo(() => {
    const merged = mergeRows(berData, berAdvancedData)
    return buildDisplayRows(merged)
  }, [berData, berAdvancedData])

  const problemRows = useMemo(() => displayRows.filter(row => !!row.ibhAnomaly), [displayRows])

  if (displayRows.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
        <p>无BER数据</p>
      </div>
    )
  }

  const rowsForView = showProblemsOnly ? problemRows : displayRows
  const term = searchTerm.trim().toLowerCase()
  const filteredRows = term
    ? rowsForView.filter(row =>
        Object.values(row).some(value =>
          typeof value === 'string' && value.toLowerCase().includes(term)
        )
      )
    : rowsForView

  const totalRows = filteredRows.length

  const totalPages = Math.max(1, Math.ceil(totalRows / ITEMS_PER_PAGE))
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const pageRows = filteredRows.slice(startIndex, startIndex + ITEMS_PER_PAGE)

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#111827' }}>BER 测试结果</h2>
        <p style={{ margin: '4px 0 0 0', color: '#6b7280' }}>
          展示格式与 <code>/test_data/ber(1).csv</code> 一致，便于核对离线样例。
        </p>
      </div>

      <div style={{ marginBottom: '12px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '220px' }}>
          <input
            type="text"
            value={searchTerm}
            onChange={(event) => {
              setSearchTerm(event.target.value)
              setCurrentPage(1)
            }}
            placeholder="搜索 NodeGUID、端口、节点或 IBH Anomaly..."
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '0.95rem'
            }}
          />
        </div>
        <button
          onClick={() => {
            setShowProblemsOnly(prev => !prev)
            setCurrentPage(1)
          }}
          style={{
            padding: '10px 14px',
            borderRadius: '6px',
            border: '1px solid #d1d5db',
            background: showProblemsOnly ? '#fef3c7' : '#f3f4f6',
            color: '#374151',
            cursor: 'pointer',
            minWidth: '140px'
          }}
        >
          {showProblemsOnly ? '显示全部端口' : '只看异常端口'}
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: 'white' }}>
          <thead>
            <tr style={{ background: '#f3f4f6', borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ textAlign: 'left', padding: '10px' }}>Node GUID</th>
              <th style={{ textAlign: 'left', padding: '10px' }}>Port Number</th>
              <th style={{ textAlign: 'left', padding: '10px' }}>Node Name</th>
              <th style={{ textAlign: 'left', padding: '10px' }}>Attached To</th>
              <th style={{ textAlign: 'left', padding: '10px' }}>Raw BER</th>
              <th style={{ textAlign: 'left', padding: '10px' }}>Effective BER</th>
              <th style={{ textAlign: 'left', padding: '10px' }}>Symbol BER</th>
              <th style={{ textAlign: 'left', padding: '10px' }}>IBH Anomaly</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => (
              <tr key={row.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: '10px', fontFamily: 'monospace' }}>{row.nodeGuid}</td>
                <td style={{ padding: '10px' }}>{row.portNumber}</td>
                <td style={{ padding: '10px' }}>{row.nodeName}</td>
                <td style={{ padding: '10px' }}>{row.attachedTo}</td>
                <td style={{ padding: '10px', fontFamily: 'monospace' }}>{row.rawBer}</td>
                <td style={{ padding: '10px', fontFamily: 'monospace' }}>{row.effectiveBer}</td>
                <td style={{ padding: '10px', fontFamily: 'monospace' }}>{row.symbolBer}</td>
                <td style={{ padding: '10px', color: row.ibhAnomaly ? '#dc2626' : '#4b5563' }}>{row.ibhAnomaly || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
        <span style={{ color: '#6b7280', fontSize: '0.9rem' }}>
          共 {totalRows} 条记录（第 {currentPage} / {totalPages} 页）
        </span>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
            disabled={currentPage === 1}
            style={{
              padding: '6px 12px',
              borderRadius: '4px',
              border: 'none',
              background: currentPage === 1 ? '#e5e7eb' : '#3b82f6',
              color: currentPage === 1 ? '#9ca3af' : 'white',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
            }}
          >
            上一页
          </button>
          <button
            onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: '6px 12px',
              borderRadius: '4px',
              border: 'none',
              background: currentPage === totalPages ? '#e5e7eb' : '#3b82f6',
              color: currentPage === totalPages ? '#9ca3af' : 'white',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
            }}
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  )
}

export default BERAnalysis
