/**
 * 侧边栏 - 文件上传区域
 */

import { Server, FileText } from 'lucide-react'
import ErrorDisplay from './ErrorDisplay'
import { useAppStore } from '../store/appStore'

export default function Sidebar({ onIbdiagnetUpload, onCsvUpload, loading }) {
  const { error, clearError } = useAppStore()

  const handleIbdiagnetChange = (event) => {
    const file = event.target.files[0]
    if (file) {
      onIbdiagnetUpload(file)
      event.target.value = '' // Reset input
    }
  }

  const handleCsvChange = (event) => {
    const file = event.target.files[0]
    if (file) {
      onCsvUpload(file)
      event.target.value = '' // Reset input
    }
  }

  return (
    <div className="sidebar">
      {/* IBDiagnet Upload */}
      <div className="upload-card">
        <h3><Server size={20} /> IBDiagnet 分析</h3>
        <p>上传 .zip / .tar.gz 格式的 ibdiagnet 结果。</p>
        <div className="file-input-wrapper">
          <input
            type="file"
            accept=".zip,.tar.gz,.tgz"
            onChange={handleIbdiagnetChange}
            disabled={loading}
          />
        </div>
      </div>

      {/* CSV Upload */}
      <div className="upload-card">
        <h3><FileText size={20} /> UFM CSV 分析</h3>
        <p>上传命令 CSV（例如 low_freq_debug）。</p>
        <div className="file-input-wrapper">
          <input
            type="file"
            accept=".csv"
            onChange={handleCsvChange}
            disabled={loading}
          />
        </div>
      </div>

      {/* Error Display */}
      {error && <ErrorDisplay error={error} onDismiss={clearError} />}
    </div>
  )
}
