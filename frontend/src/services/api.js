/**
 * 统一的 API 服务层
 * 所有后端 API 调用集中管理
 */

import axios from 'axios'

// ============ Configuration ============
const normalizeBaseUrl = (value = '') => value.replace(/\/+$/, '')
const rawBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_URL || '')
const hasApiSuffix = rawBaseUrl.endsWith('/api')
const apiRootUrl = hasApiSuffix ? rawBaseUrl.slice(0, -4) : rawBaseUrl
const API_ENDPOINT_BASE = hasApiSuffix ? rawBaseUrl : (apiRootUrl ? `${apiRootUrl}/api` : '/api')

const MAX_FILE_SIZE = Number(import.meta.env.VITE_MAX_FILE_SIZE) || 500 * 1024 * 1024

// ============ Axios Instance ============
const apiClient = axios.create({
  baseURL: API_ENDPOINT_BASE,
  timeout: 900000, // 15 minutes
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if needed
    // const token = localStorage.getItem('token')
    // if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // Unified error handling
    const formattedError = formatError(error)
    console.error('API Error:', formattedError)
    return Promise.reject(formattedError)
  }
)

// ============ Error Formatting ============
const formatError = (err) => {
  if (err.response) {
    const { status, data } = err.response

    switch (status) {
      case 413:
        return `文件过大。最大限制为 ${MAX_FILE_SIZE / (1024 * 1024)}MB`
      case 400:
        return data?.detail || '无效的文件格式'
      case 500:
        return `服务器错误: ${data?.detail || '分析失败'}`
      default:
        return data?.detail || `服务器错误 (${status})`
    }
  }

  if (err.request) {
    return '无法连接到服务器，请检查后端是否运行'
  }

  if (err.code === 'ECONNABORTED') {
    return '请求超时。文件可能太大或服务器繁忙'
  }

  if (err.code === 'ERR_NETWORK') {
    return '网络错误。请检查后端服务器是否运行'
  }

  return err.message || '未知错误'
}

// ============ API Functions ============

/**
 * Upload IBDiagnet archive file
 * @param {File} file - .zip or .tar.gz file
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<Object>} Analysis result
 */
export const uploadIbdiagnetFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post('/upload/ibdiagnet', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      onProgress?.(percentCompleted)
    }
  })

  return response.data
}

/**
 * Upload UFM CSV file
 * @param {File} file - .csv file
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<Object>} Analysis result
 */
export const uploadCsvFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post('/upload/ufm-csv', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    timeout: 600000, // 10 minutes
    onUploadProgress: (progressEvent) => {
      const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      onProgress?.(percentCompleted)
    }
  })

  return response.data
}

/**
 * Get health check status
 * @returns {Promise<Object>} Health status
 */
export const getHealthStatus = async () => {
  const response = await apiClient.get('/health')
  return response.data
}

/**
 * Validate file before upload
 * @param {File} file - File to validate
 * @param {Array<string>} allowedExtensions - Allowed file extensions
 * @param {number} maxSize - Max file size in bytes
 * @throws {Error} If validation fails
 */
export const validateFile = (file, allowedExtensions, maxSize = MAX_FILE_SIZE) => {
  // Check file size
  if (file.size > maxSize) {
    throw new Error(`文件过大。最大限制为 ${maxSize / (1024 * 1024)}MB`)
  }

  // Check file extension
  const fileName = file.name.toLowerCase()
  const isValid = allowedExtensions.some(ext => fileName.endsWith(ext))

  if (!isValid) {
    throw new Error(`无效的文件类型。允许的类型: ${allowedExtensions.join(', ')}`)
  }

  return true
}

// ============ Constants Export ============
export const FILE_CONSTRAINTS = {
  MAX_FILE_SIZE,
  ALLOWED_ARCHIVE_TYPES: ['.zip', '.tar.gz', '.tgz'],
  ALLOWED_CSV_TYPES: ['.csv'],
}

export default apiClient
