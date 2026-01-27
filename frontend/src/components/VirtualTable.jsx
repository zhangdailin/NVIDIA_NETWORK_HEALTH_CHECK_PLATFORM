import { useMemo, useRef, useCallback } from 'react'
import { FixedSizeList } from 'react-window'
import './VirtualTable.css'

/**
 * 高性能虚拟滚动表格组件
 * 适用于大数据集（1000+ 行）
 */
const VirtualTable = ({
  data = [],
  columns = [],
  rowHeight = 50,
  headerHeight = 45,
  height = 600,
  onRowClick = null,
  className = '',
}) => {
  const listRef = useRef()

  // 渲染表头
  const renderHeader = () => (
    <div className="virtual-table-header" style={{ height: headerHeight }}>
      {columns.map((col, index) => (
        <div
          key={col.key || index}
          className="virtual-table-header-cell"
          style={{ flex: col.width || 1 }}
        >
          {col.label || col.key}
        </div>
      ))}
    </div>
  )

  // 渲染单行
  const Row = useCallback(({ index, style }) => {
    const row = data[index]
    if (!row) return null

    return (
      <div
        style={style}
        className={`virtual-table-row ${onRowClick ? 'clickable' : ''}`}
        onClick={() => onRowClick?.(row, index)}
      >
        {columns.map((col, colIndex) => {
          let value = row[col.key]

          // 使用自定义渲染函数
          if (col.render) {
            value = col.render(row, index)
          }

          return (
            <div
              key={col.key || colIndex}
              className="virtual-table-cell"
              style={{ flex: col.width || 1 }}
              title={String(value)}
            >
              {value ?? 'N/A'}
            </div>
          )
        })}
      </div>
    )
  }, [data, columns, onRowClick])

  // 如果没有数据
  if (!data || data.length === 0) {
    return (
      <div className={`virtual-table-container ${className}`}>
        {renderHeader()}
        <div className="virtual-table-empty">
          <p>暂无数据</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`virtual-table-container ${className}`}>
      {renderHeader()}
      <FixedSizeList
        ref={listRef}
        height={height - headerHeight}
        itemCount={data.length}
        itemSize={rowHeight}
        width="100%"
        className="virtual-table-list"
      >
        {Row}
      </FixedSizeList>
      <div className="virtual-table-footer">
        共 {data.length.toLocaleString()} 行
      </div>
    </div>
  )
}

export default VirtualTable
