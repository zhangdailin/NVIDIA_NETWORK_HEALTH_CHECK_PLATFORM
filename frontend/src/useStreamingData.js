import { useState, useEffect, useCallback, useRef } from 'react'

/**
 * Custom hook for streaming data using Server-Sent Events (SSE)
 *
 * @param {string} taskId - The analysis task ID
 * @param {string} serviceName - The service name (e.g., 'cable', 'xmit', 'ber')
 * @param {boolean} enabled - Whether to start streaming
 * @returns {Object} - { data, loading, error, progress, total }
 */
export function useStreamingData(taskId, serviceName, enabled = true) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [progress, setProgress] = useState({ loaded: 0, total: 0 })
  const eventSourceRef = useRef(null)
  const accumulatedDataRef = useRef([])

  const startStreaming = useCallback(() => {
    if (!taskId || !serviceName || !enabled) {
      return
    }

    // Reset state
    setData([])
    setLoading(true)
    setError(null)
    setProgress({ loaded: 0, total: 0 })
    accumulatedDataRef.current = []

    // Construct streaming URL
    const baseUrl = import.meta.env.VITE_API_URL || ''
    const apiBase = baseUrl.endsWith('/api') ? baseUrl : `${baseUrl}/api`
    const streamUrl = `${apiBase}/stream/${taskId}/${serviceName}`

    console.log(`[useStreamingData] Starting stream: ${streamUrl}`)

    // Create EventSource
    const eventSource = new EventSource(streamUrl)
    eventSourceRef.current = eventSource

    // Handle metadata event
    eventSource.addEventListener('metadata', (event) => {
      try {
        const metadata = JSON.parse(event.data)
        console.log(`[useStreamingData] Metadata received:`, metadata)
        setProgress({ loaded: 0, total: metadata.total })
      } catch (err) {
        console.error('[useStreamingData] Failed to parse metadata:', err)
      }
    })

    // Handle data event
    eventSource.addEventListener('data', (event) => {
      try {
        const chunk = JSON.parse(event.data)
        console.log(`[useStreamingData] Chunk ${chunk.chunk_index} received: ${chunk.data.length} rows`)

        // Accumulate data
        accumulatedDataRef.current = [...accumulatedDataRef.current, ...chunk.data]

        // Update state
        setData([...accumulatedDataRef.current])
        setProgress({ loaded: chunk.end, total: progress.total || chunk.end })
      } catch (err) {
        console.error('[useStreamingData] Failed to parse data chunk:', err)
      }
    })

    // Handle complete event
    eventSource.addEventListener('complete', (event) => {
      try {
        const result = JSON.parse(event.data)
        console.log(`[useStreamingData] Stream complete:`, result)
        setLoading(false)
        setProgress({ loaded: result.total, total: result.total })
        eventSource.close()
      } catch (err) {
        console.error('[useStreamingData] Failed to parse complete event:', err)
        setLoading(false)
        eventSource.close()
      }
    })

    // Handle error event
    eventSource.addEventListener('error', (event) => {
      console.error('[useStreamingData] Stream error:', event)

      try {
        if (event.data) {
          const errorData = JSON.parse(event.data)
          setError(errorData.error || 'Stream error occurred')
        } else {
          setError('Connection error')
        }
      } catch (err) {
        setError('Stream connection failed')
      }

      setLoading(false)
      eventSource.close()
    })

    // Handle connection open
    eventSource.onopen = () => {
      console.log('[useStreamingData] Connection opened')
    }

    // Handle generic errors
    eventSource.onerror = (err) => {
      console.error('[useStreamingData] EventSource error:', err)

      // Only set error if we haven't received any data yet
      if (accumulatedDataRef.current.length === 0) {
        setError('Failed to connect to streaming endpoint')
        setLoading(false)
      }

      eventSource.close()
    }

  }, [taskId, serviceName, enabled])

  // Start streaming when dependencies change
  useEffect(() => {
    if (enabled && taskId && serviceName) {
      startStreaming()
    }

    // Cleanup function
    return () => {
      if (eventSourceRef.current) {
        console.log('[useStreamingData] Closing EventSource')
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }
  }, [taskId, serviceName, enabled, startStreaming])

  return {
    data,
    loading,
    error,
    progress,
    total: progress.total,
    loaded: progress.loaded,
    percentage: progress.total > 0 ? Math.round((progress.loaded / progress.total) * 100) : 0
  }
}

export default useStreamingData
