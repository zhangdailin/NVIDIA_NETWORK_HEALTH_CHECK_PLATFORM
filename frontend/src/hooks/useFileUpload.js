/**
 * 文件上传自定义 Hook
 * 封装上传逻辑，分离业务逻辑和UI
 */

import { useCallback } from 'react'
import { uploadIbdiagnetFile, uploadCsvFile, validateFile, FILE_CONSTRAINTS } from '../services/api'
import { useAppStore } from '../store/appStore'

export const useFileUpload = () => {
  const {
    setLoading,
    setUploadProgress,
    setError,
    setResult,
    setActiveTab,
    clearError,
  } = useAppStore()

  /**
   * Upload IBDiagnet archive file
   */
  const uploadIbdiagnet = useCallback(async (file) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setActiveTab('overview')
    setUploadProgress(0)

    try {
      // Validate file
      validateFile(file, FILE_CONSTRAINTS.ALLOWED_ARCHIVE_TYPES)

      // Upload
      const data = await uploadIbdiagnetFile(file, (progress) => {
        setUploadProgress(progress)
      })

      setResult({ type: 'ibdiagnet', data })
      setUploadProgress(100)
    } catch (err) {
      console.error('Upload error:', err)
      setError(err.message || err)
    } finally {
      setLoading(false)
    }
  }, [setLoading, setUploadProgress, setError, setResult, setActiveTab, clearError])

  /**
   * Upload CSV file
   */
  const uploadCsv = useCallback(async (file) => {
    setLoading(true)
    setError(null)
    setResult(null)
    setActiveTab('data')
    setUploadProgress(0)

    try {
      // Validate file
      validateFile(file, FILE_CONSTRAINTS.ALLOWED_CSV_TYPES)

      // Upload
      const data = await uploadCsvFile(file, (progress) => {
        setUploadProgress(progress)
      })

      setResult({ type: 'csv', data })
      setUploadProgress(100)
    } catch (err) {
      console.error('Upload error:', err)
      setError(err.message || err)
    } finally {
      setLoading(false)
    }
  }, [setLoading, setUploadProgress, setError, setResult, setActiveTab, clearError])

  return {
    uploadIbdiagnet,
    uploadCsv,
  }
}
