import PropTypes from 'prop-types'

/**
 * Loading progress bar component for streaming data
 */
function StreamingProgress({ loaded, total, percentage, loading }) {
  if (!loading && loaded === 0) {
    return null
  }

  return (
    <div style={{
      padding: '16px',
      background: '#f0f9ff',
      border: '1px solid #bae6fd',
      borderRadius: '8px',
      marginBottom: '16px'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px'
      }}>
        <span style={{ fontSize: '0.875rem', fontWeight: 500, color: '#0369a1' }}>
          {loading ? '正在加载数据...' : '数据加载完成'}
        </span>
        <span style={{ fontSize: '0.875rem', color: '#0369a1' }}>
          {loaded.toLocaleString()} / {total.toLocaleString()} 行 ({percentage}%)
        </span>
      </div>

      {/* Progress bar */}
      <div style={{
        width: '100%',
        height: '8px',
        background: '#e0f2fe',
        borderRadius: '4px',
        overflow: 'hidden'
      }}>
        <div style={{
          width: `${percentage}%`,
          height: '100%',
          background: loading ? '#0ea5e9' : '#10b981',
          transition: 'width 0.3s ease',
          borderRadius: '4px'
        }} />
      </div>

      {loading && (
        <div style={{
          marginTop: '8px',
          fontSize: '0.75rem',
          color: '#64748b',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <div style={{
            width: '12px',
            height: '12px',
            border: '2px solid #0ea5e9',
            borderTopColor: 'transparent',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite'
          }} />
          <span>数据正在流式传输中，请稍候...</span>
        </div>
      )}

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

StreamingProgress.propTypes = {
  loaded: PropTypes.number.isRequired,
  total: PropTypes.number.isRequired,
  percentage: PropTypes.number.isRequired,
  loading: PropTypes.bool.isRequired
}

export default StreamingProgress
