/**
 * Tab配置常量
 * 集中管理所有Tab的配置
 */

import {
  Activity, Server, AlertTriangle, ShieldCheck, Cpu, Clock3,
  FanIcon as Fan, Zap, Network, GitBranch, Layers, Settings,
  Database, BarChart2, Key, Box, Info, PlugZap, Shuffle,
  BrainCircuit, Shield, Radio, Users, BarChart3, HardDrive,
  Router, ThermometerSun
} from 'lucide-react'
import { HEALTH_CHECK_GROUPS, HEALTH_CHECK_DEFINITIONS } from '../healthCheckDefinitions'

export const TAB_ICON_MAP = {
  overview: Activity,
  cable: Server,
  link_oscillation: AlertTriangle,
  xmit: AlertTriangle,
  latency: Clock3,
  per_lane_performance: Layers,
  ber: ShieldCheck,
  hca: Cpu,
  system_info: Info,
  sm_info: Settings,
  fan: Fan,
  power_sensors: Zap,
  temp_alerts: ThermometerSun,
  switches: Network,
  routing: GitBranch,
  routing_config: Router,
  port_hierarchy: Database,
  qos: Layers,
  n2n_security: Shield,
  pkey: Key,
  vports: Box,
  mlnx_counters: Cpu,
  pm_delta: BarChart2,
  pci_performance: HardDrive,
  ar_info: Shuffle,
  sharp: BrainCircuit,
  fec_mode: Shield,
  phy_diagnostics: Radio,
  extended_port_info: PlugZap,
  extended_node_info: HardDrive,
  extended_switch_info: Network,
  buffer_histogram: BarChart3,
  neighbors: Users,
}

export const TAB_GROUPS = HEALTH_CHECK_GROUPS.map(group => ({
  ...group,
  tabs: group.checks.map(checkKey => {
    const definition = HEALTH_CHECK_DEFINITIONS[checkKey] || { label: checkKey }
    return {
      key: checkKey,
      label: definition.label || checkKey,
      icon: TAB_ICON_MAP[checkKey] || Activity,
    }
  }),
}))

export const TAB_LIST = [
  { key: 'overview', label: '总览', icon: Activity },
  ...TAB_GROUPS.flatMap(group => group.tabs),
]

export const TAB_LOOKUP = TAB_LIST.reduce((acc, tab) => {
  acc[tab.key] = tab
  return acc
}, {})

export const resolveTabMeta = (key) => TAB_LOOKUP[key] || { label: key, icon: Activity }
