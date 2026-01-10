import { useState, useMemo } from 'react'
import { AlertTriangle, XCircle, AlertCircle, ChevronDown, ChevronUp, BookOpen, Clock3, Search, Download, ChevronLeft, ChevronRight } from 'lucide-react'
import { getErrorExplanation } from './ErrorExplanations'

/**
 * 故障汇总组件 - 卡片式详细展示,支持分页和搜索
 */
function FaultSummary({ analysisData }) {
  const [expandedCategory, setExpandedCategory] = useState('critical') // 默认展开严重故障
  const [expandedItems, setExpandedItems] = useState({})
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState({ critical: 1, warning: 1, info: 1 })

  const ITEMS_PER_PAGE = 10

  // 定义故障分类
  const faultCategories = {
    critical: {
      title: '严重故障 (Critical)',
      color: '#dc2626',
      bgColor: '#fee2e2',
      icon: <XCircle size={20} />
    },
    warning: {
      title: '警告 (Warning)',
      color: '#f59e0b',
      bgColor: '#fef3c7',
      icon: <AlertTriangle size={20} />
    },
    info: {
      title: '提示信息 (Info)',
      color: '#3b82f6',
      bgColor: '#dbeafe',
      icon: <AlertCircle size={20} />
    }
  }

  // Helper to safely convert to number
  const toNumber = (value) => {
    const num = Number(value)
    return Number.isFinite(num) ? num : 0
  }

  // Helper to check alarm flags
  const hasAlarmFlag = (value) => {
    if (value === null || value === undefined) return false
    const text = String(value).trim()
    if (!text || text.toLowerCase() === 'n/a') return false
    const token = text.split(/\s+/)[0]
    if (!token) return false
    try {
      if (token.toLowerCase().startsWith('0x')) {
        return parseInt(token, 16) !== 0
      }
      const parsed = Number(token)
      return Number.isFinite(parsed) && parsed !== 0
    } catch {
      return false
    }
  }

  // Extract all faults with detailed information
  const extractFaults = () => {
    const faults = {
      critical: [],
      warning: [],
      info: []
    }

    if (!analysisData) return faults

    const addFault = (category, faultType, item) => {
      faults[category].push({
        faultType,
        ...item,
        kb: item.kbType ? getErrorExplanation(item.kbType) : null
      })
    }

    // 1. Cable Temperature Issues
    if (analysisData.cable_data && Array.isArray(analysisData.cable_data)) {
      analysisData.cable_data.forEach(row => {
        const temp = toNumber(row['Temperature (c)'] || row.Temperature)
        if (temp >= 70) {
          addFault(
            temp >= 80 ? 'critical' : 'warning',
            'CABLE_HIGH_TEMPERATURE',
            {
              nodeName: row['Node Name'] || row.NodeName || 'Unknown',
              nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
              portNumber: row.PortNumber || row['Port Number'] || 'N/A',
              currentValue: `${temp.toFixed(1)}°C`,
              threshold: temp >= 80 ? '80°C' : '70°C',
              deviation: temp >= 80 ? `+${(temp - 80).toFixed(1)}°C` : `+${(temp - 70).toFixed(1)}°C`,
              vendor: row.Vendor || row['Vendor Name'] || 'N/A',
              // Backend returns 'PN' and 'SN'
              partNumber: row.PN || row['Part Number'] || row.PartNumber || 'N/A',
              serialNumber: row.SN || row['Serial Number'] || row.SerialNumber || 'N/A',
              kbType: 'CABLE_HIGH_TEMPERATURE',
              details: {
                cableType: row.TypeDesc || row['Cable Type'] || 'N/A',
                length: row.LengthCopperOrActive || row.LengthSMFiber || row.Length || row['Cable Length'] || 'N/A',
                supplyVoltage: row.SupplyVoltageReporting || row['Supply Voltage Reporting'] || 'N/A'
              }
            }
          )
        }
      })
    }

    // 2. Cable Power Alarms
    if (analysisData.cable_data && Array.isArray(analysisData.cable_data)) {
      analysisData.cable_data.forEach(row => {
        const alarms = []
        if (hasAlarmFlag(row['TX Bias Alarm and Warning'])) alarms.push('TX Bias')
        if (hasAlarmFlag(row['TX Power Alarm and Warning'])) alarms.push('TX Power')
        if (hasAlarmFlag(row['RX Power Alarm and Warning'])) alarms.push('RX Power')
        if (hasAlarmFlag(row['Latched Voltage Alarm and Warning'])) alarms.push('Voltage')

        if (alarms.length > 0) {
          addFault('critical', 'CABLE_TX_POWER_ALARM', {
            nodeName: row['Node Name'] || row.NodeName || 'Unknown',
            nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
            portNumber: row.PortNumber || row['Port Number'] || 'N/A',
            currentValue: alarms.join(', ') + ' 告警',
            threshold: '无告警',
            deviation: `${alarms.length}个参数异常`,
            vendor: row.Vendor || row['Vendor Name'] || 'N/A',
            partNumber: row.PN || row['Part Number'] || row.PartNumber || 'N/A',
            kbType: 'CABLE_TX_POWER_ALARM',
            details: {
              txBias: row['TX Bias Alarm and Warning'] || 'N/A',
              txPower: row['TX Power Alarm and Warning'] || 'N/A',
              rxPower: row['RX Power Alarm and Warning'] || 'N/A',
              voltage: row['Latched Voltage Alarm and Warning'] || 'N/A'
            }
          })
        }
      })
    }

    // 3. BER Issues
    if (analysisData.ber_data && Array.isArray(analysisData.ber_data)) {
      analysisData.ber_data.forEach(row => {
        // Support both SymbolBERSeverity (basic) and Severity (advanced)
        const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
        const log10Value = toNumber(row.SymbolBERLog10Value || row.EffectiveBERLog10 || row.RawBERLog10)

        if (severity === 'critical' || severity === 'warning') {
          addFault(
            severity,
            severity === 'critical' ? 'BER_CRITICAL' : 'BER_WARNING',
            {
              nodeName: row['Node Name'] || row.NodeName || 'Unknown',
              nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
              portNumber: row.PortNumber || row['Port Number'] || 'N/A',
              currentValue: `10^${log10Value.toFixed(1)}`,
              threshold: '10^-12',
              deviation: `超标 ${Math.pow(10, log10Value + 12).toFixed(0)}倍`,
              kbType: severity === 'critical' ? 'BER_CRITICAL' : 'BER_WARNING',
              details: {
                eventName: row.EventName || row.Issues || 'N/A',
                effectiveBER: row.EffectiveBER || row['Effective BER'] || 'N/A',
                rawBER: row.RawBER || row['Raw BER'] || 'N/A'
              }
            }
          )
        }
      })
    }

    // 4. Congestion Issues
    if (analysisData.xmit_data && Array.isArray(analysisData.xmit_data)) {
      analysisData.xmit_data.forEach(row => {
        const waitRatio = toNumber(row.WaitRatioPct)
        const waitSeconds = toNumber(row.WaitSeconds)
        const congestionPct = toNumber(row.XmitCongestionPct)
        const fecnCount = toNumber(row.FECNCount)
        const becnCount = toNumber(row.BECNCount)

        if (waitRatio >= 1 || congestionPct >= 1) {
          const severity = (waitRatio >= 5 || congestionPct >= 5) ? 'critical' : 'warning'
          addFault(
            severity,
            severity === 'critical' ? 'XMIT_SEVERE_CONGESTION' : 'XMIT_MODERATE_CONGESTION',
            {
              nodeName: row['Node Name'] || row.NodeName || 'Unknown',
              nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
              portNumber: row.PortNumber || row['Port Number'] || 'N/A',
              currentValue: `等待${waitRatio.toFixed(2)}%`,
              threshold: severity === 'critical' ? '5%' : '1%',
              deviation: `+${(waitRatio - (severity === 'critical' ? 5 : 1)).toFixed(2)}%`,
              kbType: severity === 'critical' ? 'XMIT_SEVERE_CONGESTION' : 'XMIT_MODERATE_CONGESTION',
              details: {
                waitSeconds: `${waitSeconds.toFixed(2)}秒`,
                xmitCongestionPct: congestionPct ? `${congestionPct.toFixed(2)}%` : 'N/A',
                fecnCount: fecnCount || 0,
                becnCount: becnCount || 0,
                linkDowned: toNumber(row.LinkDownedCounter || row.LinkDownedCounterExt) || 0
              }
            }
          )
        }
      })
    }

    // 5. Fan Issues
    if (analysisData.fan_data && Array.isArray(analysisData.fan_data)) {
      analysisData.fan_data.forEach(row => {
        const status = String(row.FanStatus || '').toLowerCase()
        const fanSpeed = toNumber(row.FanSpeed)
        const minSpeed = toNumber(row.MinSpeed)

        if (status === 'alert' || (minSpeed > 0 && fanSpeed < minSpeed)) {
          addFault('critical', 'FAN_SPEED_LOW', {
            nodeName: row['Node Name'] || row.NodeName || row.Description || 'Unknown',
            nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
            portNumber: row.SensorIndex || row.PortNumber || 'N/A',
            currentValue: `${fanSpeed.toFixed(0)} RPM`,
            threshold: `${minSpeed.toFixed(0)} RPM (最低)`,
            deviation: minSpeed > 0 ? `-${(minSpeed - fanSpeed).toFixed(0)} RPM` : 'Alert',
            kbType: 'FAN_SPEED_LOW',
            details: {
              maxSpeed: row.MaxSpeed ? `${toNumber(row.MaxSpeed).toFixed(0)} RPM` : 'N/A',
              fanAlert: row.FanAlert || 'N/A'
            }
          })
        }
      })
    }

    // 6. Temperature Sensor Issues
    if (analysisData.temperature_data && Array.isArray(analysisData.temperature_data)) {
      analysisData.temperature_data.forEach(row => {
        const severity = String(row.Severity || '').toLowerCase()
        const temp = toNumber(row.Temperature || row.TemperatureReading)

        if (severity === 'critical' || severity === 'warning') {
          addFault(severity, 'CABLE_HIGH_TEMPERATURE', {
            nodeName: row['Node Name'] || row.NodeName || 'Unknown',
            nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
            portNumber: row.SensorIndex || row.PortNumber || 'N/A',
            currentValue: `${temp.toFixed(1)}°C`,
            threshold: severity === 'critical' ? '临界温度' : '警告温度',
            deviation: `Severity: ${severity}`,
            kbType: 'CABLE_HIGH_TEMPERATURE',
            details: {
              sensorName: row.SensorName || 'N/A',
              sensorType: row.SensorType || 'N/A'
            }
          })
        }
      })
    }

    // 7. Power Issues
    if (analysisData.power_data && Array.isArray(analysisData.power_data)) {
      analysisData.power_data.forEach(row => {
        const severity = String(row.Severity || '').toLowerCase()

        if (severity === 'critical' || severity === 'warning') {
          addFault(severity, 'FAN_SPEED_LOW', {
            nodeName: row['Node Name'] || row.NodeName || 'Unknown',
            nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
            portNumber: row.PSUIndex || row.SensorIndex || 'N/A',
            currentValue: severity,
            threshold: 'OK',
            deviation: '电源状态异常',
            kbType: 'FAN_SPEED_LOW',
            details: {
              isPresent: row.IsPresent ? 'Yes' : 'No',
              powerConsumption: row.PowerConsumption || 'N/A',
              psuStatus: row.PSUStatus || 'N/A'
            }
          })
        }
      })
    }

    // 8. Firmware Issues
    if (analysisData.hca_data && Array.isArray(analysisData.hca_data)) {
      analysisData.hca_data.forEach(row => {
        const fwCompliant = row.FW_Compliant
        const isOutdated = fwCompliant === false || fwCompliant === 'false' || fwCompliant === 'False'

        if (isOutdated) {
          addFault('warning', 'HCA_FIRMWARE_OUTDATED', {
            nodeName: row['Node Name'] || row.NodeName || row.Description || 'Unknown',
            nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
            portNumber: 'N/A',
            currentValue: row.FW_Version || row.FirmwareVersion || 'Unknown',
            threshold: '最新版本',
            deviation: '版本过旧',
            kbType: 'HCA_FIRMWARE_OUTDATED',
            details: {
              deviceType: row.DeviceType || 'N/A',
              psid: row.PSID || 'N/A',
              partNumber: row.PartNumber || row.PN || 'N/A'
            }
          })
        }
      })
    }

    // 9. Latency Issues
    if (analysisData.histogram_data && Array.isArray(analysisData.histogram_data)) {
      analysisData.histogram_data.forEach(row => {
        const p99OverMedian = toNumber(row.RttP99OverMedian)
        const medianUs = toNumber(row.RttMedianUs)
        const p99Us = toNumber(row.RttP99Us)

        if (p99OverMedian >= 3) {
          addFault(
            p99OverMedian >= 5 ? 'critical' : 'warning',
            'HISTOGRAM_HIGH_LATENCY',
            {
              nodeName: row['Node Name'] || row.NodeName || 'Unknown',
              nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
              portNumber: row.PortNumber || row['Port Number'] || 'N/A',
              currentValue: `P99=${p99Us.toFixed(2)}µs`,
              threshold: `中位数=${medianUs.toFixed(2)}µs`,
              deviation: `P99是中位数的${p99OverMedian.toFixed(1)}倍`,
              kbType: 'HISTOGRAM_HIGH_LATENCY',
              details: {
                minUs: row.RttMinUs || 'N/A',
                maxUs: row.RttMaxUs || 'N/A',
                upperBucketRatio: row.RttUpperBucketRatio ? `${(toNumber(row.RttUpperBucketRatio) * 100).toFixed(1)}%` : 'N/A'
              }
            }
          )
        }
      })
    }

    // 10. PCIe Performance Issues
    if (analysisData.pci_performance_data && Array.isArray(analysisData.pci_performance_data)) {
      analysisData.pci_performance_data.forEach(row => {
        const isDegraded = row.IsDegraded === true || row.IsDegraded === 'true'

        if (isDegraded) {
          addFault('critical', 'PCI_DEGRADATION', {
            nodeName: row['Node Name'] || row.NodeName || 'Unknown',
            nodeGuid: row.NodeGUID || row['Node GUID'] || 'N/A',
            portNumber: 'PCIe',
            currentValue: row.CurrentGen || 'Unknown',
            threshold: row.MaxGen || 'Unknown',
            deviation: 'PCIe速度降级',
            kbType: 'PCI_DEGRADATION',
            details: {
              currentWidth: row.CurrentWidth || 'N/A',
              maxWidth: row.MaxWidth || 'N/A',
              bandwidth: row.BandwidthGBps ? `${toNumber(row.BandwidthGBps).toFixed(1)} GB/s` : 'N/A'
            }
          })
        }
      })
    }

    return faults
  }

  const allFaults = useMemo(() => extractFaults(), [analysisData])

  // Filter faults based on search term
  const filteredFaults = useMemo(() => {
    if (!searchTerm.trim()) return allFaults

    const term = searchTerm.toLowerCase()
    const filtered = {}

    Object.keys(allFaults).forEach(category => {
      filtered[category] = allFaults[category].filter(fault =>
        fault.nodeName?.toLowerCase().includes(term) ||
        fault.nodeGuid?.toLowerCase().includes(term) ||
        String(fault.portNumber).toLowerCase().includes(term) ||
        fault.faultType?.toLowerCase().includes(term)
      )
    })

    return filtered
  }, [allFaults, searchTerm])

  const totalCritical = filteredFaults.critical?.length || 0
  const totalWarning = filteredFaults.warning?.length || 0
  const totalInfo = filteredFaults.info?.length || 0
  const totalFaults = totalCritical + totalWarning + totalInfo

  const toggleCategory = (category) => {
    setExpandedCategory(expandedCategory === category ? null : category)
    setCurrentPage(prev => ({ ...prev, [category]: 1 })) // Reset to page 1 when toggling
  }

  const toggleItem = (category, index) => {
    const key = `${category}-${index}`
    setExpandedItems(prev => ({
      ...prev,
      [key]: !prev[key]
    }))
  }

  const exportToPDF = () => {
    // Simple PDF export using browser print
    window.print()
  }

  if (totalFaults === 0) {
    return (
      <div style={{
        padding: '24px',
        textAlign: 'center',
        background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        borderRadius: '8px',
        color: 'white'
      }}>
        <h2 style={{ margin: '0 0 12px 0', fontSize: '1.5rem' }}>✅ 网络健康状况良好</h2>
        <p style={{ margin: 0, fontSize: '1.1rem' }}>
          {searchTerm ? '搜索无结果,尝试其他关键词' : '未发现严重问题或警告'}
        </p>
      </div>
    )
  }

  return (
    <div>
      {/* Search and Export Bar */}
      <div style={{
        display: 'flex',
        gap: '12px',
        marginBottom: '16px',
        alignItems: 'center',
        flexWrap: 'wrap'
      }}>
        <div style={{ flex: '1', minWidth: '200px', position: 'relative' }}>
          <Search size={18} style={{
            position: 'absolute',
            left: '12px',
            top: '50%',
            transform: 'translateY(-50%)',
            color: '#6b7280'
          }} />
          <input
            type="text"
            placeholder="搜索节点名、GUID、端口号..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 12px 10px 40px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              fontSize: '0.95rem'
            }}
          />
        </div>
        <button
          onClick={exportToPDF}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '10px 16px',
            background: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '0.95rem',
            fontWeight: '500'
          }}
        >
          <Download size={18} />
          导出PDF
        </button>
      </div>

      {/* Summary Header */}
      <div style={{
        padding: '16px',
        marginBottom: '20px',
        background: totalCritical > 0
          ? 'linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)'
          : totalWarning > 0
            ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
            : 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
        borderRadius: '8px',
        color: 'white'
      }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.2rem' }}>
          {totalCritical > 0 ? '🔴' : totalWarning > 0 ? '⚠️' : 'ℹ️'} 故障详细列表
        </h3>
        <div style={{ display: 'flex', gap: '16px', fontSize: '0.95rem' }}>
          {totalCritical > 0 && <span>🔴 严重: {totalCritical}</span>}
          {totalWarning > 0 && <span>⚠️ 警告: {totalWarning}</span>}
          {totalInfo > 0 && <span>ℹ️ 提示: {totalInfo}</span>}
        </div>
      </div>

      {/* Fault Categories */}
      {Object.entries(faultCategories).map(([category, config]) => {
        const faults = filteredFaults[category] || []
        if (faults.length === 0) return null

        const isExpanded = expandedCategory === category
        const page = currentPage[category] || 1
        const totalPages = Math.ceil(faults.length / ITEMS_PER_PAGE)
        const startIdx = (page - 1) * ITEMS_PER_PAGE
        const endIdx = startIdx + ITEMS_PER_PAGE
        const pageFaults = faults.slice(startIdx, endIdx)

        return (
          <div key={category} style={{
            marginBottom: '16px',
            border: `2px solid ${config.color}`,
            borderRadius: '8px',
            overflow: 'hidden'
          }}>
            {/* Category Header */}
            <div
              onClick={() => toggleCategory(category)}
              style={{
                padding: '12px 16px',
                background: config.bgColor,
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                color: config.color,
                fontWeight: 'bold'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {config.icon}
                <span>{config.title} ({faults.length}个问题)</span>
              </div>
              {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>

            {/* Fault Items */}
            {isExpanded && (
              <div style={{ padding: '16px', background: '#f9fafb' }}>
                {pageFaults.map((fault, index) => {
                  const globalIndex = startIdx + index
                  const itemKey = `${category}-${globalIndex}`
                  const isItemExpanded = expandedItems[itemKey]

                  return (
                    <div key={globalIndex} style={{
                      marginBottom: index < pageFaults.length - 1 ? '16px' : 0,
                      padding: '16px',
                      background: 'white',
                      borderRadius: '8px',
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                    }}>
                      {/* Fault Card Header */}
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: '12px',
                        paddingBottom: '12px',
                        borderBottom: '1px solid #e5e7eb'
                      }}>
                        <div style={{ flex: 1 }}>
                          <h4 style={{
                            margin: '0 0 4px 0',
                            fontSize: '1.05rem',
                            color: '#1f2937',
                            fontWeight: '600'
                          }}>
                            {fault.kb?.title || fault.faultType}
                          </h4>
                          <div style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                            问题 #{globalIndex + 1}
                          </div>
                        </div>
                        {fault.kb && (
                          <button
                            onClick={() => toggleItem(category, globalIndex)}
                            style={{
                              padding: '6px 12px',
                              background: '#3b82f6',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              fontSize: '0.85rem',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              whiteSpace: 'nowrap'
                            }}
                          >
                            <BookOpen size={14} />
                            {isItemExpanded ? '收起' : '详情'}
                          </button>
                        )}
                      </div>

                      {/* Fault Details Grid */}
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                        gap: '12px',
                        marginBottom: isItemExpanded ? '16px' : 0
                      }}>
                        <div>
                          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>📍 节点</div>
                          <div style={{ fontSize: '0.9rem', color: '#1f2937', fontWeight: '500' }}>
                            {fault.nodeName}
                          </div>
                          <div style={{ fontSize: '0.8rem', color: '#9ca3af', fontFamily: 'monospace' }}>
                            {fault.nodeGuid}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>📍 端口</div>
                          <div style={{ fontSize: '0.9rem', color: '#1f2937', fontWeight: '500' }}>
                            {fault.portNumber}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>📊 当前值</div>
                          <div style={{ fontSize: '0.9rem', color: config.color, fontWeight: '600' }}>
                            {fault.currentValue}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>⚠️ 阈值</div>
                          <div style={{ fontSize: '0.9rem', color: '#1f2937' }}>
                            {fault.threshold}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>📈 偏差</div>
                          <div style={{ fontSize: '0.9rem', color: '#dc2626', fontWeight: '500' }}>
                            {fault.deviation}
                          </div>
                        </div>

                        {fault.vendor && fault.vendor !== 'N/A' && (
                          <div>
                            <div style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '4px' }}>🏭 厂商</div>
                            <div style={{ fontSize: '0.9rem', color: '#1f2937' }}>
                              {fault.vendor}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Additional Details */}
                      {fault.details && Object.keys(fault.details).length > 0 && (
                        <div style={{
                          marginTop: '12px',
                          padding: '12px',
                          background: '#f3f4f6',
                          borderRadius: '6px'
                        }}>
                          <div style={{ fontSize: '0.8rem', color: '#4b5563', display: 'grid', gap: '4px' }}>
                            {Object.entries(fault.details).map(([key, value]) => (
                              value && value !== 'N/A' && (
                                <div key={key}>
                                  <strong>{key}:</strong> {typeof value === 'object' ? JSON.stringify(value) : value}
                                </div>
                              )
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Knowledge Base Details (Expanded) */}
                      {isItemExpanded && fault.kb && (
                        <div style={{
                          marginTop: '16px',
                          padding: '16px',
                          background: '#eff6ff',
                          borderRadius: '6px',
                          border: '1px solid #bfdbfe'
                        }}>
                          <h5 style={{ margin: '0 0 12px 0', fontSize: '0.95rem', color: '#1e40af' }}>
                            📚 知识库详情
                          </h5>

                          <div style={{ marginBottom: '12px' }}>
                            <strong style={{ fontSize: '0.85rem', color: '#374151' }}>为什么重要:</strong>
                            <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#4b5563' }}>
                              {fault.kb.why_it_matters}
                            </p>
                          </div>

                          {fault.kb.likely_causes && fault.kb.likely_causes.length > 0 && (
                            <div style={{ marginBottom: '12px' }}>
                              <strong style={{ fontSize: '0.85rem', color: '#374151' }}>可能原因:</strong>
                              <ul style={{ margin: '4px 0 0 0', paddingLeft: '20px', fontSize: '0.85rem', color: '#4b5563' }}>
                                {fault.kb.likely_causes.slice(0, 3).map((cause, i) => (
                                  <li key={i}>{cause}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {fault.kb.recommended_actions && fault.kb.recommended_actions.length > 0 && (
                            <div style={{ marginBottom: '12px' }}>
                              <strong style={{ fontSize: '0.85rem', color: '#374151' }}>🔧 建议操作:</strong>
                              <ol style={{ margin: '4px 0 0 0', paddingLeft: '20px', fontSize: '0.85rem', color: '#4b5563' }}>
                                {fault.kb.recommended_actions.slice(0, 4).map((action, i) => (
                                  <li key={i}>{action}</li>
                                ))}
                              </ol>
                            </div>
                          )}

                          <div style={{ display: 'flex', gap: '16px', fontSize: '0.8rem', color: '#6b7280' }}>
                            {fault.kb.mttr_estimate && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <Clock3 size={12} />
                                预计修复: {fault.kb.mttr_estimate}
                              </div>
                            )}
                            {fault.kb.reference && (
                              <div>
                                参考: {fault.kb.reference}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}

                {/* Pagination */}
                {totalPages > 1 && (
                  <div style={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    gap: '12px',
                    marginTop: '20px',
                    padding: '12px',
                    background: 'white',
                    borderRadius: '6px'
                  }}>
                    <button
                      onClick={() => setCurrentPage(prev => ({ ...prev, [category]: Math.max(1, page - 1) }))}
                      disabled={page === 1}
                      style={{
                        padding: '6px 12px',
                        background: page === 1 ? '#e5e7eb' : '#3b82f6',
                        color: page === 1 ? '#9ca3af' : 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: page === 1 ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      <ChevronLeft size={16} />
                      上一页
                    </button>

                    <span style={{ fontSize: '0.9rem', color: '#4b5563' }}>
                      第 {page} / {totalPages} 页 (共 {faults.length} 项)
                    </span>

                    <button
                      onClick={() => setCurrentPage(prev => ({ ...prev, [category]: Math.min(totalPages, page + 1) }))}
                      disabled={page === totalPages}
                      style={{
                        padding: '6px 12px',
                        background: page === totalPages ? '#e5e7eb' : '#3b82f6',
                        color: page === totalPages ? '#9ca3af' : 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: page === totalPages ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px'
                      }}
                    >
                      下一页
                      <ChevronRight size={16} />
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default FaultSummary
