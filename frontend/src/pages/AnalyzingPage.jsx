import { useState, useEffect, useRef } from 'react'
import { useNavigate, useLocation, useParams } from 'react-router-dom'
import { Activity, Loader, CheckCircle } from 'lucide-react'
import axios from 'axios'
import { buildApiUrl, API_CONFIG } from '../config'
import './AnalyzingPage.css'

function AnalyzingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { taskId: urlTaskId } = useParams()
  const [stage, setStage] = useState('uploading') // uploading | analyzing | completed
  const [progress, setProgress] = useState(0)
  const [currentService, setCurrentService] = useState('')
  const [message, setMessage] = useState('准备上传文件...')
  const [error, setError] = useState(null)
  const [actualTaskId, setActualTaskId] = useState(null)
  const pollIntervalRef = useRef(null)
  const uploadStartedRef = useRef(false)
  const consecutiveErrorsRef = useRef(0)

  const extractTaskId = (response) => {
    const contentType = response?.headers?.['content-type'] || ''
    const rawData = response?.data
    let parsedData = rawData

    if (typeof rawData === 'string') {
      try {
        parsedData = JSON.parse(rawData)
      } catch {
        parsedData = rawData
      }
    }

    const taskId = parsedData?.task_id
      || parsedData?.taskId
      || parsedData?.analysis?.task_id
      || parsedData?.analysis?.taskId
      || parsedData?.analysis_data?.task_id
      || parsedData?.analysis_data?.taskId

    if (!taskId) {
      if (contentType.includes('text/html')) {
        throw new Error('上传接口返回了 HTML，可能未命中 /api 后端。请检查 VITE_API_URL 或代理配置')
      }
      throw new Error(`未获取到任务ID，请检查后端响应 (${response?.status || 'unknown status'})`)
    }

    return { taskId, parsedData }
  }

  useEffect(() => {
    const { file, type } = location.state || {}

    if (!file || !type) {
      setError('缺少文件信息')
      setTimeout(() => navigate('/'), 2000)
      return
    }

    if (!uploadStartedRef.current) {
      uploadStartedRef.current = true
      startUploadAndAnalysis(file, type)
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [])

  const startUploadAndAnalysis = async (file, type) => {
    try {
      // Upload file
      setStage('uploading')
      setMessage('正在上传文件...')

      const formData = new FormData()
      formData.append('file', file)

      const endpoint = type === 'ibdiagnet'
        ? buildApiUrl('/upload/ibdiagnet')
        : buildApiUrl('/upload/ufm-csv')

      const response = await axios.post(endpoint, formData, {
        onUploadProgress: (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setProgress(percent)
          setMessage(`上传中... ${percent}%`)
        },
        timeout: API_CONFIG.TIMEOUT
      })

      const { taskId, parsedData } = extractTaskId(response)
      console.log('Upload response:', parsedData)

      setActualTaskId(taskId)

      // Show analyzing stage and start polling
      setStage('analyzing')
      setProgress(0)
      setMessage('上传完成，开始分析...')

      // Start polling for progress
      startProgressPolling(taskId)

    } catch (err) {
      console.error('Upload failed:', err)
      const errorMessage = err.response?.data?.detail || err.message || '上传失败'
      setError(errorMessage)
      setStage('error')
    }
  }

  const startProgressPolling = (taskId) => {
    // Poll immediately
    pollProgress(taskId)

    // Then poll every second
    pollIntervalRef.current = setInterval(() => {
      pollProgress(taskId)
    }, 1000)
  }

  const pollProgress = async (taskId) => {
    try {
      const response = await axios.get(buildApiUrl(`/analysis/${taskId}/progress`))
      const { stage: progressStage, progress: progressPercent, current_service, message: progressMessage } = response.data

      // Reset error counter on success
      consecutiveErrorsRef.current = 0

      setProgress(progressPercent)
      setCurrentService(current_service)
      setMessage(progressMessage || '分析中...')

      if (progressStage === 'completed') {
        setStage('completed')
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
        }

        // Navigate to results page after a short delay
        setTimeout(() => {
          navigate(`/results/${taskId}`)
        }, 1000)
      } else if (progressStage === 'error') {
        setError('分析过程中出现错误')
        setStage('error')
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
        }
      }
    } catch (err) {
      consecutiveErrorsRef.current += 1

      // Only log if it's not a network error (server restart)
      if (err.code !== 'ERR_NETWORK') {
        console.error('Failed to poll progress:', err)
      }

      // Only show error after 10 consecutive failures (10 seconds)
      if (consecutiveErrorsRef.current >= 10) {
        console.warn('Server appears to be down. Continuing to poll...')
      }

      // Don't set error state - keep polling as the analysis might still be running
    }
  }

  return (
    <div className="analyzing-page">
      <div className="analyzing-container">
        <div className="analyzing-content">
          {/* Icon */}
          <div className="analyzing-icon">
            {stage === 'completed' ? (
              <CheckCircle size={64} color="#22c55e" />
            ) : stage === 'error' ? (
              <Activity size={64} color="#ef4444" />
            ) : (
              <div className="spinner-large">
                <Loader size={64} color="#76b900" />
              </div>
            )}
          </div>

          {/* Title */}
          <h1 className="analyzing-title">
            {stage === 'uploading' && '上传文件中'}
            {stage === 'analyzing' && '分析进行中'}
            {stage === 'completed' && '分析完成'}
            {stage === 'error' && '分析失败'}
          </h1>

          {/* Message */}
          <p className="analyzing-message">{message}</p>

          {/* Progress Bar */}
          {!error && (
            <div className="progress-container">
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="progress-text">{progress}%</div>
            </div>
          )}

          {/* Current Service */}
          {stage === 'analyzing' && currentService && (
            <div className="current-service">
              <span className="service-label">当前服务：</span>
              <span className="service-name">{currentService}</span>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="error-message">
              <p>{error}</p>
              <button
                className="back-button"
                onClick={() => navigate('/')}
              >
                返回首页
              </button>
            </div>
          )}

          {/* Completion Message */}
          {stage === 'completed' && (
            <p className="completion-message">
              正在跳转到结果页面...
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalyzingPage
