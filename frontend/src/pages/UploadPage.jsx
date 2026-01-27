import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Server, FileText, Upload, Clock, ChevronDown, ChevronUp } from 'lucide-react'
import axios from 'axios'
import { buildApiUrl } from '../config'
import './UploadPage.css'

function UploadPage() {
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [showGuide, setShowGuide] = useState(false)

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    try {
      const response = await axios.get(buildApiUrl('/analysis/history?limit=10'))
      setHistory(response.data.history || [])
    } catch (error) {
      console.error('Failed to fetch history:', error)
    } finally {
      setLoadingHistory(false)
    }
  }

  const handleFileSelect = async (file, type) => {
    if (!file) return

    // Generate a temporary task ID for navigation
    const tempTaskId = `temp-${Date.now()}`

    // Navigate to analyzing page with file data
    navigate(`/analyzing/${tempTaskId}`, {
      state: { file, type }
    })
  }

  const handleHistoryClick = (taskId) => {
    navigate(`/results/${taskId}`)
  }

  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return dateString
    }
  }

  return (
    <div className="upload-page">
      <header className="upload-header">
        <div className="header-content">
          <div className="brand">
            <div className="brand-mark">
              <Activity size={28} color="#76b900" />
            </div>
            <div className="brand-text">
              <span className="brand-title">NVIDIA Network Health</span>
              <span className="brand-subtitle">Enterprise Diagnostic Platform</span>
            </div>
          </div>
          <div className="brand-pill">Enterprise Console</div>
        </div>
      </header>

      <main className="upload-main">
        <div className="upload-container">
          <section className="upload-hero">
            <div className="hero-text">
              <h2>网络健康诊断分析</h2>
              <p>上传 IBDiagnet 或 UFM CSV 文件，快速生成企业级健康报告与修复建议。</p>
              <div className="hero-tags">
                <span>实时诊断</span>
                <span>异常分级</span>
                <span>行动建议</span>
              </div>
            </div>
            <div className="hero-panel">
              <div className="panel-title">支持文件</div>
              <div className="panel-items">
                <div>
                  <strong>IBDiagnet</strong>
                  <span>.zip / .tar.gz</span>
                </div>
                <div>
                  <strong>UFM CSV</strong>
                  <span>low_freq_debug 等</span>
                </div>
              </div>
            </div>
          </section>

          <div className="upload-layout">
            <div className="upload-primary">
              <div className="upload-cards">
                <div className="upload-card">
                  <div className="card-icon">
                    <Server size={32} color="#76b900" />
                  </div>
                  <h3>IBDiagnet 分析</h3>
                  <p>上传 .zip 或 .tar.gz 格式的 ibdiagnet 输出文件</p>
                  <input
                    type="file"
                    accept=".zip,.tar.gz"
                    onChange={(e) => handleFileSelect(e.target.files[0], 'ibdiagnet')}
                    className="file-input"
                    id="ibdiagnet-upload"
                  />
                  <label htmlFor="ibdiagnet-upload" className="upload-button">
                    <Upload size={20} />
                    选择文件
                  </label>
                </div>

                <div className="upload-card">
                  <div className="card-icon">
                    <FileText size={32} color="#76b900" />
                  </div>
                  <h3>UFM CSV 分析</h3>
                  <p>上传 UFM 命令输出的 CSV 文件（如 low_freq_debug）</p>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => handleFileSelect(e.target.files[0], 'csv')}
                    className="file-input"
                    id="csv-upload"
                  />
                  <label htmlFor="csv-upload" className="upload-button">
                    <Upload size={20} />
                    选择文件
                  </label>
                </div>
              </div>
            </div>

            <div className="upload-secondary">
              <div className="guide-section">
                <button
                  className="guide-toggle"
                  onClick={() => setShowGuide(!showGuide)}
                >
                  <span>📖 采集指导</span>
                  {showGuide ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>

                {showGuide && (
                  <div className="guide-content">
                    <div className="guide-item">
                      <h4>IBDiagnet 采集步骤（Docker 环境）：</h4>
                      <ol>
                        <li>查看运行的 Docker 容器：<code>docker ps</code></li>
                        <li>进入 UFM 容器：<code>docker exec -it ufm /bin/bash</code></li>
                        <li>执行诊断命令：
                          <code className="code-block">
                            /opt/ufm/opensm/bin/ibdiagnet --sc --extended_speeds all -P all=1 --pm_per_lane --get_cable_info -w ibdiagnet2.topo --cable_info_disconnected --get_phy_info --routing --sharp --phy_cable_disconnected --rail_validation --get_p_info
                          </code>
                        </li>
                        <li>打包生成的文件：<code>tar -czvf ibdiagnet2_$(date +%Y-%m-%d_%H).tar.gz /var/tmp/ibdiagnet2/*</code></li>
                        <li>退出容器：<code>exit</code></li>
                        <li>复制文件到宿主机：<code>docker cp ufm:/root/ibdiagnet2_2025-xx-xx_08.tar.gz /root/</code></li>
                        <li>下载并上传该文件</li>
                      </ol>
                    </div>

                    <div className="guide-item">
                      <h4>UFM CSV 采集步骤：</h4>
                      <ol>
                        <li>在 UFM 服务器上执行命令：
                          <code className="code-block">
                            curl -s 127.0.0.1:9002/csv/xcset/low_freq_debug &gt;low_freq_debug.csv
                          </code>
                        </li>
                        <li>下载生成的 low_freq_debug.csv 文件并上传</li>
                      </ol>
                    </div>
                  </div>
                )}
              </div>

              {!loadingHistory && history.length > 0 && (
                <div className="history-section">
                  <h3>
                    <Clock size={20} />
                    最近分析记录
                  </h3>
                  <div className="history-list">
                    {history.map((record) => (
                      <div
                        key={record.task_id}
                        className="history-item"
                        onClick={() => handleHistoryClick(record.task_id)}
                      >
                        <div className="history-icon">
                          {record.file_type === 'ibdiagnet' ? (
                            <Server size={20} />
                          ) : (
                            <FileText size={20} />
                          )}
                        </div>
                        <div className="history-info">
                          <div className="history-name">{record.file_name}</div>
                          <div className="history-date">{formatDate(record.created_at)}</div>
                        </div>
                        <div className="history-status">
                          {record.status === 'completed' && (
                            <span className="status-badge success">已完成</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default UploadPage
