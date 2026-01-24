/**
 * 懒加载组件配置
 * 按需加载分析组件，减少初始包大小
 */

import { lazy } from 'react'

// ============ 核心组件（预加载）============
export const ModernOverview = lazy(() => import('../components/ModernOverview'))
export const FaultSummary = lazy(() => import('../FaultSummary'))
export const HealthCheckBoard = lazy(() => import('../HealthCheckBoard'))

// ============ 分析组件（懒加载）============
export const CableAnalysis = lazy(() => import('../CableAnalysis'))
export const BERAnalysis = lazy(() => import('../BERAnalysis'))
export const CongestionAnalysis = lazy(() => import('../CongestionAnalysis'))
export const LinkOscillation = lazy(() => import('../LinkOscillation'))
export const HcaAnalysis = lazy(() => import('../HcaAnalysis'))
export const FanAnalysis = lazy(() => import('../FanAnalysis'))
export const LatencyAnalysis = lazy(() => import('../LatencyAnalysis'))
export const SwitchesAnalysis = lazy(() => import('../SwitchesAnalysis'))
export const RoutingAnalysis = lazy(() => import('../RoutingAnalysis'))
export const QosAnalysis = lazy(() => import('../QosAnalysis'))
export const SmInfoAnalysis = lazy(() => import('../SmInfoAnalysis'))
export const PortHierarchyAnalysis = lazy(() => import('../PortHierarchyAnalysis'))
export const MlnxCountersAnalysis = lazy(() => import('../MlnxCountersAnalysis'))
export const PmDeltaAnalysis = lazy(() => import('../PmDeltaAnalysis'))
export const VportsAnalysis = lazy(() => import('../VportsAnalysis'))
export const PkeyAnalysis = lazy(() => import('../PkeyAnalysis'))
export const SystemInfoAnalysis = lazy(() => import('../SystemInfoAnalysis'))
export const ExtendedPortInfoAnalysis = lazy(() => import('../ExtendedPortInfoAnalysis'))
export const ArInfoAnalysis = lazy(() => import('../ArInfoAnalysis'))
export const SharpAnalysis = lazy(() => import('../SharpAnalysis'))
export const FecModeAnalysis = lazy(() => import('../FecModeAnalysis'))
export const PhyDiagnosticsAnalysis = lazy(() => import('../PhyDiagnosticsAnalysis'))
export const NeighborsAnalysis = lazy(() => import('../NeighborsAnalysis'))
export const BufferHistogramAnalysis = lazy(() => import('../BufferHistogramAnalysis'))
export const ExtendedNodeInfoAnalysis = lazy(() => import('../ExtendedNodeInfoAnalysis'))
export const ExtendedSwitchInfoAnalysis = lazy(() => import('../ExtendedSwitchInfoAnalysis'))
export const PowerSensorsAnalysis = lazy(() => import('../PowerSensorsAnalysis'))
export const RoutingConfigAnalysis = lazy(() => import('../RoutingConfigAnalysis'))
export const TempAlertsAnalysis = lazy(() => import('../TempAlertsAnalysis'))
export const PciPerformanceAnalysis = lazy(() => import('../PciPerformanceAnalysis'))
export const PerLanePerformanceAnalysis = lazy(() => import('../PerLanePerformanceAnalysis'))
export const N2nSecurityAnalysis = lazy(() => import('../N2nSecurityAnalysis'))
export const DataTable = lazy(() => import('../DataTable'))

/**
 * 组件映射表
 * key: tab key
 * value: 懒加载组件
 */
export const COMPONENT_MAP = {
  cable: CableAnalysis,
  ber: BERAnalysis,
  xmit: CongestionAnalysis,
  link_oscillation: LinkOscillation,
  hca: HcaAnalysis,
  fan: FanAnalysis,
  latency: LatencyAnalysis,
  switches: SwitchesAnalysis,
  routing: RoutingAnalysis,
  qos: QosAnalysis,
  sm_info: SmInfoAnalysis,
  port_hierarchy: PortHierarchyAnalysis,
  mlnx_counters: MlnxCountersAnalysis,
  pm_delta: PmDeltaAnalysis,
  vports: VportsAnalysis,
  pkey: PkeyAnalysis,
  system_info: SystemInfoAnalysis,
  extended_port_info: ExtendedPortInfoAnalysis,
  ar_info: ArInfoAnalysis,
  sharp: SharpAnalysis,
  fec_mode: FecModeAnalysis,
  phy_diagnostics: PhyDiagnosticsAnalysis,
  neighbors: NeighborsAnalysis,
  buffer_histogram: BufferHistogramAnalysis,
  extended_node_info: ExtendedNodeInfoAnalysis,
  extended_switch_info: ExtendedSwitchInfoAnalysis,
  power_sensors: PowerSensorsAnalysis,
  routing_config: RoutingConfigAnalysis,
  temp_alerts: TempAlertsAnalysis,
  pci_performance: PciPerformanceAnalysis,
  per_lane_performance: PerLanePerformanceAnalysis,
  n2n_security: N2nSecurityAnalysis,
}

/**
 * 获取懒加载组件
 */
export const getComponentForTab = (tabKey) => {
  return COMPONENT_MAP[tabKey] || null
}
