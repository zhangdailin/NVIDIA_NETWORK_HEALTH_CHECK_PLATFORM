import { useEffect, useMemo, useState } from 'react'

const ensureArray = (value) => (Array.isArray(value) ? value : [])
const DEFAULT_PAGE_SIZE = 100

const normalizeSearchValue = (value) => {
  if (value === null || value === undefined) return ''
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const compareValues = (a, b) => {
  const aNumber = Number(a)
  const bNumber = Number(b)
  const aIsNumber = Number.isFinite(aNumber)
  const bIsNumber = Number.isFinite(bNumber)
  if (aIsNumber && bIsNumber) {
    return aNumber - bNumber
  }
  const aText = normalizeSearchValue(a).toLowerCase()
  const bText = normalizeSearchValue(b).toLowerCase()
  return aText.localeCompare(bText, undefined, { numeric: true, sensitivity: 'base' })
}

const buildColumnOrder = (rows, preferredColumns = [], hiddenColumns = []) => {
  const columnSet = new Set()
  ensureArray(rows).forEach(row => {
    if (!row || typeof row !== 'object') return
    Object.keys(row).forEach(key => {
      if (!key) return
      if (hiddenColumns.includes(key)) return
      if (key.startsWith('__')) return
      columnSet.add(key)
    })
  })
  const pinned = ensureArray(preferredColumns).filter(col => columnSet.has(col))
  const remainder = Array.from(columnSet).filter(col => !pinned.includes(col))
  return [...pinned, ...remainder]
}

function DataTable({
  rows,
  totalRows,
  emptyDebug,
  pageSize = DEFAULT_PAGE_SIZE,
  searchPlaceholder = '搜索任意字段...',
  preferredColumns = [],
  defaultSortKey = null,
  hiddenColumns = [],
}) {
  const data = ensureArray(rows)
  const [page, setPage] = useState(1)
  const [searchTerm, setSearchTerm] = useState('')
  const [sortConfig, setSortConfig] = useState(defaultSortKey ? { key: defaultSortKey, direction: 'desc' } : null)

  useEffect(() => {
    setPage(1)
  }, [rows, searchTerm])

  const columns = useMemo(() => buildColumnOrder(data, preferredColumns, hiddenColumns), [data, preferredColumns, hiddenColumns])

  const filteredRows = useMemo(() => {
    if (!searchTerm) return data
    const lower = searchTerm.toLowerCase()
    return data.filter(row =>
      columns.some(col => normalizeSearchValue(row?.[col]).toLowerCase().includes(lower))
    )
  }, [columns, data, searchTerm])

  const sortedRows = useMemo(() => {
    if (!sortConfig?.key) return filteredRows
    const { key, direction } = sortConfig
    const factor = direction === 'desc' ? -1 : 1
    return [...filteredRows].sort((a, b) => factor * compareValues(a?.[key], b?.[key]))
  }, [filteredRows, sortConfig])

  useEffect(() => {
    setPage(1)
  }, [sortConfig])

  if (!data.length) {
    if (emptyDebug?.stderr || emptyDebug?.stdout) {
      return (
        <div>
          <p>No structured data available.</p>
          {emptyDebug.stderr && (
            <div style={{ marginTop: '20px' }}>
              <h4>Debug Error Log:</h4>
              <pre style={{ color: 'red' }}>{emptyDebug.stderr}</pre>
            </div>
          )}
          {emptyDebug.stdout && (
            <div style={{ marginTop: '20px' }}>
              <h4>Debug Output Log:</h4>
              <pre>{emptyDebug.stdout}</pre>
            </div>
          )}
        </div>
      )
    }
    return <p>No data available.</p>
  }

  if (!columns.length) {
    return <p>No structured columns available.</p>
  }

  const totalRecords = Number.isFinite(totalRows) && totalRows > 0 ? totalRows : data.length
  const previewTrimmed = totalRecords > data.length
  const totalPages = Math.max(1, Math.ceil(sortedRows.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const startIndex = (currentPage - 1) * pageSize
  const endIndex = Math.min(startIndex + pageSize, sortedRows.length)
  const displayRows = sortedRows.slice(startIndex, endIndex)

  const toggleSort = (column) => {
    setSortConfig(prev => {
      if (!prev || prev.key !== column) {
        return { key: column, direction: 'asc' }
      }
      if (prev.direction === 'asc') {
        return { key: column, direction: 'desc' }
      }
      return null
    })
  }

  const renderSortIndicator = (column) => {
    if (!sortConfig || sortConfig.key !== column) return null
    return sortConfig.direction === 'asc' ? '▲' : '▼'
  }

  return (
    <div className="table-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
        <input
          type="text"
          placeholder={searchPlaceholder}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{ flex: '1', minWidth: '240px', padding: '8px 10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
        />
        {sortConfig?.key && (
          <button
            onClick={() => setSortConfig(null)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', background: '#fff' }}
          >
            清除排序
          </button>
        )}
      </div>
      <table>
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col}>
                <button
                  type="button"
                  onClick={() => toggleSort(col)}
                  style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}
                >
                  <span>{col}</span>
                  <span>{renderSortIndicator(col)}</span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayRows.map((row, idx) => (
            <tr key={`${currentPage}-${idx}`}>
              {columns.map(col => {
                const value = row?.[col]
                if (value === null || value === undefined) {
                  return <td key={col}>—</td>
                }
                if (typeof value === 'object') {
                  return <td key={col} style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{JSON.stringify(value)}</td>
                }
                return <td key={col}>{String(value)}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            style={{ padding: '6px 12px', borderRadius: '4px', border: '1px solid #1f2937', background: '#0f172a', color: '#e2e8f0', cursor: currentPage === 1 ? 'not-allowed' : 'pointer', opacity: currentPage === 1 ? 0.4 : 1 }}
            disabled={currentPage === 1}
            onClick={() => setPage(Math.max(1, currentPage - 1))}
          >
            Previous
          </button>
          <button
            style={{ padding: '6px 12px', borderRadius: '4px', border: '1px solid #1f2937', background: '#0f172a', color: '#e2e8f0', cursor: currentPage === totalPages ? 'not-allowed' : 'pointer', opacity: currentPage === totalPages ? 0.4 : 1 }}
            disabled={currentPage === totalPages}
            onClick={() => setPage(Math.min(totalPages, currentPage + 1))}
          >
            Next
          </button>
        </div>
        <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
          Page {currentPage} / {totalPages}
        </span>
      </div>
      <p style={{ marginTop: '10px', fontSize: '0.85rem', color: '#94a3b8' }}>
        Showing rows {startIndex + 1}-{endIndex} of {totalRecords} rows. {previewTrimmed ? `Only ${data.length} rows are included in this preview.` : ''}
      </p>
      {previewTrimmed && (
        <p style={{ marginTop: '4px', fontSize: '0.8rem', color: '#94a3b8' }}>
          Sorting与搜索仅作用于当前预览行，如需完整数据请下载原始 ibdiagnet 包。
        </p>
      )}
    </div>
  )
}

export default DataTable
