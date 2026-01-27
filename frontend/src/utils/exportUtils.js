/**
 * 数据导出工具函数
 * 支持导出 CSV、JSON、Excel 格式
 */

/**
 * 将数据导出为 CSV 文件
 * @param {Array} data - 要导出的数据数组
 * @param {string} filename - 文件名（不含扩展名）
 * @param {Array} columns - 可选的列名数组，如果不提供则使用数据的所有键
 */
export function exportToCSV(data, filename = 'export', columns = null) {
  if (!data || data.length === 0) {
    alert('没有数据可导出')
    return
  }

  // 确定要导出的列
  const cols = columns || Object.keys(data[0])

  // 创建 CSV 内容
  const csvContent = [
    // 表头
    cols.join(','),
    // 数据行
    ...data.map(row =>
      cols.map(col => {
        let value = row[col]
        // 处理特殊字符
        if (value === null || value === undefined) {
          return ''
        }
        if (typeof value === 'object') {
          value = JSON.stringify(value)
        }
        // 如果包含逗号、引号或换行符，需要用引号包围
        value = String(value)
        if (value.includes(',') || value.includes('"') || value.includes('\n')) {
          value = `"${value.replace(/"/g, '""')}"`
        }
        return value
      }).join(',')
    )
  ].join('\n')

  // 添加 BOM 以支持中文
  const BOM = '\uFEFF'
  const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8;' })

  downloadFile(blob, `${filename}.csv`)
}

/**
 * 将数据导出为 JSON 文件
 * @param {Array|Object} data - 要导出的数据
 * @param {string} filename - 文件名（不含扩展名）
 * @param {boolean} pretty - 是否格式化输出
 */
export function exportToJSON(data, filename = 'export', pretty = true) {
  if (!data) {
    alert('没有数据可导出')
    return
  }

  const jsonContent = pretty ? JSON.stringify(data, null, 2) : JSON.stringify(data)
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' })

  downloadFile(blob, `${filename}.json`)
}

/**
 * 将数据导出为 Excel 格式（实际上是 CSV，但使用 .xlsx 扩展名）
 * 注意：这是简化版本，真正的 Excel 需要使用 xlsx 库
 * @param {Array} data - 要导出的数据数组
 * @param {string} filename - 文件名（不含扩展名）
 */
export function exportToExcel(data, filename = 'export') {
  // 暂时使用 CSV 格式，但文件名为 .xlsx
  // 如果需要真正的 Excel 格式，可以集成 xlsx 库
  exportToCSV(data, filename, null)
}

/**
 * 导出完整的分析报告（包含多个工作表）
 * @param {Object} analysisData - 完整的分析数据对象
 * @param {string} filename - 文件名
 */
export function exportFullReport(analysisData, filename = 'network_health_report') {
  if (!analysisData) {
    alert('没有数据可导出')
    return
  }

  // 创建包含所有数据的报告对象
  const report = {
    metadata: {
      exportTime: new Date().toISOString(),
      healthScore: analysisData.health?.score,
      healthStatus: analysisData.health?.status,
      totalNodes: analysisData.health?.total_nodes,
      totalPorts: analysisData.health?.total_ports,
    },
    summary: analysisData.health?.summary || {},
    issues: analysisData.issues || [],
    datasets: {}
  }

  // 添加各个分析模块的数据（只包含非空数据）
  const dataKeys = [
    'cable_data', 'xmit_data', 'ber_data', 'hca_data', 'fan_data',
    'switch_data', 'routing_data', 'link_oscillation_data', 'histogram_data',
    'qos_data', 'sm_info_data', 'port_hierarchy_data', 'mlnx_counters_data',
    'pm_delta_data', 'vports_data', 'pkey_data', 'system_info_data',
    'extended_port_info_data', 'ar_info_data', 'sharp_data', 'fec_mode_data',
    'phy_diagnostics_data', 'neighbors_data', 'buffer_histogram_data',
    'extended_node_info_data', 'extended_switch_info_data', 'power_sensors_data',
    'routing_config_data', 'temp_alerts_data', 'pci_performance_data',
    'per_lane_performance_data', 'n2n_security_data'
  ]

  dataKeys.forEach(key => {
    if (analysisData[key] && analysisData[key].length > 0) {
      const datasetName = key.replace('_data', '').replace(/_/g, ' ')
      report.datasets[datasetName] = {
        count: analysisData[key].length,
        sample: analysisData[key].slice(0, 5) // 只包含前5条作为示例
      }
    }
  })

  exportToJSON(report, filename, true)
}

/**
 * 下载文件的通用函数
 * @param {Blob} blob - 文件内容
 * @param {string} filename - 文件名
 */
function downloadFile(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'

  document.body.appendChild(link)
  link.click()

  // 清理
  setTimeout(() => {
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }, 100)
}

/**
 * 导出当前表格数据
 * @param {Array} data - 表格数据
 * @param {string} tableName - 表格名称
 * @param {string} format - 导出格式 ('csv' | 'json')
 */
export function exportTableData(data, tableName = 'table', format = 'csv') {
  const timestamp = new Date().toISOString().split('T')[0]
  const filename = `${tableName}_${timestamp}`

  switch (format.toLowerCase()) {
    case 'csv':
      exportToCSV(data, filename)
      break
    case 'json':
      exportToJSON(data, filename)
      break
    case 'excel':
      exportToExcel(data, filename)
      break
    default:
      console.error('不支持的导出格式:', format)
  }
}

export default {
  exportToCSV,
  exportToJSON,
  exportToExcel,
  exportFullReport,
  exportTableData
}
