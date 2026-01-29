import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Activity, Home, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import { buildApiUrl } from '../config'
import './ResultsPage.css'

// Import all analysis components from backup
import CableAnalysis from '../CableAnalysis'
import BERAnalysis from '../BERAnalysis'
import CongestionAnalysis from '../CongestionAnalysis'
import LinkOscillation from '../LinkOscillation'
import HcaAnalysis from '../HcaAnalysis'
import FanAnalysis from '../FanAnalysis'
import SwitchesAnalysis from '../SwitchesAnalysis'
import RoutingAnalysis from '../RoutingAnalysis'
import QosAnalysis from '../QosAnalysis'
import SmInfoAnalysis from '../SmInfoAnalysis'
import PortHierarchyAnalysis from '../PortHierarchyAnalysis'
import MlnxCountersAnalysis from '../MlnxCountersAnalysis'
import PmDeltaAnalysis from '../PmDeltaAnalysis'
import VportsAnalysis from '../VportsAnalysis'
import PkeyAnalysis from '../PkeyAnalysis'
import SystemInfoAnalysis from '../SystemInfoAnalysis'
import ExtendedPortInfoAnalysis from '../ExtendedPortInfoAnalysis'
import ArInfoAnalysis from '../ArInfoAnalysis'
import SharpAnalysis from '../SharpAnalysis'
import FecModeAnalysis from '../FecModeAnalysis'
import PhyDiagnosticsAnalysis from '../PhyDiagnosticsAnalysis'
import NeighborsAnalysis from '../NeighborsAnalysis'
import BufferHistogramAnalysis from '../BufferHistogramAnalysis'
import ExtendedNodeInfoAnalysis from '../ExtendedNodeInfoAnalysis'
import ExtendedSwitchInfoAnalysis from '../ExtendedSwitchInfoAnalysis'
import PowerSensorsAnalysis from '../PowerSensorsAnalysis'
import RoutingConfigAnalysis from '../RoutingConfigAnalysis'
import TempAlertsAnalysis from '../TempAlertsAnalysis'
import PciPerformanceAnalysis from '../PciPerformanceAnalysis'
import PerLanePerformanceAnalysis from '../PerLanePerformanceAnalysis'
import N2nSecurityAnalysis from '../N2nSecurityAnalysis'
import LatencyAnalysis from '../LatencyAnalysis'
import ModernOverview from '../components/ModernOverview'
import { HEALTH_CHECK_GROUPS } from '../healthCheckDefinitions'

// UFM Components
import UFMOverview from '../components/ufm/UFMOverview'
import UFMBerAnalysis from '../components/ufm/UFMBerAnalysis'
import UFMLinkAnalysis from '../components/ufm/UFMLinkAnalysis'
import UFMTempAnalysis from '../components/ufm/UFMTempAnalysis'
import UFMCableAnalysis from '../components/ufm/UFMCableAnalysis'
import UFMPortErrors from '../components/ufm/UFMPortErrors'
import UFMPerformance from '../components/ufm/UFMPerformance'
import { UFM_GROUPS } from '../ufmHealthDefinitions'

// Tab configuration (from original App.jsx)
const TAB_GROUPS = HEALTH_CHECK_GROUPS.map(group => ({
  ...group,
  tabs: group.checks.map(checkKey => ({
    key: checkKey,
    label: checkKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
  }))
}))

