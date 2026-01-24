/**
 * 统一错误展示组件
 */

import { AlertTriangle } from 'lucide-react'

export default function ErrorDisplay({ error, onDismiss }) {
  if (!error) return null

  return (
    <div style={{
      color: '#c53030',
      background: '#fff5f5',
      padding: '10px',
      borderRadius: '4px',
      border: '1px solid #fed7d7',
      marginBottom: '1rem'
    }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <AlertTriangle size={16} />
        <strong>错误</strong>
        {onDismiss && (
          <button
            onClick={onDismiss}
            style={{
              marginLeft: 'auto',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontSize: '1.2rem'
            }}
          >
            ×
          </button>
        )}
      </div>
      <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem' }}>{error}</p>
    </div>
  )
}
