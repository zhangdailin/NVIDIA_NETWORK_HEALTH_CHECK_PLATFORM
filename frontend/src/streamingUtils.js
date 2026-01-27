/**
 * 流式数据处理工具
 * 支持 Per-Lane Performance, Power Sensors, Port Hierarchy, QoS 等所有数据类型
 */
import { buildApiUrl } from './config'

/**
 * 使用 Server-Sent Events (SSE) 获取流式数据
 * @param {string} taskId - 任务ID
 * @param {string} serviceName - 服务名称 (例如: 'per_lane_performance', 'power_sensors', 'port_hierarchy', 'qos')
 * @param {Object} callbacks - 回调函数
 * @param {Function} callbacks.onMetadata - 接收元数据时调用
 * @param {Function} callbacks.onData - 接收数据块时调用
 * @param {Function} callbacks.onComplete - 完成时调用
 * @param {Function} callbacks.onError - 错误时调用
 * @returns {Function} 取消函数
 */
export function streamServiceData(taskId, serviceName, callbacks = {}) {
  const { onMetadata, onData, onComplete, onError } = callbacks

  const url = buildApiUrl(`/stream/${taskId}/${serviceName}`)

  console.log(`[Streaming] Starting stream for ${serviceName}...`)

  const eventSource = new EventSource(url)

  // 元数据事件
  eventSource.addEventListener('metadata', (event) => {
    try {
      const metadata = JSON.parse(event.data)
      console.log(`[Streaming] Metadata for ${serviceName}:`, metadata)
      if (onMetadata) onMetadata(metadata)
    } catch (error) {
      console.error(`[Streaming] Failed to parse metadata:`, error)
      if (onError) onError(error)
    }
  })

  // 数据事件
  eventSource.addEventListener('data', (event) => {
    try {
      const chunk = JSON.parse(event.data)
      console.log(`[Streaming] Data chunk ${chunk.chunk_index} for ${serviceName}: ${chunk.data.length} rows (progress: ${chunk.progress}%)`)
      if (onData) onData(chunk)
    } catch (error) {
      console.error(`[Streaming] Failed to parse data:`, error)
      if (onError) onError(error)
    }
  })

  // 完成事件
  eventSource.addEventListener('complete', (event) => {
    try {
      const completion = JSON.parse(event.data)
      console.log(`[Streaming] Stream complete for ${serviceName}:`, completion)
      eventSource.close()
      if (onComplete) onComplete(completion)
    } catch (error) {
      console.error(`[Streaming] Failed to parse completion:`, error)
      eventSource.close()
      if (onError) onError(error)
    }
  })

  // 错误事件
  eventSource.addEventListener('error', (event) => {
    console.error(`[Streaming] Stream error for ${serviceName}:`, event)
    eventSource.close()
    if (onError) {
      try {
        const errorData = JSON.parse(event.data)
        onError(errorData)
      } catch {
        onError({ error: 'Stream connection failed', service: serviceName })
      }
    }
  })

  // 返回取消函数
  return () => {
    console.log(`[Streaming] Cancelling stream for ${serviceName}`)
    eventSource.close()
  }
}

/**
 * 检查任务的缓存状态
 * @param {string} taskId - 任务ID
 * @returns {Promise<Object>} 缓存状态信息
 */
export async function checkCacheStatus(taskId) {
  const url = buildApiUrl(`/cache/status/${taskId}`)

  try {
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    const data = await response.json()
    console.log(`[Cache] Status for task ${taskId}:`, data)
    return data
  } catch (error) {
    console.error(`[Cache] Failed to check status:`, error)
    throw error
  }
}

/**
 * 批量获取多个服务的数据（用于调试）
 * @param {string} taskId - 任务ID
 * @param {Array<string>} serviceNames - 服务名称列表
 * @returns {Promise<Object>} 所有服务的数据
 */
export async function fetchAllServicesData(taskId, serviceNames = []) {
  const results = {}

  for (const serviceName of serviceNames) {
    const allData = []

    await new Promise((resolve, reject) => {
      const cancel = streamServiceData(taskId, serviceName, {
        onData: (chunk) => {
          allData.push(...chunk.data)
        },
        onComplete: () => {
          results[serviceName] = allData
          resolve()
        },
        onError: (error) => {
          console.error(`Failed to fetch ${serviceName}:`, error)
          results[serviceName] = []
          resolve() // 继续处理其他服务
        }
      })
    })
  }

  return results
}

/**
 * 获取支持的所有服务名称
 * @returns {Array<string>} 服务名称列表
 */
export function getAllServiceNames() {
  return [
    'cable',
    'xmit',
    'ber',
    'hca',
    'fan',
    'switch',
    'routing',
    'link_oscillation',
    'histogram',
    'qos',
    'sm_info',
    'port_hierarchy',
    'mlnx_counters',
    'pm_delta',
    'vports',
    'pkey',
    'system_info',
    'extended_port_info',
    'ar_info',
    'sharp',
    'fec_mode',
    'phy_diagnostics',
    'neighbors',
    'buffer_histogram',
    'extended_node_info',
    'extended_switch_info',
    'power_sensors',
    'routing_config',
    'temp_alerts',
    'pci_performance',
    'per_lane_performance',
    'n2n_security'
  ]
}

/**
 * 获取服务的友好名称
 * @param {string} serviceName - 服务名称
 * @returns {string} 友好名称
 */
export function getServiceDisplayName(serviceName) {
  const nameMap = {
    'cable': 'Cable Analysis',
    'xmit': 'Congestion Analysis',
    'ber': 'BER Analysis',
    'hca': 'HCA Analysis',
    'fan': 'Fan Analysis',
    'switch': 'Switch Analysis',
    'routing': 'Routing Analysis',
    'link_oscillation': 'Link Oscillation',
    'histogram': 'Performance Histogram',
    'qos': 'QoS / VL Arbitration',
    'sm_info': 'Subnet Manager',
    'port_hierarchy': 'Port Hierarchy',
    'mlnx_counters': 'MLNX Counters',
    'pm_delta': 'PM Delta',
    'vports': 'Virtual Ports',
    'pkey': 'Partition Keys',
    'system_info': 'System Info',
    'extended_port_info': 'Extended Port Info',
    'ar_info': 'Adaptive Routing',
    'sharp': 'SHARP',
    'fec_mode': 'FEC Mode',
    'phy_diagnostics': 'PHY Diagnostics',
    'neighbors': 'Neighbors',
    'buffer_histogram': 'Buffer Histogram',
    'extended_node_info': 'Extended Node Info',
    'extended_switch_info': 'Extended Switch Info',
    'power_sensors': 'Power Sensors',
    'routing_config': 'Routing Config',
    'temp_alerts': 'Temperature Alerts',
    'pci_performance': 'PCI Performance',
    'per_lane_performance': 'Per-Lane Performance',
    'n2n_security': 'N2N Security'
  }

  return nameMap[serviceName] || serviceName
}