function ResultsPage() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [navCollapsedGroups, setNavCollapsedGroups] = useState({})

  useEffect(() => {
    fetchAnalysisResult()
  }, [taskId])

  const fetchAnalysisResult = async () => {
    try {
      setLoading(true)
      const response = await axios.get(buildApiUrl(`/analysis/${taskId}`))

      // Transform the stored data to match the expected format
      const data = response.data
      const analysisData = data.analysis_data

      setResult({
        type: data.file_type,
        data: analysisData
      })

    } catch (err) {
      console.error('Failed to fetch analysis result:', err)
      setError(err.response?.data?.detail || '无法加载分析结果')
    } finally {
      setLoading(false)
    }
  }

  const toggleNavGroup = (groupKey) => {
    setNavCollapsedGroups(prev => ({
      ...prev,
      [groupKey]: !prev[groupKey]
    }))
  }

  const renderIbdiagnetContent = () => {
    if (!result || result.type !== 'ibdiagnet') return null

    const data = result.data

    switch (activeTab) {
      case 'overview':
        return (
          <div className="scroll-area">
            <ModernOverview analysisData={data} onSelectTab={setActiveTab} />
          </div>
        )

      case 'cable':
        return (
          <div className="scroll-area">
            <CableAnalysis
              cableData={data.cable_data}
              summary={data.cable_summary}
              totalRows={data.cable_total_rows}
            />
          </div>
        )

      case 'ber':
        return (
          <div className="scroll-area">
            <BERAnalysis berData={data.ber_data} totalRows={data.ber_total_rows} />
          </div>
        )

      case 'xmit':
        return (
          <div className="scroll-area">
            <CongestionAnalysis
              xmitData={data.xmit_data}
              summary={data.xmit_summary}
              totalRows={data.xmit_total_rows}
            />
          </div>
        )

      case 'link_oscillation':
        return (
          <div className="scroll-area">
            <LinkOscillation
              paths={data.link_oscillation_data}
              summary={data.link_oscillation_summary}
              totalRows={data.link_oscillation_total_rows}
            />
          </div>
        )

      case 'hca':
        return (
          <div className="scroll-area">
            <HcaAnalysis
              hcaData={data.hca_data}
              firmwareWarnings={data.firmware_warnings}
              pciWarnings={data.pci_warnings}
              totalRows={data.hca_total_rows}
            />
          </div>
        )

      case 'fan':
        return (
          <div className="scroll-area">
            <FanAnalysis fanData={data.fan_data} totalRows={data.fan_total_rows} />
          </div>
        )

      case 'histogram':
        return (
          <div className="scroll-area">
            <LatencyAnalysis
              histogramData={data.histogram_data}
              summary={data.histogram_summary}
              totalRows={data.histogram_total_rows}
            />
          </div>
        )

      case 'switch':
        return (
          <div className="scroll-area">
            <SwitchesAnalysis
              switchData={data.switch_data}
              summary={data.switch_summary}
              totalRows={data.switch_total_rows}
            />
          </div>
        )

      case 'routing':
        return (
          <div className="scroll-area">
            <RoutingAnalysis routingData={data.routing_data} totalRows={data.routing_total_rows} />
          </div>
        )

      case 'qos':
        return (
          <div className="scroll-area">
            <QosAnalysis qosData={data.qos_data} totalRows={data.qos_total_rows} />
          </div>
        )

      case 'sm_info':
        return (
          <div className="scroll-area">
            <SmInfoAnalysis
              smInfoData={data.sm_info_data}
              summary={data.sm_info_summary}
              totalRows={data.sm_info_total_rows}
            />
          </div>
        )

      case 'port_hierarchy':
        return (
          <div className="scroll-area">
            <PortHierarchyAnalysis portHierarchyData={data.port_hierarchy_data} totalRows={data.port_hierarchy_total_rows} />
          </div>
        )

      case 'mlnx_counters':
        return (
          <div className="scroll-area">
            <MlnxCountersAnalysis
              mlnxCountersData={data.mlnx_counters_data}
              summary={data.mlnx_counters_summary}
              totalRows={data.mlnx_counters_total_rows}
            />
          </div>
        )

      case 'pm_delta':
        return (
          <div className="scroll-area">
            <PmDeltaAnalysis pmDeltaData={data.pm_delta_data} totalRows={data.pm_delta_total_rows} />
          </div>
        )

      case 'vports':
        return (
          <div className="scroll-area">
            <VportsAnalysis vportsData={data.vports_data} totalRows={data.vports_total_rows} />
          </div>
        )

      case 'pkey':
        return (
          <div className="scroll-area">
            <PkeyAnalysis pkeyData={data.pkey_data} totalRows={data.pkey_total_rows} />
          </div>
        )

      case 'system_info':
        return (
          <div className="scroll-area">
            <SystemInfoAnalysis systemInfoData={data.system_info_data} totalRows={data.system_info_total_rows} />
          </div>
        )

      case 'extended_port_info':
        return (
          <div className="scroll-area">
            <ExtendedPortInfoAnalysis extendedPortInfoData={data.extended_port_info_data} totalRows={data.extended_port_info_total_rows} />
          </div>
        )

      case 'ar_info':
        return (
          <div className="scroll-area">
            <ArInfoAnalysis arInfoData={data.ar_info_data} totalRows={data.ar_info_total_rows} />
          </div>
        )

      case 'sharp':
        return (
          <div className="scroll-area">
            <SharpAnalysis sharpData={data.sharp_data} totalRows={data.sharp_total_rows} />
          </div>
        )

      case 'fec_mode':
        return (
          <div className="scroll-area">
            <FecModeAnalysis fecModeData={data.fec_mode_data} totalRows={data.fec_mode_total_rows} />
          </div>
        )

      case 'phy_diagnostics':
        return (
          <div className="scroll-area">
            <PhyDiagnosticsAnalysis phyDiagnosticsData={data.phy_diagnostics_data} totalRows={data.phy_diagnostics_total_rows} />
          </div>
        )

      case 'neighbors':
        return (
          <div className="scroll-area">
            <NeighborsAnalysis neighborsData={data.neighbors_data} totalRows={data.neighbors_total_rows} />
          </div>
        )

      case 'buffer_histogram':
        return (
          <div className="scroll-area">
            <BufferHistogramAnalysis bufferHistogramData={data.buffer_histogram_data} totalRows={data.buffer_histogram_total_rows} />
          </div>
        )

      case 'extended_node_info':
        return (
          <div className="scroll-area">
            <ExtendedNodeInfoAnalysis
              extendedNodeInfoData={data.extended_node_info_data}
              summary={data.extended_node_info_summary}
              totalRows={data.extended_node_info_total_rows}
            />
          </div>
        )

      case 'extended_switch_info':
        return (
          <div className="scroll-area">
            <ExtendedSwitchInfoAnalysis extendedSwitchInfoData={data.extended_switch_info_data} totalRows={data.extended_switch_info_total_rows} />
          </div>
        )

      case 'power_sensors':
        return (
          <div className="scroll-area">
            <PowerSensorsAnalysis powerSensorsData={data.power_sensors_data} totalRows={data.power_sensors_total_rows} />
          </div>
        )

      case 'routing_config':
        return (
          <div className="scroll-area">
            <RoutingConfigAnalysis routingConfigData={data.routing_config_data} totalRows={data.routing_config_total_rows} />
          </div>
        )

      case 'temp_alerts':
        return (
          <div className="scroll-area">
            <TempAlertsAnalysis tempAlertsData={data.temp_alerts_data} totalRows={data.temp_alerts_total_rows} />
          </div>
        )

      case 'pci_performance':
        return (
          <div className="scroll-area">
            <PciPerformanceAnalysis
              pciPerformanceData={data.pci_performance_data}
              summary={data.pci_performance_summary}
              totalRows={data.pci_performance_total_rows}
            />
          </div>
        )

      case 'per_lane_performance':
        return (
          <div className="scroll-area">
            <PerLanePerformanceAnalysis perLanePerformanceData={data.per_lane_performance_data} totalRows={data.per_lane_performance_total_rows} />
          </div>
        )

      case 'n2n_security':
        return (
          <div className="scroll-area">
            <N2nSecurityAnalysis n2nSecurityData={data.n2n_security_data} totalRows={data.n2n_security_total_rows} />
          </div>
        )

      default:
        return <div className="placeholder">选择一个标签查看分析结果</div>
    }
  }

  const renderUfmContent = () => {
    if (!result || result.type !== 'csv') return null

    const data = result.data

    // Safety check for analysis object
    if (!data || !data.analysis) {
      return <div className="placeholder">UFM 数据格式错误</div>
    }

    const { analysis } = data

    switch (activeTab) {
      case 'overview':
        return (
          <div className="scroll-area">
            <UFMOverview data={data} onSelectTab={setActiveTab} />
          </div>
        )

      case 'ber':
        return (
          <div className="scroll-area">
            {analysis.ber_analysis ? (
              <UFMBerAnalysis berData={analysis.ber_analysis} />
            ) : (
              <div className="placeholder">暂无 BER 分析数据</div>
            )}
          </div>
        )

      case 'link':
        return (
          <div className="scroll-area">
            {analysis.link_status ? (
              <UFMLinkAnalysis linkData={analysis.link_status} />
            ) : (
              <div className="placeholder">暂无链路状态数据</div>
            )}
          </div>
        )

      case 'temp':
        return (
          <div className="scroll-area">
            {analysis.temperature ? (
              <UFMTempAnalysis tempData={analysis.temperature} />
            ) : (
              <div className="placeholder">暂无温度数据</div>
            )}
          </div>
        )

      case 'cable':
        return (
          <div className="scroll-area">
            {analysis.cables ? (
              <UFMCableAnalysis cableData={analysis.cables} />
            ) : (
              <div className="placeholder">暂无线缆数据</div>
            )}
          </div>
        )

      case 'errors':
        return (
          <div className="scroll-area">
            {analysis.port_errors ? (
              <UFMPortErrors portErrorData={analysis.port_errors} />
            ) : (
              <div className="placeholder">暂无端口错误数据</div>
            )}
          </div>
        )

      case 'performance':
        return (
          <div className="scroll-area">
            {analysis.performance ? (
              <UFMPerformance performanceData={analysis.performance} />
            ) : (
              <div className="placeholder">暂无性能数据</div>
            )}
          </div>
        )

      default:
        return <div className="placeholder">选择一个标签查看分析结果</div>
    }
  }

  if (loading) {
    return (
      <div className="results-page loading">
        <div className="loading-spinner">
          <Activity size={48} />
          <p>加载分析结果...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="results-page error">
        <div className="error-container">
          <AlertTriangle size={48} color="#ef4444" />
          <h2>加载失败</h2>
          <p>{error}</p>
          <button onClick={() => navigate('/')} className="home-button">
            <Home size={20} />
            返回首页
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="results-page">
      <header className="results-header">
        <div className="results-header-left">
          <button onClick={() => navigate('/')} className="header-button">
            <Home size={20} />
            返回首页
          </button>
          <div className="results-title">
            <h1>
              <Activity size={24} color="#76b900" />
              分析结果
            </h1>
            <div className="results-meta">
              <span className="results-pill">
                {result?.type === 'ibdiagnet' ? 'IBDiagnet' : 'UFM CSV'}
              </span>
              <span className="results-meta-text">Task ID: {taskId}</span>
            </div>
          </div>
        </div>
        <div className="results-header-right">
          <span className="results-status">已完成</span>
        </div>
      </header>

      <div className="results-main">
        <aside className="results-sidebar">
          {result && result.type === 'ibdiagnet' ? (
            <>
              <div className="sidebar-header">
                <h3>分析标签</h3>
              </div>
              <div className="tabs grouped-tabs">
                <div
                  className={`tab overview-tab ${activeTab === 'overview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('overview')}
                >
                  <Activity size={16} /> 总览
                </div>
                {TAB_GROUPS.map(group => {
                  const collapsed = !!navCollapsedGroups[group.key]
                  return (
                    <div key={group.key} className="tab-group">
                      <div className="tab-group-header">
                        <div>
                          <h4>{group.label}</h4>
                          <span>{group.description}</span>
                        </div>
                        <button
                          type="button"
                          className="tab-group-toggle"
                          onClick={() => toggleNavGroup(group.key)}
                        >
                          {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                        </button>
                      </div>
                      {!collapsed && (
                        <div className="tab-group-tabs">
                          {group.tabs.map(({ key, label }) => (
                            <div
                              key={key}
                              className={`tab ${activeTab === key ? 'active' : ''}`}
                              onClick={() => setActiveTab(key)}
                            >
                              {label}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          ) : result && result.type === 'csv' ? (
            <>
              <div className="sidebar-header">
                <h3>UFM 分析</h3>
              </div>
              <div className="tabs grouped-tabs">
                {UFM_GROUPS.map(group => {
                  const collapsed = !!navCollapsedGroups[group.key]
                  return (
                    <div key={group.key} className="tab-group">
                      <div className="tab-group-header">
                        <div>
                          <h4>{group.label}</h4>
                          <span>{group.description}</span>
                        </div>
                        <button
                          type="button"
                          className="tab-group-toggle"
                          onClick={() => toggleNavGroup(group.key)}
                        >
                          {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                        </button>
                      </div>
                      {!collapsed && (
                        <div className="tab-group-tabs">
                          {group.tabs.map(({ key, label }) => (
                            <div
                              key={key}
                              className={`tab ${activeTab === key ? 'active' : ''}`}
                              onClick={() => setActiveTab(key)}
                            >
                              {label}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </>
          ) : (
            <div className="sidebar-placeholder">
              <p>未知结果类型</p>
            </div>
          )}
        </aside>

        <main className="results-content">
          {result && result.type === 'ibdiagnet' && renderIbdiagnetContent()}
          {result && result.type === 'csv' && renderUfmContent()}
        </main>
      </div>
    </div>
  )
}

export default ResultsPage
