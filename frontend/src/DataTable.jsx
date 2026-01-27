import { useEffect, useMemo, useState } from 'react'
import { ensureArray } from './analysisUtils'

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
      <div className="data-table-toolbar">
        <input
          type="text"
          placeholder={searchPlaceholder}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="data-table-search"
        />
        {sortConfig?.key && (
          <button
            onClick={() => setSortConfig(null)}
            className="data-table-reset"
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
                  className="data-table-sort"
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
                  return <td key={col} className="data-table-cell-mono">{JSON.stringify(value)}</td>
                }
                return <td key={col}>{String(value)}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="data-table-pagination">
        <div className="data-table-pagination-controls">
          <button
            className="data-table-page-btn"
            disabled={currentPage === 1}
            onClick={() => setPage(Math.max(1, currentPage - 1))}
          >
            Previous
          </button>
          <button
            className="data-table-page-btn"
            disabled={currentPage === totalPages}
            onClick={() => setPage(Math.min(totalPages, currentPage + 1))}
          >
            Next
          </button>
        </div>
        <span className="data-table-page-info">
          Page {currentPage} / {totalPages}
        </span>
      </div>
      <p className="data-table-summary">
        显示第 {startIndex + 1}-{endIndex} 行，共 {totalRecords} 行
      </p>
    </div>
  )
}

export default DataTable
