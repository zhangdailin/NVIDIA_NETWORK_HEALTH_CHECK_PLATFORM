/**
 * 统一配置管理
 * 集中管理所有环境变量和配置项
 */

// API配置
const normalizeBaseUrl = (value = '') => value.replace(/\/+$/, '')
const rawBaseUrl = normalizeBaseUrl(import.meta.env.VITE_API_URL || '')
const hasApiSuffix = rawBaseUrl.endsWith('/api')
const apiRootUrl = hasApiSuffix ? rawBaseUrl.slice(0, -4) : rawBaseUrl

export const API_CONFIG = {
  BASE_URL: hasApiSuffix ? rawBaseUrl : (apiRootUrl ? `${apiRootUrl}/api` : '/api'),
  TIMEOUT: 900000, // 15 minutes
  MAX_FILE_SIZE: Number(import.meta.env.VITE_MAX_FILE_SIZE) || 500 * 1024 * 1024, // 500MB
}

// 文件上传配置
export const UPLOAD_CONFIG = {
  MAX_SIZE_MB: 500,
  ALLOWED_ARCHIVE_TYPES: ['.zip', '.tar.gz', '.tgz'],
  ALLOWED_CSV_TYPES: ['.csv'],
}

// 业务配置
export const BUSINESS_CONFIG = {
  RECENT_REBOOT_THRESHOLD_HOURS: 1,
  MAX_PREVIEW_ROWS: 100,
}

// UI配置
export const UI_CONFIG = {
  DEFAULT_PAGE_SIZE: 20,
  CHART_COLORS: {
    primary: '#76b900', // NVIDIA green
    success: '#22c55e',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6',
  },
}

// 构建API URL
export const buildApiUrl = (path = '') => `${API_CONFIG.BASE_URL}${path}`
