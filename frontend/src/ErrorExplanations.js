/**
 * 综合错误解释和解决方案知识库
 * Comprehensive Error Explanations and Solutions Knowledge Base
 *
 * 为 NVIDIA InfiniBand 网络健康检查平台提供详细的问题解释和操作指南
 * Provides detailed explanations and operational guidance for NVIDIA InfiniBand Network Health Check Platform
 *
 * 支持的问题类型 (Supported Issue Types):
 * - Cable/Optics: 线缆和光模块问题
 * - BER: 误码率问题
 * - Xmit/Congestion: 传输拥塞问题
 * - HCA/Firmware: 固件和设备问题
 * - Histogram/Latency: 延迟问题
 * - Topology: 拓扑问题
 * - Fan/Chassis: 风扇和机箱问题
 */

// ==================== 严重程度定义 ====================
export const SEVERITY_LEVELS = {
  critical: {
    label: 'Critical',
    labelCn: '严重',
    color: '#ef4444',
    bgColor: '#fef2f2',
    borderColor: '#fecaca',
    icon: 'XCircle',
    priority: 1,
    description: 'Immediate action required - service impacting issue',
    descriptionCn: '需要立即处理 - 影响服务的问题'
  },
  warning: {
    label: 'Warning',
    labelCn: '警告',
    color: '#f59e0b',
    bgColor: '#fffbeb',
    borderColor: '#fed7aa',
    icon: 'AlertTriangle',
    priority: 2,
    description: 'Action recommended within maintenance window',
    descriptionCn: '建议在维护窗口期处理'
  },
  info: {
    label: 'Info',
    labelCn: '提示',
    color: '#3b82f6',
    bgColor: '#eff6ff',
    borderColor: '#bfdbfe',
    icon: 'Info',
    priority: 3,
    description: 'For awareness - no immediate action needed',
    descriptionCn: '仅供参考 - 无需立即处理'
  },
  none: {
    label: 'None',
    labelCn: '无',
    color: '#6b7280',
    bgColor: '#f9fafb',
    borderColor: '#e5e7eb',
    icon: 'CheckCircle',
    priority: 4,
    description: 'No issue detected',
    descriptionCn: '未检测到问题'
  }
}

// ==================== 问题类别定义 ====================
export const ISSUE_CATEGORIES = {
  cable: {
    label: 'Cable/Optics',
    labelCn: '线缆/光模块',
    icon: 'Cable',
    description: 'Cable and optical transceiver issues'
  },
  ber: {
    label: 'Bit Error Rate',
    labelCn: '误码率',
    icon: 'Activity',
    description: 'Signal quality and bit error rate issues'
  },
  xmit: {
    label: 'Congestion',
    labelCn: '拥塞',
    icon: 'AlertTriangle',
    description: 'Transmission wait and congestion issues'
  },
  hca: {
    label: 'Firmware/HCA',
    labelCn: '固件/网卡',
    icon: 'Cpu',
    description: 'Host Channel Adapter and firmware issues'
  },
  histogram: {
    label: 'Latency',
    labelCn: '延迟',
    icon: 'Clock',
    description: 'Round-trip time and latency distribution issues'
  },
  topology: {
    label: 'Topology',
    labelCn: '拓扑',
    icon: 'Network',
    description: 'Network topology and connectivity issues'
  },
  fan: {
    label: 'Chassis/Fan',
    labelCn: '机箱/风扇',
    icon: 'Fan',
    description: 'Chassis health and cooling issues'
  }
}

export const ERROR_KNOWLEDGE_BASE = {
  // ==================== Cable/Optics 相关问题 ====================
  CABLE_HIGH_TEMPERATURE: {
    title: '光模块温度过高',
    titleEn: 'Optical Module High Temperature',
    category: 'cable',
    severity: 'critical',
    threshold: '≥ 70°C',
    thresholdValue: 70,
    why_it_matters: '光模块温度过高会导致信号质量下降、误码率增加、设备寿命缩短，严重时可能导致链路中断或设备永久损坏。',
    why_it_matters_en: 'High optical module temperature degrades signal quality, increases bit error rate, shortens device lifespan, and may cause link interruption or permanent damage.',
    likely_causes: [
      '机房空调故障或通风不良',
      '光模块散热不良或风扇故障',
      '使用了劣质或假冒光模块',
      '端口灰尘堵塞影响散热',
      '环境温度过高（超过40°C）',
      '光模块老化或接近寿命终点'
    ],
    likely_causes_en: [
      'HVAC failure or poor ventilation in data center',
      'Poor heat dissipation or fan failure',
      'Counterfeit or low-quality optical modules',
      'Dust blocking port affecting cooling',
      'Ambient temperature too high (>40°C)',
      'Optical module aging or nearing end of life'
    ],
    recommended_actions: [
      '立即检查机房空调系统是否正常工作',
      '检查交换机风扇是否运转正常',
      '清洁端口和光模块，去除灰尘',
      '验证光模块是否为NVIDIA原厂正品',
      '考虑更换高温光模块',
      '如果多个模块同时高温，检查整体散热系统',
      '监控温度趋势，如持续升高需立即更换'
    ],
    recommended_actions_en: [
      'Check HVAC system operation immediately',
      'Verify switch fans are operating normally',
      'Clean ports and optical modules to remove dust',
      'Verify optical modules are genuine NVIDIA products',
      'Consider replacing high-temperature modules',
      'If multiple modules are hot, check overall cooling system',
      'Monitor temperature trends; replace immediately if rising'
    ],
    reference: 'NVIDIA InfiniBand Optics Troubleshooting Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/ufmenterpriseufmreleasenotes/optical+transceiver+troubleshooting',
    urgency: 'high',
    impact: {
      performance: 'high',
      reliability: 'critical',
      dataIntegrity: 'medium'
    },
    mttr_estimate: '15-60 minutes',
    tools_needed: ['Optical power meter', 'Compressed air', 'Replacement modules']
  },

  CABLE_TX_POWER_ALARM: {
    title: 'TX 发送光功率异常',
    titleEn: 'TX Optical Power Alarm',
    category: 'cable',
    severity: 'critical',
    threshold: '超出厂商规格范围',
    thresholdValue: null,
    why_it_matters: 'TX光功率异常表明光模块发送端故障，会导致对端接收信号弱或无信号，造成链路不稳定、丢包或完全中断。',
    why_it_matters_en: 'TX power alarm indicates transmitter failure, causing weak/no signal at receiver, leading to link instability, packet loss, or complete interruption.',
    likely_causes: [
      '光模块发送端激光器故障',
      '光纤连接松动或接触不良',
      '光纤弯曲半径过小导致光损耗',
      '光纤接头污染或损坏',
      '光模块供电异常',
      '光模块与端口不兼容'
    ],
    likely_causes_en: [
      'Transmitter laser failure in optical module',
      'Loose fiber connection or poor contact',
      'Fiber bend radius too small causing loss',
      'Contaminated or damaged fiber connector',
      'Optical module power supply issue',
      'Optical module incompatible with port'
    ],
    recommended_actions: [
      '检查光纤连接是否牢固，重新插拔光模块',
      '使用光功率计测量实际光功率值',
      '清洁光纤接头（使用专用清洁工具）',
      '检查光纤路由，确保弯曲半径 > 3cm',
      '更换光模块到备用端口测试',
      '如果问题持续，更换光模块',
      '检查光模块是否在兼容列表中'
    ],
    recommended_actions_en: [
      'Check fiber connection; reseat optical module',
      'Measure actual optical power with power meter',
      'Clean fiber connectors using proper cleaning tools',
      'Check fiber routing; ensure bend radius > 3cm',
      'Test optical module in spare port',
      'Replace optical module if issue persists',
      'Verify optical module is on compatibility list'
    ],
    reference: 'NVIDIA Mellanox Optics Validation Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/ConnectX7VPI/Optical+Module+Installation',
    urgency: 'high',
    impact: {
      performance: 'critical',
      reliability: 'critical',
      dataIntegrity: 'high'
    },
    mttr_estimate: '15-45 minutes',
    tools_needed: ['Optical power meter', 'Fiber cleaning kit', 'Replacement modules']
  },

  CABLE_RX_POWER_ALARM: {
    title: 'RX 接收光功率异常',
    titleEn: 'RX Optical Power Alarm',
    category: 'cable',
    severity: 'critical',
    threshold: '超出厂商规格范围',
    thresholdValue: null,
    why_it_matters: 'RX光功率异常表明接收信号过弱或过强，会导致误码率升高、链路不稳定或完全无法通信。',
    why_it_matters_en: 'RX power alarm indicates received signal too weak or too strong, causing high BER, link instability, or complete communication failure.',
    likely_causes: [
      '对端TX光功率异常',
      '光纤衰减过大（距离过长或质量差）',
      '光纤接头污染严重',
      '光纤断裂或严重弯曲',
      '使用了错误类型的光纤（单模/多模混用）',
      '光模块接收端故障'
    ],
    likely_causes_en: [
      'Remote TX optical power abnormal',
      'Excessive fiber attenuation (too long or poor quality)',
      'Severely contaminated fiber connector',
      'Fiber break or severe bend',
      'Wrong fiber type (single-mode/multi-mode mismatch)',
      'Optical module receiver failure'
    ],
    recommended_actions: [
      '检查对端设备的TX光功率是否正常',
      '测量光纤链路损耗（应 < 2dB）',
      '清洁两端光纤接头',
      '检查光纤是否有物理损伤',
      '验证光纤类型是否匹配（单模 vs 多模）',
      '更换光纤或光模块',
      '使用OTDR测试光纤链路质量'
    ],
    recommended_actions_en: [
      'Check remote device TX optical power',
      'Measure fiber link loss (should be < 2dB)',
      'Clean fiber connectors on both ends',
      'Inspect fiber for physical damage',
      'Verify fiber type matches (single-mode vs multi-mode)',
      'Replace fiber or optical module',
      'Use OTDR to test fiber link quality'
    ],
    reference: 'InfiniBand Link Troubleshooting',
    reference_url: 'https://docs.nvidia.com/networking/display/IBDiagnetUserManualv2130/Link+Troubleshooting',
    urgency: 'high',
    impact: {
      performance: 'critical',
      reliability: 'critical',
      dataIntegrity: 'high'
    },
    mttr_estimate: '20-60 minutes',
    tools_needed: ['Optical power meter', 'OTDR', 'Fiber cleaning kit', 'Replacement fiber/modules']
  },

  CABLE_TX_BIAS_ALARM: {
    title: 'TX Bias 偏置电流异常',
    titleEn: 'TX Bias Current Alarm',
    category: 'cable',
    severity: 'warning',
    threshold: '超出正常范围',
    thresholdValue: null,
    why_it_matters: 'TX Bias电流异常表明激光器驱动电路问题，是光模块老化或即将故障的早期信号。',
    why_it_matters_en: 'TX bias current alarm indicates laser driver circuit issues, an early sign of optical module aging or imminent failure.',
    likely_causes: [
      '光模块激光器老化',
      '温度过高导致性能下降',
      '光模块质量问题',
      '供电电压不稳定',
      '模块内部电路问题'
    ],
    likely_causes_en: [
      'Optical module laser aging',
      'High temperature causing performance degradation',
      'Optical module quality issues',
      'Unstable power supply voltage',
      'Internal circuit issues in module'
    ],
    recommended_actions: [
      '记录当前偏置电流值和温度',
      '检查光模块温度是否正常',
      '计划更换该光模块',
      '监控趋势，如持续恶化需立即更换',
      '检查供电电压是否稳定'
    ],
    recommended_actions_en: [
      'Record current bias current value and temperature',
      'Check if optical module temperature is normal',
      'Plan to replace the optical module',
      'Monitor trends; replace immediately if worsening',
      'Check if power supply voltage is stable'
    ],
    reference: 'Optical Module Diagnostics Guide',
    urgency: 'medium',
    impact: {
      performance: 'medium',
      reliability: 'high',
      dataIntegrity: 'low'
    },
    mttr_estimate: '15-30 minutes',
    tools_needed: ['Replacement modules']
  },

  CABLE_VOLTAGE_ALARM: {
    title: '光模块供电电压异常',
    titleEn: 'Optical Module Supply Voltage Alarm',
    category: 'cable',
    severity: 'warning',
    threshold: '超出正常范围',
    thresholdValue: null,
    why_it_matters: '供电电压异常可能导致光模块工作不稳定，影响发送和接收性能。',
    why_it_matters_en: 'Supply voltage anomaly may cause optical module instability, affecting transmit and receive performance.',
    likely_causes: [
      '交换机电源问题',
      '端口供电不足',
      '光模块功耗异常',
      '接触不良',
      '光模块内部问题'
    ],
    likely_causes_en: [
      'Switch power supply issues',
      'Port power delivery insufficient',
      'Abnormal optical module power consumption',
      'Poor contact',
      'Internal optical module issues'
    ],
    recommended_actions: [
      '检查交换机电源状态',
      '重新插拔光模块确保良好接触',
      '尝试更换到其他端口',
      '如果多个端口有问题，检查电源模块',
      '更换光模块测试'
    ],
    recommended_actions_en: [
      'Check switch power supply status',
      'Reseat optical module to ensure good contact',
      'Try moving to different port',
      'If multiple ports affected, check power supply module',
      'Test with replacement optical module'
    ],
    reference: 'Switch Power Supply Guide',
    urgency: 'medium',
    impact: {
      performance: 'medium',
      reliability: 'medium',
      dataIntegrity: 'low'
    },
    mttr_estimate: '10-30 minutes',
    tools_needed: ['Multimeter', 'Replacement modules']
  },

  CABLE_COMPLIANCE_ISSUE: {
    title: '线缆规格不符合要求',
    titleEn: 'Cable Compliance Issue',
    category: 'cable',
    severity: 'warning',
    threshold: '长度或类型不匹配',
    thresholdValue: null,
    why_it_matters: '使用不符合规格的线缆会导致信号衰减、误码率增加、链路速率下降或无法达到标称速率。',
    why_it_matters_en: 'Non-compliant cables cause signal attenuation, increased BER, reduced link speed, or inability to reach rated speed.',
    likely_causes: [
      'HDR速率下使用超过5米的铜缆',
      'FDR速率下使用超过3米的铜缆',
      '光纤长度超过支持的最大距离',
      '使用了低速率线缆连接高速端口',
      '线缆类型与速率不匹配'
    ],
    likely_causes_en: [
      'Using copper cable >5m at HDR speed',
      'Using copper cable >3m at FDR speed',
      'Fiber length exceeds maximum supported distance',
      'Using low-speed cable with high-speed port',
      'Cable type does not match speed requirements'
    ],
    recommended_actions: [
      '查看线缆标签，确认规格和速率等级',
      'HDR (200Gb/s): 铜缆 ≤ 5m，光纤 ≤ 1000m',
      'FDR (56Gb/s): 铜缆 ≤ 3m，光纤 ≤ 2000m',
      'NDR (400Gb/s): 铜缆 ≤ 2m',
      '更换为符合规格的线缆',
      '或降低端口速率以匹配现有线缆',
      '使用 NVIDIA 认证的线缆型号'
    ],
    recommended_actions_en: [
      'Check cable label for specification and speed rating',
      'HDR (200Gb/s): Copper ≤ 5m, Fiber ≤ 1000m',
      'FDR (56Gb/s): Copper ≤ 3m, Fiber ≤ 2000m',
      'NDR (400Gb/s): Copper ≤ 2m',
      'Replace with compliant cable',
      'Or reduce port speed to match existing cable',
      'Use NVIDIA certified cable models'
    ],
    reference: 'InfiniBand Cable Specifications',
    reference_url: 'https://docs.nvidia.com/networking/display/linkxdg/cables+and+transceivers',
    urgency: 'medium',
    impact: {
      performance: 'high',
      reliability: 'medium',
      dataIntegrity: 'low'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['Replacement cables', 'Cable tester']
  },

  CABLE_SPEED_MISMATCH: {
    title: '线缆速率与端口速率不匹配',
    titleEn: 'Cable Speed Mismatch',
    category: 'cable',
    severity: 'warning',
    threshold: '线缆速率 < 端口速率',
    thresholdValue: null,
    why_it_matters: '使用低速率线缆连接高速端口会导致链路无法达到最佳性能，可能出现不稳定或降速运行。',
    why_it_matters_en: 'Using low-speed cable with high-speed port prevents optimal performance, may cause instability or speed downgrade.',
    likely_causes: [
      '使用了旧的低速率线缆',
      '线缆标签错误或混用',
      '端口配置了过高的速率',
      '线缆质量不达标'
    ],
    likely_causes_en: [
      'Using old low-speed cable',
      'Cable mislabeled or mixed up',
      'Port configured for higher speed than cable supports',
      'Cable quality does not meet standards'
    ],
    recommended_actions: [
      '检查线缆标签上的速率等级',
      '升级线缆以匹配端口速率',
      '或在交换机上降低端口速率配置',
      '使用 ibdiagnet 验证链路实际速率',
      '更换为 NVIDIA 认证的高速线缆'
    ],
    recommended_actions_en: [
      'Check speed rating on cable label',
      'Upgrade cable to match port speed',
      'Or reduce port speed configuration on switch',
      'Use ibdiagnet to verify actual link speed',
      'Replace with NVIDIA certified high-speed cable'
    ],
    reference: 'Link Speed Configuration Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/Link+Speed+Configuration',
    urgency: 'medium',
    impact: {
      performance: 'high',
      reliability: 'low',
      dataIntegrity: 'low'
    },
    mttr_estimate: '15-60 minutes',
    tools_needed: ['Replacement cables']
  },

  // ==================== BER 相关问题 ====================
  BER_CRITICAL: {
    title: '误码率严重超标',
    titleEn: 'Critical Bit Error Rate',
    category: 'ber',
    severity: 'critical',
    threshold: 'Symbol BER > 1e-12',
    thresholdValue: 1e-12,
    why_it_matters: '误码率超过1e-12阈值表明信号质量极差，会导致大量数据重传、性能严重下降、应用超时甚至数据损坏。',
    why_it_matters_en: 'BER exceeding 1e-12 indicates extremely poor signal quality, causing massive retransmissions, severe performance degradation, application timeouts, and potential data corruption.',
    likely_causes: [
      '光纤接头污染（最常见原因）',
      '光模块故障或老化',
      '光纤物理损坏或弯曲过度',
      '光功率不匹配（过强或过弱）',
      'EMI电磁干扰',
      '温度过高导致信号劣化',
      '使用了劣质光模块或线缆'
    ],
    likely_causes_en: [
      'Contaminated fiber connector (most common)',
      'Optical module failure or aging',
      'Physical damage or excessive bending of fiber',
      'Optical power mismatch (too high or too low)',
      'EMI electromagnetic interference',
      'High temperature causing signal degradation',
      'Low-quality optical modules or cables'
    ],
    recommended_actions: [
      '【第一步】清洁光纤接头（使用专用清洁笔/棉签+酒精）',
      '【第二步】检查光模块温度是否过高',
      '【第三步】使用光功率计测量TX/RX功率',
      '【第四步】检查光纤是否有明显弯曲或损伤',
      '【第五步】更换光模块到备用端口测试',
      '【第六步】如果问题持续，更换光纤',
      '【第七步】如果仍未解决，更换光模块',
      '持续监控BER值，确认问题已解决'
    ],
    recommended_actions_en: [
      '[Step 1] Clean fiber connectors (use cleaning pen/swab with alcohol)',
      '[Step 2] Check if optical module temperature is too high',
      '[Step 3] Measure TX/RX power with optical power meter',
      '[Step 4] Check fiber for obvious bends or damage',
      '[Step 5] Test optical module in spare port',
      '[Step 6] If issue persists, replace fiber',
      '[Step 7] If still unresolved, replace optical module',
      'Continue monitoring BER to confirm issue is resolved'
    ],
    reference: 'NVIDIA InfiniBand BER Troubleshooting',
    reference_url: 'https://docs.nvidia.com/networking/display/IBDiagnetUserManualv2130/BER+Analysis',
    urgency: 'critical',
    impact: {
      performance: 'critical',
      reliability: 'critical',
      dataIntegrity: 'high'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['Fiber cleaning kit', 'Optical power meter', 'Replacement modules', 'Replacement fiber']
  },

  BER_WARNING: {
    title: '误码率偏高（接近阈值）',
    titleEn: 'Elevated Bit Error Rate',
    category: 'ber',
    severity: 'warning',
    threshold: '1e-15 < Symbol BER < 1e-12',
    thresholdValue: 1e-15,
    why_it_matters: '误码率虽未超标但已接近阈值，表明信号质量下降，如不处理可能恶化为严重问题。',
    why_it_matters_en: 'BER approaching threshold indicates declining signal quality; if not addressed, may escalate to critical issue.',
    likely_causes: [
      '光纤接头轻微污染',
      '光模块开始老化',
      '环境温度偏高',
      '光纤轻微弯曲',
      '光功率边缘值'
    ],
    likely_causes_en: [
      'Slightly contaminated fiber connector',
      'Optical module beginning to age',
      'Elevated ambient temperature',
      'Slight fiber bending',
      'Optical power at edge of acceptable range'
    ],
    recommended_actions: [
      '定期清洁光纤接头（建议每季度一次）',
      '监控BER趋势，设置告警',
      '检查并记录光功率值',
      '优化光纤布线，避免过度弯曲',
      '计划在维护窗口进行深入检查',
      '考虑预防性更换老化光模块'
    ],
    recommended_actions_en: [
      'Clean fiber connectors regularly (recommend quarterly)',
      'Monitor BER trends; set up alerts',
      'Check and record optical power values',
      'Optimize fiber routing; avoid excessive bending',
      'Plan detailed inspection during maintenance window',
      'Consider preventive replacement of aging modules'
    ],
    reference: 'Preventive Maintenance Best Practices',
    reference_url: 'https://docs.nvidia.com/networking/display/ufmenterpriseufmreleasenotes/ber+monitoring',
    urgency: 'medium',
    impact: {
      performance: 'medium',
      reliability: 'medium',
      dataIntegrity: 'low'
    },
    mttr_estimate: '15-60 minutes',
    tools_needed: ['Fiber cleaning kit', 'Optical power meter']
  },

  BER_FEC_EXCESSIVE: {
    title: 'FEC 前向纠错过度使用',
    titleEn: 'Excessive FEC Correction',
    category: 'ber',
    severity: 'warning',
    threshold: 'RS-FEC 纠错频繁',
    thresholdValue: null,
    why_it_matters: 'FEC能纠正错误，但过度使用表明底层信号质量不佳，会增加延迟并消耗额外带宽。',
    why_it_matters_en: 'FEC can correct errors, but excessive use indicates underlying signal quality issues, adding latency and consuming bandwidth.',
    likely_causes: [
      '信号质量下降但未达到BER阈值',
      '光纤衰减偏大',
      '光模块性能下降',
      '链路配置不优',
      '线缆质量边缘'
    ],
    likely_causes_en: [
      'Signal quality degraded but not at BER threshold',
      'High fiber attenuation',
      'Optical module performance degradation',
      'Suboptimal link configuration',
      'Marginal cable quality'
    ],
    recommended_actions: [
      '检查信号质量和光功率',
      '清洁光纤接头',
      '优化FEC配置（如果支持）',
      '考虑更换质量更好的线缆',
      '监控FEC纠错统计趋势',
      '在HDR/NDR环境下确保使用RS-FEC'
    ],
    recommended_actions_en: [
      'Check signal quality and optical power',
      'Clean fiber connectors',
      'Optimize FEC configuration (if supported)',
      'Consider replacing with higher quality cable',
      'Monitor FEC correction statistics trends',
      'Ensure RS-FEC is enabled for HDR/NDR environments'
    ],
    reference: 'FEC Configuration Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/Forward+Error+Correction',
    urgency: 'low',
    impact: {
      performance: 'low',
      reliability: 'medium',
      dataIntegrity: 'low'
    },
    mttr_estimate: '15-30 minutes',
    tools_needed: ['Fiber cleaning kit']
  },

  BER_NO_THRESHOLD: {
    title: '设备不支持BER阈值监控',
    titleEn: 'BER Threshold Monitoring Not Supported',
    category: 'ber',
    severity: 'info',
    threshold: 'N/A',
    thresholdValue: null,
    why_it_matters: '这是正常现象，不是错误。某些设备型号、固件版本或端口类型不支持BER阈值监控功能。',
    why_it_matters_en: 'This is normal, not an error. Some device models, firmware versions, or port types do not support BER threshold monitoring.',
    likely_causes: [
      '设备硬件不支持BER监控（如旧型号）',
      '固件版本不支持此功能',
      '端口类型不支持（如某些铜缆端口）',
      '功能未启用或需要license',
      '连接的是管理端口而非数据端口'
    ],
    likely_causes_en: [
      'Device hardware does not support BER monitoring (e.g., older models)',
      'Firmware version does not support this feature',
      'Port type not supported (e.g., some copper ports)',
      'Feature not enabled or requires license',
      'Connected to management port instead of data port'
    ],
    recommended_actions: [
      '这不是问题，无需处理',
      '如需BER监控，可考虑：',
      '  - 升级固件到最新版本',
      '  - 使用支持BER监控的设备型号',
      '  - 启用相关功能或获取license',
      '可使用其他指标监控链路健康（如光功率、温度）'
    ],
    recommended_actions_en: [
      'This is not an issue; no action required',
      'If BER monitoring is needed, consider:',
      '  - Upgrade firmware to latest version',
      '  - Use device model that supports BER monitoring',
      '  - Enable feature or obtain license',
      'Use other metrics to monitor link health (optical power, temperature)'
    ],
    reference: 'Device Capabilities Matrix',
    reference_url: 'https://docs.nvidia.com/networking/display/IBDiagnetUserManualv2130',
    urgency: 'none',
    impact: {
      performance: 'none',
      reliability: 'none',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'N/A',
    tools_needed: []
  },

  BER_RS_FEC_HIGH_ERRORS: {
    title: 'RS-FEC 纠错率偏高',
    titleEn: 'High RS-FEC Error Correction Rate',
    category: 'ber',
    severity: 'warning',
    threshold: 'RS-FEC symbol errors > 1000/hour',
    thresholdValue: 1000,
    why_it_matters: 'RS-FEC正在积极纠正大量错误，虽然数据完整性得到保护，但表明物理层存在问题。',
    why_it_matters_en: 'RS-FEC is actively correcting many errors; while data integrity is protected, this indicates physical layer issues.',
    likely_causes: [
      '光信号边缘质量',
      '光模块性能下降',
      '光纤老化',
      '环境干扰',
      '温度波动'
    ],
    likely_causes_en: [
      'Marginal optical signal quality',
      'Optical module performance degradation',
      'Aging fiber',
      'Environmental interference',
      'Temperature fluctuations'
    ],
    recommended_actions: [
      '检查光功率是否在正常范围内',
      '监控温度变化',
      '清洁光纤接头',
      '考虑预防性更换光模块',
      '查看错误是否与特定时间段相关'
    ],
    recommended_actions_en: [
      'Check if optical power is within normal range',
      'Monitor temperature changes',
      'Clean fiber connectors',
      'Consider preventive optical module replacement',
      'Check if errors correlate with specific time periods'
    ],
    reference: 'RS-FEC Monitoring Guide',
    urgency: 'medium',
    impact: {
      performance: 'low',
      reliability: 'medium',
      dataIntegrity: 'low'
    },
    mttr_estimate: '15-45 minutes',
    tools_needed: ['Fiber cleaning kit', 'Optical power meter']
  },

  // ==================== Xmit/Congestion 相关问题 ====================
  XMIT_SEVERE_CONGESTION: {
    title: '严重拥塞',
    titleEn: 'Severe Congestion',
    category: 'xmit',
    severity: 'critical',
    threshold: 'WaitRatioPct ≥ 5%',
    thresholdValue: 5,
    why_it_matters: '端口等待时间超过5%表明严重拥塞，会导致吞吐量大幅下降、延迟增加、应用性能严重受影响。',
    why_it_matters_en: 'Port wait time exceeding 5% indicates severe congestion, causing significant throughput reduction, increased latency, and severe application performance impact.',
    likely_causes: [
      '下游交换机或节点处理能力不足',
      '路由配置不当导致流量集中',
      '应用流量模式不均衡',
      '存在慢速节点拖累整体性能',
      '交换机buffer配置不当',
      '存在信用环路（credit loop）',
      '链路带宽不匹配'
    ],
    likely_causes_en: [
      'Downstream switch or node insufficient capacity',
      'Improper routing causing traffic concentration',
      'Unbalanced application traffic patterns',
      'Slow nodes dragging overall performance',
      'Improper switch buffer configuration',
      'Credit loop exists',
      'Link bandwidth mismatch'
    ],
    recommended_actions: [
      '【诊断】检查拥塞端口的对端设备',
      '【诊断】使用拓扑图查看流量路径',
      '【诊断】检查是否存在credit loop',
      '【优化】调整路由算法（如使用adaptive routing）',
      '【优化】优化应用通信模式',
      '【优化】调整交换机QoS和buffer配置',
      '【硬件】升级慢速节点或交换机',
      '【硬件】增加链路带宽或使用链路聚合'
    ],
    recommended_actions_en: [
      '[Diagnose] Check device connected to congested port',
      '[Diagnose] Use topology map to view traffic path',
      '[Diagnose] Check for credit loop',
      '[Optimize] Adjust routing algorithm (use adaptive routing)',
      '[Optimize] Optimize application communication patterns',
      '[Optimize] Adjust switch QoS and buffer configuration',
      '[Hardware] Upgrade slow nodes or switches',
      '[Hardware] Increase link bandwidth or use link aggregation'
    ],
    reference: 'InfiniBand Congestion Management',
    reference_url: 'https://docs.nvidia.com/networking/display/UFMEnterpriseUFMReleaseNotes/Congestion+Control',
    urgency: 'critical',
    impact: {
      performance: 'critical',
      reliability: 'high',
      dataIntegrity: 'low'
    },
    mttr_estimate: '1-4 hours',
    tools_needed: ['Network analyzer', 'UFM', 'ibdiagnet', 'Traffic monitoring tools']
  },

  XMIT_MODERATE_CONGESTION: {
    title: '中度拥塞',
    titleEn: 'Moderate Congestion',
    category: 'xmit',
    severity: 'warning',
    threshold: '1% ≤ WaitRatioPct < 5%',
    thresholdValue: 1,
    why_it_matters: '端口等待时间在1-5%之间表明存在拥塞，虽未严重影响性能，但需要关注和优化。',
    why_it_matters_en: 'Port wait time between 1-5% indicates congestion; while not severely impacting performance, requires attention and optimization.',
    likely_causes: [
      '流量突发导致临时拥塞',
      '路由不够均衡',
      '某些时段流量过大',
      '交换机buffer不足',
      '应用流量模式周期性变化'
    ],
    likely_causes_en: [
      'Traffic bursts causing temporary congestion',
      'Routing not well balanced',
      'Traffic peaks during certain periods',
      'Insufficient switch buffer',
      'Periodic application traffic pattern changes'
    ],
    recommended_actions: [
      '监控拥塞趋势，确认是否持续',
      '分析流量模式，识别高峰时段',
      '考虑启用adaptive routing',
      '优化应用通信模式',
      '调整交换机buffer配置',
      '如果持续恶化，参考严重拥塞的处理方案'
    ],
    recommended_actions_en: [
      'Monitor congestion trends; confirm if persistent',
      'Analyze traffic patterns; identify peak periods',
      'Consider enabling adaptive routing',
      'Optimize application communication patterns',
      'Adjust switch buffer configuration',
      'If worsening, refer to severe congestion remediation'
    ],
    reference: 'Performance Tuning Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/Performance+Tuning',
    urgency: 'medium',
    impact: {
      performance: 'medium',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['Network analyzer', 'UFM', 'Traffic monitoring tools']
  },

  XMIT_FECN_BECN: {
    title: 'FECN/BECN 拥塞通知',
    titleEn: 'FECN/BECN Congestion Notification',
    category: 'xmit',
    severity: 'warning',
    threshold: 'FECN/BECN > 0',
    thresholdValue: 1,
    why_it_matters: 'FECN（前向拥塞通知）和BECN（后向拥塞通知）表明网络中存在拥塞点，需要定位和解决。',
    why_it_matters_en: 'FECN (Forward ECN) and BECN (Backward ECN) indicate congestion points in the network that need to be located and resolved.',
    likely_causes: [
      '下游路径存在拥塞',
      '上游发送速率过快',
      '交换机队列溢出',
      '端到端流控未生效',
      '路由不均衡'
    ],
    likely_causes_en: [
      'Congestion on downstream path',
      'Upstream sending too fast',
      'Switch queue overflow',
      'End-to-end flow control not effective',
      'Unbalanced routing'
    ],
    recommended_actions: [
      '使用拓扑图追踪拥塞路径',
      '检查拥塞点的交换机配置',
      '启用或优化拥塞控制机制',
      '调整应用发送速率',
      '考虑使用QoS优先级',
      '检查是否启用了ECN和CC（拥塞控制）'
    ],
    recommended_actions_en: [
      'Use topology map to trace congestion path',
      'Check switch configuration at congestion point',
      'Enable or optimize congestion control mechanisms',
      'Adjust application sending rate',
      'Consider using QoS priorities',
      'Check if ECN and CC (Congestion Control) are enabled'
    ],
    reference: 'Congestion Control Mechanisms',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/Congestion+Control',
    urgency: 'medium',
    impact: {
      performance: 'medium',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['Network analyzer', 'UFM', 'ibdiagnet']
  },

  XMIT_LINK_DOWNSHIFT: {
    title: '链路降速运行',
    titleEn: 'Link Speed Downshift',
    category: 'xmit',
    severity: 'warning',
    threshold: '实际速率 < 支持速率',
    thresholdValue: null,
    why_it_matters: '链路未运行在最高支持速率，导致带宽浪费和性能下降。',
    why_it_matters_en: 'Link not running at maximum supported speed, causing bandwidth waste and performance degradation.',
    likely_causes: [
      '链路训练失败，自动降速',
      '线缆质量不支持高速率',
      '端口配置限制了速率',
      '对端设备不支持高速率',
      '信号质量差导致自动降速',
      '固件版本不支持最高速率'
    ],
    likely_causes_en: [
      'Link training failed; automatic speed reduction',
      'Cable quality does not support high speed',
      'Port configuration limits speed',
      'Remote device does not support high speed',
      'Poor signal quality causing automatic downshift',
      'Firmware version does not support maximum speed'
    ],
    recommended_actions: [
      '检查链路两端的支持速率配置',
      '验证线缆是否支持目标速率',
      '检查BER和光功率是否正常',
      '尝试重新训练链路（disable/enable端口）',
      '升级线缆或光模块',
      '检查固件版本是否支持高速率'
    ],
    recommended_actions_en: [
      'Check supported speed configuration on both ends',
      'Verify cable supports target speed',
      'Check if BER and optical power are normal',
      'Try retraining link (disable/enable port)',
      'Upgrade cable or optical module',
      'Check if firmware version supports high speed'
    ],
    reference: 'Link Speed Configuration',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/Link+Speed+Configuration',
    urgency: 'medium',
    impact: {
      performance: 'high',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: '15-60 minutes',
    tools_needed: ['ibdiagnet', 'Replacement cables', 'Optical power meter']
  },

  XMIT_LINK_WIDTH_DOWNSHIFT: {
    title: '链路宽度降级',
    titleEn: 'Link Width Downshift',
    category: 'xmit',
    severity: 'warning',
    threshold: '实际宽度 < 支持宽度',
    thresholdValue: null,
    why_it_matters: '链路未使用全部可用通道，导致带宽减少。例如4X降为1X会损失75%带宽。',
    why_it_matters_en: 'Link not using all available lanes, reducing bandwidth. E.g., 4X to 1X loses 75% bandwidth.',
    likely_causes: [
      '线缆部分通道损坏',
      '端口针脚接触不良',
      '光模块部分激光器故障',
      '端口硬件问题',
      '线缆不支持全宽度'
    ],
    likely_causes_en: [
      'Some cable lanes damaged',
      'Port pin contact issues',
      'Partial laser failure in optical module',
      'Port hardware issues',
      'Cable does not support full width'
    ],
    recommended_actions: [
      '重新插拔线缆确保良好接触',
      '检查线缆是否有物理损伤',
      '更换线缆测试',
      '尝试其他端口排除硬件问题',
      '更换光模块',
      '检查端口针脚是否有污染或损坏'
    ],
    recommended_actions_en: [
      'Reseat cable to ensure good contact',
      'Check cable for physical damage',
      'Test with replacement cable',
      'Try other ports to rule out hardware issues',
      'Replace optical module',
      'Check port pins for contamination or damage'
    ],
    reference: 'Link Width Troubleshooting',
    urgency: 'medium',
    impact: {
      performance: 'high',
      reliability: 'medium',
      dataIntegrity: 'none'
    },
    mttr_estimate: '15-60 minutes',
    tools_needed: ['Replacement cables', 'Replacement modules']
  },

  XMIT_CREDIT_WATCHDOG: {
    title: 'Credit Watchdog 超时',
    titleEn: 'Credit Watchdog Timeout',
    category: 'xmit',
    severity: 'critical',
    threshold: 'Timeout > 0',
    thresholdValue: 1,
    why_it_matters: 'Credit watchdog超时表明流控机制异常，可能存在死锁或严重的协议问题，会导致链路挂起。',
    why_it_matters_en: 'Credit watchdog timeout indicates flow control mechanism failure, possible deadlock or serious protocol issues, causing link hang.',
    likely_causes: [
      '存在credit loop（信用环路）',
      '对端设备响应异常',
      '交换机固件bug',
      '链路不稳定导致credit丢失',
      '配置错误',
      '硬件故障'
    ],
    likely_causes_en: [
      'Credit loop exists',
      'Remote device response abnormal',
      'Switch firmware bug',
      'Link instability causing credit loss',
      'Configuration error',
      'Hardware failure'
    ],
    recommended_actions: [
      '【紧急】检查是否存在credit loop',
      '【紧急】检查对端设备状态',
      '重启受影响的端口或设备',
      '升级交换机固件到最新版本',
      '检查网络拓扑是否合理',
      '联系NVIDIA技术支持'
    ],
    recommended_actions_en: [
      '[Urgent] Check for credit loop',
      '[Urgent] Check remote device status',
      'Restart affected port or device',
      'Upgrade switch firmware to latest version',
      'Check if network topology is reasonable',
      'Contact NVIDIA technical support'
    ],
    reference: 'Credit Loop Detection and Resolution',
    reference_url: 'https://docs.nvidia.com/networking/display/IBDiagnetUserManualv2130/Credit+Loop+Detection',
    urgency: 'critical',
    impact: {
      performance: 'critical',
      reliability: 'critical',
      dataIntegrity: 'medium'
    },
    mttr_estimate: '30-180 minutes',
    tools_needed: ['ibdiagnet', 'UFM', 'Console access']
  },

  XMIT_HIGH_DISCARD: {
    title: '端口丢包严重',
    titleEn: 'High Port Discard Rate',
    category: 'xmit',
    severity: 'critical',
    threshold: 'PortXmitDiscards > 0',
    thresholdValue: 1,
    why_it_matters: '端口丢弃数据包表明存在拥塞或配置问题，会导致数据重传和性能下降。',
    why_it_matters_en: 'Port discarding packets indicates congestion or configuration issues, causing retransmissions and performance degradation.',
    likely_causes: [
      '严重的网络拥塞',
      '交换机buffer溢出',
      'QoS配置问题',
      '流量超过端口容量',
      'MTU配置不匹配'
    ],
    likely_causes_en: [
      'Severe network congestion',
      'Switch buffer overflow',
      'QoS configuration issues',
      'Traffic exceeds port capacity',
      'MTU configuration mismatch'
    ],
    recommended_actions: [
      '检查网络拥塞情况',
      '分析丢包发生的时间和模式',
      '检查QoS配置',
      '调整交换机buffer配置',
      '验证MTU设置一致性'
    ],
    recommended_actions_en: [
      'Check network congestion status',
      'Analyze timing and patterns of packet drops',
      'Check QoS configuration',
      'Adjust switch buffer configuration',
      'Verify MTU setting consistency'
    ],
    reference: 'Port Counter Analysis',
    urgency: 'critical',
    impact: {
      performance: 'critical',
      reliability: 'high',
      dataIntegrity: 'medium'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['ibdiagnet', 'Network analyzer', 'UFM']
  },

  XMIT_HIGH_RCV_ERRORS: {
    title: '接收错误过多',
    titleEn: 'High Receive Errors',
    category: 'xmit',
    severity: 'critical',
    threshold: 'PortRcvErrors > 0',
    thresholdValue: 1,
    why_it_matters: '接收错误表明物理层或链路层问题，会导致数据包需要重传。',
    why_it_matters_en: 'Receive errors indicate physical or link layer issues, requiring packet retransmissions.',
    likely_causes: [
      '光信号质量差',
      '线缆问题',
      'EMI干扰',
      '光模块故障',
      '端口硬件问题'
    ],
    likely_causes_en: [
      'Poor optical signal quality',
      'Cable issues',
      'EMI interference',
      'Optical module failure',
      'Port hardware issues'
    ],
    recommended_actions: [
      '检查BER和光功率',
      '清洁光纤接头',
      '更换线缆测试',
      '更换光模块',
      '检查周围是否有EMI源'
    ],
    recommended_actions_en: [
      'Check BER and optical power',
      'Clean fiber connectors',
      'Test with replacement cable',
      'Replace optical module',
      'Check for nearby EMI sources'
    ],
    reference: 'Error Counter Analysis',
    urgency: 'critical',
    impact: {
      performance: 'high',
      reliability: 'high',
      dataIntegrity: 'medium'
    },
    mttr_estimate: '30-90 minutes',
    tools_needed: ['Fiber cleaning kit', 'Optical power meter', 'Replacement modules']
  },

  XMIT_LINK_DOWN_COUNTER: {
    title: '链路频繁断开',
    titleEn: 'Frequent Link Down Events',
    category: 'xmit',
    severity: 'warning',
    threshold: 'LinkDownedCounter > 0',
    thresholdValue: 1,
    why_it_matters: '链路断开计数器非零表明链路不稳定，可能间歇性影响通信。',
    why_it_matters_en: 'Link down counter non-zero indicates link instability, potentially causing intermittent communication issues.',
    likely_causes: [
      '线缆接触不良',
      '光模块问题',
      '电源波动',
      '过热导致保护性断开',
      '固件问题'
    ],
    likely_causes_en: [
      'Poor cable contact',
      'Optical module issues',
      'Power fluctuations',
      'Thermal protection disconnect',
      'Firmware issues'
    ],
    recommended_actions: [
      '检查线缆连接是否牢固',
      '检查光模块温度',
      '查看事件日志确定断开时间',
      '更换线缆或光模块',
      '检查电源稳定性'
    ],
    recommended_actions_en: [
      'Check if cable connection is secure',
      'Check optical module temperature',
      'Review event logs to determine disconnect times',
      'Replace cable or optical module',
      'Check power supply stability'
    ],
    reference: 'Link Stability Analysis',
    urgency: 'medium',
    impact: {
      performance: 'medium',
      reliability: 'high',
      dataIntegrity: 'low'
    },
    mttr_estimate: '20-60 minutes',
    tools_needed: ['Event logs', 'Replacement cables/modules']
  },

  // ==================== HCA/Firmware 相关问题 ====================
  HCA_FIRMWARE_OUTDATED: {
    title: '固件版本过旧',
    titleEn: 'Firmware Version Outdated',
    category: 'hca',
    severity: 'warning',
    threshold: '低于推荐版本',
    thresholdValue: null,
    why_it_matters: '旧版本固件可能存在已知bug、性能问题或安全漏洞，且无法使用新功能。',
    why_it_matters_en: 'Older firmware may have known bugs, performance issues, or security vulnerabilities, and cannot use new features.',
    likely_causes: [
      '长期未更新固件',
      '不知道有新版本发布',
      '担心升级风险',
      '缺少维护窗口',
      '升级流程复杂'
    ],
    likely_causes_en: [
      'Firmware not updated for extended period',
      'Unaware of new version release',
      'Concerns about upgrade risks',
      'Lack of maintenance window',
      'Complex upgrade procedure'
    ],
    recommended_actions: [
      '访问 NVIDIA 官网查看最新固件版本',
      '阅读固件发布说明（Release Notes）',
      '在测试环境先验证新固件',
      '计划维护窗口进行升级',
      '备份当前配置',
      '按照官方升级指南操作',
      '升级后验证功能正常'
    ],
    recommended_actions_en: [
      'Visit NVIDIA website for latest firmware version',
      'Read firmware release notes',
      'Validate new firmware in test environment first',
      'Schedule maintenance window for upgrade',
      'Backup current configuration',
      'Follow official upgrade guide',
      'Verify functionality after upgrade'
    ],
    reference: 'NVIDIA Firmware Update Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/Firmware+Update',
    urgency: 'low',
    impact: {
      performance: 'low',
      reliability: 'medium',
      dataIntegrity: 'low'
    },
    mttr_estimate: '30-120 minutes per device',
    tools_needed: ['Firmware package', 'mlxfwmanager', 'Console access']
  },

  HCA_PSID_UNSUPPORTED: {
    title: 'PSID 不在支持列表',
    titleEn: 'PSID Not in Supported List',
    category: 'hca',
    severity: 'warning',
    threshold: 'PSID 不匹配',
    thresholdValue: null,
    why_it_matters: 'PSID（Parameter Set ID）不匹配表明设备可能不是标准配置，可能影响兼容性和支持。',
    why_it_matters_en: 'PSID mismatch indicates device may not be standard configuration, potentially affecting compatibility and support.',
    likely_causes: [
      '使用了非标准配置的设备',
      '设备来自不同的供应商或渠道',
      'OEM定制版本',
      '配置被修改过',
      '测试或开发设备'
    ],
    likely_causes_en: [
      'Non-standard device configuration',
      'Device from different vendor or channel',
      'OEM customized version',
      'Configuration has been modified',
      'Test or development device'
    ],
    recommended_actions: [
      '确认设备采购渠道是否正规',
      '检查设备是否在NVIDIA兼容列表中',
      '如果是OEM版本，联系OEM厂商',
      '考虑重新刷写标准固件',
      '如果功能正常，可能只是配置差异',
      '联系NVIDIA技术支持确认'
    ],
    recommended_actions_en: [
      'Verify device procurement channel is legitimate',
      'Check if device is on NVIDIA compatibility list',
      'If OEM version, contact OEM vendor',
      'Consider reflashing standard firmware',
      'If functioning normally, may just be configuration difference',
      'Contact NVIDIA technical support for confirmation'
    ],
    reference: 'Device Configuration Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/PSID',
    urgency: 'low',
    impact: {
      performance: 'none',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'N/A (investigation required)',
    tools_needed: ['mlxfwmanager', 'Device documentation']
  },

  HCA_FIRMWARE_MIXED_VERSIONS: {
    title: '固件版本不一致',
    titleEn: 'Mixed Firmware Versions',
    category: 'hca',
    severity: 'warning',
    threshold: '多个不同版本存在',
    thresholdValue: null,
    why_it_matters: '同一网络中存在不同固件版本可能导致功能不一致、兼容性问题或难以诊断的间歇性故障。',
    why_it_matters_en: 'Different firmware versions in the same network may cause inconsistent functionality, compatibility issues, or hard-to-diagnose intermittent failures.',
    likely_causes: [
      '分批升级未完成',
      '新设备使用不同版本',
      '升级过程中出现问题',
      '缺乏版本管理策略',
      '不同时期采购的设备'
    ],
    likely_causes_en: [
      'Batch upgrade not completed',
      'New devices have different versions',
      'Issues during upgrade process',
      'Lack of version management strategy',
      'Devices procured at different times'
    ],
    recommended_actions: [
      '统计所有设备的固件版本',
      '制定统一升级计划',
      '确定目标固件版本',
      '分批完成升级',
      '建立固件版本管理策略',
      '定期审计固件版本一致性'
    ],
    recommended_actions_en: [
      'Inventory firmware versions of all devices',
      'Create unified upgrade plan',
      'Determine target firmware version',
      'Complete upgrades in batches',
      'Establish firmware version management policy',
      'Regularly audit firmware version consistency'
    ],
    reference: 'Firmware Management Best Practices',
    urgency: 'low',
    impact: {
      performance: 'low',
      reliability: 'medium',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'Varies based on scale',
    tools_needed: ['Inventory tools', 'Firmware packages', 'mlxfwmanager']
  },

  HCA_HIGH_UPTIME: {
    title: '设备运行时间过长',
    titleEn: 'Device Uptime Very Long',
    category: 'hca',
    severity: 'info',
    threshold: '> 365天',
    thresholdValue: 365,
    why_it_matters: '虽然长时间运行不一定是问题，但可能表明设备长期未重启，错过了固件更新或配置刷新的机会。',
    why_it_matters_en: 'While long uptime is not necessarily an issue, it may indicate device has not been restarted for updates or configuration refreshes.',
    likely_causes: [
      '设备运行稳定无需重启',
      '缺少维护窗口',
      '担心重启影响业务',
      '固件更新计划滞后'
    ],
    likely_causes_en: [
      'Device running stable without need to restart',
      'Lack of maintenance windows',
      'Concerns about restart impacting business',
      'Firmware update schedule delayed'
    ],
    recommended_actions: [
      '检查是否有待应用的固件更新',
      '计划定期维护窗口',
      '评估设备健康状态',
      '考虑预防性重启（如果业务允许）'
    ],
    recommended_actions_en: [
      'Check if there are pending firmware updates',
      'Plan regular maintenance windows',
      'Assess device health status',
      'Consider preventive restart (if business allows)'
    ],
    reference: 'Maintenance Planning Guide',
    urgency: 'none',
    impact: {
      performance: 'none',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'N/A',
    tools_needed: []
  },

  HCA_DEVICE_NOT_FOUND: {
    title: '设备未检测到',
    titleEn: 'Device Not Detected',
    category: 'hca',
    severity: 'critical',
    threshold: '预期设备缺失',
    thresholdValue: null,
    why_it_matters: '预期存在的设备未被检测到，可能表明设备故障、链路断开或严重的硬件问题。',
    why_it_matters_en: 'Expected device not detected may indicate device failure, link disconnection, or serious hardware issues.',
    likely_causes: [
      '设备电源故障',
      '设备硬件故障',
      '链路完全断开',
      '设备被错误关闭',
      'SM（子网管理器）问题'
    ],
    likely_causes_en: [
      'Device power failure',
      'Device hardware failure',
      'Link completely disconnected',
      'Device incorrectly powered off',
      'SM (Subnet Manager) issues'
    ],
    recommended_actions: [
      '检查设备电源指示灯',
      '验证物理连接',
      '检查链路状态',
      '查看SM日志',
      '尝试重启设备',
      '联系硬件支持'
    ],
    recommended_actions_en: [
      'Check device power indicators',
      'Verify physical connections',
      'Check link status',
      'Review SM logs',
      'Try restarting device',
      'Contact hardware support'
    ],
    reference: 'Hardware Troubleshooting Guide',
    urgency: 'critical',
    impact: {
      performance: 'critical',
      reliability: 'critical',
      dataIntegrity: 'high'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['Console access', 'Physical access']
  },

  // ==================== Histogram/Latency 相关问题 ====================
  HISTOGRAM_HIGH_LATENCY: {
    title: '延迟异常偏高',
    titleEn: 'Abnormally High Latency',
    category: 'histogram',
    severity: 'warning',
    threshold: 'P99 > 3x Median',
    thresholdValue: 3,
    why_it_matters: 'P99延迟远高于中位数表明存在延迟尖刺，会影响应用性能和用户体验。',
    why_it_matters_en: 'P99 latency much higher than median indicates latency spikes, affecting application performance and user experience.',
    likely_causes: [
      '网络拥塞导致排队延迟',
      '路由路径过长',
      '存在慢速节点',
      '应用层处理延迟',
      '交换机转发延迟',
      'CPU或内存瓶颈',
      '中断处理延迟'
    ],
    likely_causes_en: [
      'Network congestion causing queuing delay',
      'Routing path too long',
      'Slow nodes present',
      'Application layer processing delay',
      'Switch forwarding delay',
      'CPU or memory bottleneck',
      'Interrupt handling delay'
    ],
    recommended_actions: [
      '使用拓扑图分析路由路径',
      '检查是否存在拥塞（查看Xmit标签页）',
      '优化路由算法',
      '检查应用性能',
      '监控节点CPU和内存使用率',
      '考虑使用更快的交换机或优化配置',
      '检查网卡中断配置'
    ],
    recommended_actions_en: [
      'Analyze routing path using topology map',
      'Check for congestion (see Xmit tab)',
      'Optimize routing algorithm',
      'Check application performance',
      'Monitor node CPU and memory usage',
      'Consider faster switches or optimize configuration',
      'Check NIC interrupt configuration'
    ],
    reference: 'Latency Optimization Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/MLNXOFEDv531001/Performance+Tuning',
    urgency: 'medium',
    impact: {
      performance: 'high',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: '1-4 hours',
    tools_needed: ['Network analyzer', 'Performance monitoring tools', 'ibdiagnet']
  },

  HISTOGRAM_UPPER_BUCKET: {
    title: '高延迟桶占比过高',
    titleEn: 'High Latency Bucket Ratio Excessive',
    category: 'histogram',
    severity: 'warning',
    threshold: 'Upper Bucket Ratio > 10%',
    thresholdValue: 0.1,
    why_it_matters: '超过10%的数据包落在高延迟区间，表明存在持续的性能问题。',
    why_it_matters_en: 'More than 10% of packets falling in high latency buckets indicates persistent performance issues.',
    likely_causes: [
      '持续的网络拥塞',
      '路由不优',
      '设备性能瓶颈',
      '应用行为异常',
      '流量突发',
      '队列配置不当'
    ],
    likely_causes_en: [
      'Persistent network congestion',
      'Suboptimal routing',
      'Device performance bottleneck',
      'Abnormal application behavior',
      'Traffic bursts',
      'Improper queue configuration'
    ],
    recommended_actions: [
      '分析延迟分布直方图',
      '识别延迟峰值的时间模式',
      '检查拥塞和BER问题',
      '优化网络配置',
      '调整应用参数',
      '考虑增加带宽或负载均衡'
    ],
    recommended_actions_en: [
      'Analyze latency distribution histogram',
      'Identify timing patterns of latency peaks',
      'Check congestion and BER issues',
      'Optimize network configuration',
      'Adjust application parameters',
      'Consider increasing bandwidth or load balancing'
    ],
    reference: 'Performance Analysis',
    reference_url: 'https://docs.nvidia.com/networking/display/IBDiagnetUserManualv2130/Performance+Histogram',
    urgency: 'medium',
    impact: {
      performance: 'high',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: '1-4 hours',
    tools_needed: ['Performance monitoring tools', 'ibdiagnet']
  },

  HISTOGRAM_JITTER: {
    title: '延迟抖动过大',
    titleEn: 'Excessive Latency Jitter',
    category: 'histogram',
    severity: 'warning',
    threshold: 'Max RTT >> Min RTT',
    thresholdValue: null,
    why_it_matters: '延迟抖动大表明网络行为不可预测，对实时应用和同步操作影响很大。',
    why_it_matters_en: 'High latency jitter indicates unpredictable network behavior, significantly affecting real-time applications and synchronized operations.',
    likely_causes: [
      '间歇性拥塞',
      '路由不稳定',
      '共享资源竞争',
      '后台流量干扰',
      '交换机缓冲不足'
    ],
    likely_causes_en: [
      'Intermittent congestion',
      'Routing instability',
      'Shared resource contention',
      'Background traffic interference',
      'Insufficient switch buffering'
    ],
    recommended_actions: [
      '识别抖动的时间规律',
      '隔离后台流量',
      '使用流量整形',
      '优化QoS配置',
      '考虑专用网络资源'
    ],
    recommended_actions_en: [
      'Identify timing patterns of jitter',
      'Isolate background traffic',
      'Use traffic shaping',
      'Optimize QoS configuration',
      'Consider dedicated network resources'
    ],
    reference: 'Jitter Analysis Guide',
    urgency: 'medium',
    impact: {
      performance: 'high',
      reliability: 'low',
      dataIntegrity: 'none'
    },
    mttr_estimate: '1-3 hours',
    tools_needed: ['Performance monitoring tools']
  },

  HISTOGRAM_MIN_RTT_HIGH: {
    title: '最小延迟偏高',
    titleEn: 'Minimum RTT High',
    category: 'histogram',
    severity: 'info',
    threshold: 'Min RTT > 预期值',
    thresholdValue: null,
    why_it_matters: '即使最小延迟也偏高，可能表明物理距离长、路由不优或固有延迟问题。',
    why_it_matters_en: 'Even minimum latency being high may indicate long physical distance, suboptimal routing, or inherent latency issues.',
    likely_causes: [
      '物理距离远',
      '经过过多跳数',
      '交换机固有延迟',
      '路由路径不优',
      '设备处理延迟'
    ],
    likely_causes_en: [
      'Long physical distance',
      'Too many hops',
      'Switch inherent latency',
      'Suboptimal routing path',
      'Device processing delay'
    ],
    recommended_actions: [
      '分析路由路径',
      '考虑优化拓扑',
      '评估是否需要更快的交换机',
      '减少不必要的跳数'
    ],
    recommended_actions_en: [
      'Analyze routing path',
      'Consider optimizing topology',
      'Evaluate need for faster switches',
      'Reduce unnecessary hops'
    ],
    reference: 'Latency Baseline Analysis',
    urgency: 'low',
    impact: {
      performance: 'medium',
      reliability: 'none',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'N/A (architectural consideration)',
    tools_needed: ['Topology analysis tools']
  },

  // ==================== Fan/Chassis 相关问题 ====================
  FAN_SPEED_LOW: {
    title: '风扇转速过低',
    titleEn: 'Fan Speed Low',
    category: 'fan',
    severity: 'critical',
    threshold: 'Speed < MinSpeed',
    thresholdValue: null,
    why_it_matters: '风扇转速过低会导致散热不足，可能造成设备过热、性能下降或自动关机。',
    why_it_matters_en: 'Low fan speed causes insufficient cooling, potentially leading to overheating, performance degradation, or automatic shutdown.',
    likely_causes: [
      '风扇故障或老化',
      '灰尘堵塞',
      '风扇控制问题',
      '电源供电不足',
      '温度传感器故障'
    ],
    likely_causes_en: [
      'Fan failure or aging',
      'Dust blockage',
      'Fan control issues',
      'Insufficient power supply',
      'Temperature sensor failure'
    ],
    recommended_actions: [
      '检查风扇是否正常旋转',
      '清洁风扇和通风口',
      '检查风扇电源连接',
      '更换故障风扇',
      '监控设备温度'
    ],
    recommended_actions_en: [
      'Check if fan is rotating normally',
      'Clean fan and ventilation',
      'Check fan power connection',
      'Replace faulty fan',
      'Monitor device temperature'
    ],
    reference: 'Chassis Maintenance Guide',
    urgency: 'critical',
    impact: {
      performance: 'high',
      reliability: 'critical',
      dataIntegrity: 'low'
    },
    mttr_estimate: '15-60 minutes',
    tools_needed: ['Replacement fans', 'Compressed air']
  },

  FAN_SPEED_HIGH: {
    title: '风扇转速过高',
    titleEn: 'Fan Speed High',
    category: 'fan',
    severity: 'warning',
    threshold: 'Speed > MaxSpeed × 0.9',
    thresholdValue: null,
    why_it_matters: '风扇长时间高速运转可能表明散热系统压力大，或存在过热风险。',
    why_it_matters_en: 'Fan running at high speed for extended periods may indicate cooling system stress or overheating risk.',
    likely_causes: [
      '设备负载过高',
      '环境温度高',
      '散热通道阻塞',
      '其他风扇故障',
      '热传导问题'
    ],
    likely_causes_en: [
      'High device load',
      'High ambient temperature',
      'Cooling path blocked',
      'Other fan failures',
      'Heat transfer issues'
    ],
    recommended_actions: [
      '检查设备温度',
      '检查机房温度',
      '清洁通风口',
      '检查其他风扇状态',
      '考虑降低负载或增加散热'
    ],
    recommended_actions_en: [
      'Check device temperature',
      'Check room temperature',
      'Clean ventilation',
      'Check other fan status',
      'Consider reducing load or improving cooling'
    ],
    reference: 'Thermal Management Guide',
    urgency: 'medium',
    impact: {
      performance: 'low',
      reliability: 'medium',
      dataIntegrity: 'none'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['Temperature monitor', 'Compressed air']
  },

  // ==================== Topology 相关问题 ====================
  TOPOLOGY_MISMATCH: {
    title: '拓扑与预期不符',
    titleEn: 'Topology Mismatch',
    category: 'topology',
    severity: 'warning',
    threshold: '实际拓扑 ≠ 预期拓扑',
    thresholdValue: null,
    why_it_matters: '拓扑变化可能表明设备故障、线缆断开或未授权的网络变更。',
    why_it_matters_en: 'Topology changes may indicate device failure, cable disconnection, or unauthorized network changes.',
    likely_causes: [
      '设备下线或故障',
      '线缆断开或移除',
      '新设备上线',
      '维护操作',
      '配置错误'
    ],
    likely_causes_en: [
      'Device offline or failed',
      'Cable disconnected or removed',
      'New device online',
      'Maintenance operation',
      'Configuration error'
    ],
    recommended_actions: [
      '对比实际拓扑和预期拓扑',
      '确认变更是否经过授权',
      '检查缺失的设备或链路',
      '更新预期拓扑文件',
      '记录变更日志'
    ],
    recommended_actions_en: [
      'Compare actual topology with expected',
      'Confirm if change was authorized',
      'Check for missing devices or links',
      'Update expected topology file',
      'Document change log'
    ],
    reference: 'Topology Management',
    reference_url: 'https://docs.nvidia.com/networking/display/IBDiagnetUserManualv2130/Topology+Verification',
    urgency: 'medium',
    impact: {
      performance: 'varies',
      reliability: 'varies',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'Varies',
    tools_needed: ['Topology file', 'ibdiagnet']
  },

  TOPOLOGY_DUPLICATE_GUID: {
    title: 'GUID 重复',
    titleEn: 'Duplicate GUID',
    category: 'topology',
    severity: 'critical',
    threshold: '存在重复GUID',
    thresholdValue: null,
    why_it_matters: 'GUID重复会导致路由混乱、数据包错误投递、严重的网络问题。',
    why_it_matters_en: 'Duplicate GUID causes routing confusion, misdirected packets, and serious network issues.',
    likely_causes: [
      '设备GUID被错误复制',
      '虚拟化环境配置问题',
      '设备故障导致GUID异常',
      '固件问题'
    ],
    likely_causes_en: [
      'Device GUID incorrectly duplicated',
      'Virtualization environment configuration issue',
      'Device failure causing GUID anomaly',
      'Firmware issues'
    ],
    recommended_actions: [
      '识别重复GUID的设备',
      '重新分配唯一GUID',
      '检查虚拟化配置',
      '升级固件',
      '联系设备厂商'
    ],
    recommended_actions_en: [
      'Identify devices with duplicate GUID',
      'Reassign unique GUID',
      'Check virtualization configuration',
      'Upgrade firmware',
      'Contact device vendor'
    ],
    reference: 'GUID Management',
    urgency: 'critical',
    impact: {
      performance: 'critical',
      reliability: 'critical',
      dataIntegrity: 'high'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['ibdiagnet', 'mstconfig']
  },

  TOPOLOGY_ASYMMETRIC: {
    title: '拓扑不对称',
    titleEn: 'Asymmetric Topology',
    category: 'topology',
    severity: 'info',
    threshold: '拓扑非对称',
    thresholdValue: null,
    why_it_matters: '不对称拓扑可能导致路由不均衡，影响某些路径的性能。',
    why_it_matters_en: 'Asymmetric topology may cause unbalanced routing, affecting performance on some paths.',
    likely_causes: [
      '设计如此',
      '扩展阶段',
      '设备故障导致',
      '未完成的变更'
    ],
    likely_causes_en: [
      'By design',
      'Expansion phase',
      'Caused by device failure',
      'Incomplete changes'
    ],
    recommended_actions: [
      '确认是否为预期设计',
      '如非预期，调查原因',
      '评估对性能的影响',
      '考虑调整路由策略'
    ],
    recommended_actions_en: [
      'Confirm if this is expected design',
      'If unexpected, investigate cause',
      'Evaluate impact on performance',
      'Consider adjusting routing strategy'
    ],
    reference: 'Topology Design Guide',
    urgency: 'low',
    impact: {
      performance: 'low',
      reliability: 'none',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'N/A',
    tools_needed: ['Topology analysis tools']
  },

  // ==================== PCI 降级问题 ====================
  PCI_DEGRADATION: {
    title: 'PCI 速度降级',
    titleEn: 'PCI Speed Degradation',
    category: 'pci',
    severity: 'critical',
    threshold: 'Active Speed < Enabled Speed',
    thresholdValue: null,
    why_it_matters: 'PCI通道运行在低于配置的速度（如Gen4降到Gen3），会导致主机到网卡的带宽减少25-50%，严重影响性能。',
    why_it_matters_en: 'PCI lanes running below configured speed (e.g., Gen4 to Gen3) reduces host-to-NIC bandwidth by 25-50%, severely impacting performance.',
    likely_causes: [
      'PCIe插槽接触不良',
      '主板或CPU PCIe控制器问题',
      '网卡硬件问题',
      'BIOS设置不正确',
      '电源供应不足',
      '散热不良导致降速保护'
    ],
    likely_causes_en: [
      'Poor PCIe slot contact',
      'Motherboard or CPU PCIe controller issues',
      'NIC hardware problems',
      'Incorrect BIOS settings',
      'Insufficient power supply',
      'Thermal throttling due to poor cooling'
    ],
    recommended_actions: [
      '重新插拔网卡，确保完全插入插槽',
      '检查BIOS中PCIe设置是否正确（Gen4/Gen5）',
      '检查系统电源是否充足',
      '检查服务器散热是否正常',
      '尝试更换到其他PCIe插槽',
      '更新主板BIOS和网卡固件',
      '如果问题持续，可能需要更换网卡'
    ],
    recommended_actions_en: [
      'Reseat NIC; ensure fully inserted in slot',
      'Check BIOS PCIe settings (Gen4/Gen5)',
      'Verify system power is adequate',
      'Check server cooling is normal',
      'Try different PCIe slot',
      'Update motherboard BIOS and NIC firmware',
      'If issue persists, NIC replacement may be needed'
    ],
    reference: 'PCIe Troubleshooting Guide',
    reference_url: 'https://docs.nvidia.com/networking/display/ConnectX7VPI/Troubleshooting',
    urgency: 'high',
    impact: {
      performance: 'critical',
      reliability: 'medium',
      dataIntegrity: 'none'
    },
    mttr_estimate: '30-120 minutes',
    tools_needed: ['BIOS access', 'System monitoring tools', 'lspci']
  },

  // ==================== 端口计数器问题 ====================
  PORT_COUNTER_INCREASED: {
    title: '端口计数器运行中增长',
    titleEn: 'Port Counter Increased During Run',
    category: 'counters',
    severity: 'warning',
    threshold: 'Counter > 0 during ibdiagnet run',
    thresholdValue: 1,
    why_it_matters: '端口错误计数器在诊断运行期间增长表明存在活跃的问题，可能正在影响网络性能和可靠性。',
    why_it_matters_en: 'Port error counters increasing during diagnostic run indicates active issues currently affecting network performance and reliability.',
    likely_causes: [
      '链路不稳定',
      '信号质量问题',
      '线缆或光模块故障',
      '拥塞导致的丢包',
      '路由问题'
    ],
    likely_causes_en: [
      'Link instability',
      'Signal quality issues',
      'Cable or optical module failure',
      'Congestion-related packet drops',
      'Routing problems'
    ],
    recommended_actions: [
      '识别具体增长的计数器类型',
      '检查相关链路的物理层健康',
      '查看BER和光功率',
      '检查是否有拥塞',
      '清除计数器后重新监控',
      '如果持续增长，更换线缆或光模块'
    ],
    recommended_actions_en: [
      'Identify specific counter type increasing',
      'Check physical layer health of related links',
      'Review BER and optical power',
      'Check for congestion',
      'Clear counters and re-monitor',
      'If continues increasing, replace cable or optical module'
    ],
    reference: 'Port Counter Analysis Guide',
    urgency: 'medium',
    impact: {
      performance: 'medium',
      reliability: 'high',
      dataIntegrity: 'low'
    },
    mttr_estimate: '30-90 minutes',
    tools_needed: ['ibdiagnet', 'perfquery', 'Optical power meter']
  },

  // ==================== 节点描述重复 ====================
  NODE_DUPLICATED_DESCRIPTION: {
    title: '节点描述重复',
    titleEn: 'Duplicated Node Description',
    category: 'topology',
    severity: 'info',
    threshold: '多个节点使用相同描述',
    thresholdValue: null,
    why_it_matters: '重复的节点描述会导致管理和故障排查困难，在大型集群中难以区分设备。',
    why_it_matters_en: 'Duplicated node descriptions make management and troubleshooting difficult; hard to distinguish devices in large clusters.',
    likely_causes: [
      '节点未配置唯一名称',
      '使用了默认设备名称',
      '克隆配置时未更新名称',
      '自动化部署脚本问题'
    ],
    likely_causes_en: [
      'Nodes not configured with unique names',
      'Using default device names',
      'Name not updated when cloning config',
      'Automation/deployment script issues'
    ],
    recommended_actions: [
      '为每个节点配置唯一的描述名称',
      '使用主机名或位置信息作为名称',
      '更新部署脚本确保唯一性',
      '使用 smpquery nodedesc 查看当前名称',
      '使用 smpquery nodedesc -D 设置新名称'
    ],
    recommended_actions_en: [
      'Configure unique description for each node',
      'Use hostname or location info as name',
      'Update deployment scripts to ensure uniqueness',
      'Use smpquery nodedesc to view current name',
      'Use smpquery nodedesc -D to set new name'
    ],
    reference: 'Node Configuration Guide',
    urgency: 'low',
    impact: {
      performance: 'none',
      reliability: 'none',
      dataIntegrity: 'none'
    },
    mttr_estimate: '5-15 minutes per node',
    tools_needed: ['smpquery', 'opensm-tools']
  },

  // ==================== 线缆测量问题 ====================
  CABLE_PRTL_ISSUE: {
    title: '线缆长度无法测量',
    titleEn: 'Cable Length Cannot Be Measured',
    category: 'cable',
    severity: 'info',
    threshold: 'PRTL data unavailable',
    thresholdValue: null,
    why_it_matters: '无法通过PRTL（Physical Round Trip Latency）寄存器测量线缆长度，可能是设备不支持此功能或链路配置问题。',
    why_it_matters_en: 'Cannot measure cable length via PRTL (Physical Round Trip Latency) register; device may not support this feature or link configuration issue.',
    likely_causes: [
      '设备固件不支持PRTL',
      '端口类型不支持测量',
      '链路未完全建立',
      '使用的是主动光缆（AOC）'
    ],
    likely_causes_en: [
      'Device firmware does not support PRTL',
      'Port type does not support measurement',
      'Link not fully established',
      'Using Active Optical Cable (AOC)'
    ],
    recommended_actions: [
      '这通常不是问题，仅供参考',
      '如需线缆长度信息，可查看线缆标签',
      '确保固件版本是最新的',
      '对于AOC，长度信息在线缆EEPROM中'
    ],
    recommended_actions_en: [
      'This is usually not an issue; informational only',
      'If cable length needed, check cable label',
      'Ensure firmware version is up to date',
      'For AOC, length info is in cable EEPROM'
    ],
    reference: 'Cable Diagnostics Guide',
    urgency: 'none',
    impact: {
      performance: 'none',
      reliability: 'none',
      dataIntegrity: 'none'
    },
    mttr_estimate: 'N/A',
    tools_needed: []
  }
}

/**
 * 根据问题类型获取详细解释
 * Get detailed explanation by error type
 */
export function getErrorExplanation(errorType) {
  return ERROR_KNOWLEDGE_BASE[errorType] || {
    title: '未知问题',
    titleEn: 'Unknown Issue',
    category: 'unknown',
    severity: 'info',
    threshold: 'N/A',
    why_it_matters: '需要进一步分析',
    why_it_matters_en: 'Requires further analysis',
    likely_causes: ['需要查看详细日志'],
    likely_causes_en: ['Need to review detailed logs'],
    recommended_actions: ['联系技术支持'],
    recommended_actions_en: ['Contact technical support'],
    reference: 'General Troubleshooting',
    urgency: 'medium'
  }
}

/**
 * 获取严重程度信息
 * Get severity level information
 */
export function getSeverityInfo(severity) {
  return SEVERITY_LEVELS[severity] || SEVERITY_LEVELS.info
}

/**
 * 获取问题类别信息
 * Get issue category information
 */
export function getCategoryInfo(category) {
  return ISSUE_CATEGORIES[category] || {
    label: category,
    labelCn: category,
    icon: 'AlertCircle',
    description: 'Unknown category'
  }
}

/**
 * 按严重程度对问题进行排序
 * Sort issues by severity
 */
export function sortBySeverity(issues) {
  const priorityMap = { critical: 0, warning: 1, info: 2, none: 3 }
  return [...issues].sort((a, b) => {
    const aP = priorityMap[a.severity] ?? 3
    const bP = priorityMap[b.severity] ?? 3
    return aP - bP
  })
}

/**
 * 获取所有问题的快速摘要
 * Get quick summary of all issues
 */
export function getIssueSummary(issues) {
  const summary = {
    total: issues.length,
    critical: 0,
    warning: 0,
    info: 0,
    byCategory: {}
  }

  issues.forEach(issue => {
    const kb = getErrorExplanation(issue.type || issue)
    if (kb.severity === 'critical') summary.critical++
    else if (kb.severity === 'warning') summary.warning++
    else summary.info++

    const cat = kb.category || 'unknown'
    summary.byCategory[cat] = (summary.byCategory[cat] || 0) + 1
  })

  return summary
}

/**
 * 生成综合行动计划
 * Generate comprehensive action plan
 */
export function generateActionPlan(issues) {
  const actions = []
  const seen = new Set()

  // Sort by severity first
  const sortedIssues = sortBySeverity(issues)

  sortedIssues.forEach(issue => {
    const kb = getErrorExplanation(issue.type || issue)
    if (kb.recommended_actions) {
      kb.recommended_actions.forEach((action, idx) => {
        if (!seen.has(action)) {
          seen.add(action)
          actions.push({
            action,
            actionEn: kb.recommended_actions_en?.[idx] || action,
            severity: kb.severity,
            category: kb.category,
            urgency: kb.urgency,
            reference: kb.reference,
            issueTitle: kb.title
          })
        }
      })
    }
  })

  return actions
}

/**
 * 根据数据自动识别问题类型
 * Automatically identify issue type based on data
 */
export function identifyIssueType(row, dataType) {
  switch (dataType) {
    case 'cable': {
      const temp = Number(row['Temperature (c)']) || 0
      if (temp >= 70) return 'CABLE_HIGH_TEMPERATURE'

      // Check TX Bias alarm
      const txBias = row['TX Bias Alarm and Warning']
      if (txBias && String(txBias).trim() !== '0' && String(txBias).trim() !== '') {
        return 'CABLE_TX_BIAS_ALARM'
      }

      const txPower = row['TX Power Alarm and Warning']
      if (txPower && String(txPower).trim() !== '0' && String(txPower).trim() !== '') {
        return 'CABLE_TX_POWER_ALARM'
      }

      const rxPower = row['RX Power Alarm and Warning']
      if (rxPower && String(rxPower).trim() !== '0' && String(rxPower).trim() !== '') {
        return 'CABLE_RX_POWER_ALARM'
      }

      // Check voltage alarm
      const voltage = row['Latched Voltage Alarm and Warning']
      if (voltage && String(voltage).trim() !== '0' && String(voltage).trim() !== '') {
        return 'CABLE_VOLTAGE_ALARM'
      }

      const compliance = String(row.CableComplianceStatus || '').toLowerCase()
      if (compliance !== 'ok' && compliance !== '') {
        return 'CABLE_COMPLIANCE_ISSUE'
      }

      const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
      if (speedStatus !== 'ok' && speedStatus !== '') {
        return 'CABLE_SPEED_MISMATCH'
      }
      break
    }

    case 'ber': {
      const severity = String(row.SymbolBERSeverity || '').toLowerCase()
      const eventName = String(row.EventName || '').toLowerCase()

      if (eventName.includes('no_threshold')) {
        return 'BER_NO_THRESHOLD'
      }
      if (eventName.includes('rs_fec_high') || eventName.includes('rs_fec_excessive')) {
        return 'BER_RS_FEC_HIGH_ERRORS'
      }
      if (severity === 'critical') {
        return 'BER_CRITICAL'
      }
      if (severity === 'warning') {
        if (eventName.includes('fec')) {
          return 'BER_FEC_EXCESSIVE'
        }
        return 'BER_WARNING'
      }
      break
    }

    case 'xmit': {
      const waitRatio = Number(row.WaitRatioPct) || 0
      const creditWatchdog = Number(row.CreditWatchdogTimeout) || 0
      const linkCompliance = String(row.LinkComplianceStatus || '').toLowerCase()
      const portRcvErrors = Number(row.PortRcvErrors) || 0
      const portXmitDiscards = Number(row.PortXmitDiscards) || 0
      const linkDowned = Number(row.LinkDownedCounter) || 0

      if (creditWatchdog > 0) {
        return 'XMIT_CREDIT_WATCHDOG'
      }
      if (portXmitDiscards > 0) {
        return 'XMIT_HIGH_DISCARD'
      }
      if (portRcvErrors > 0) {
        return 'XMIT_HIGH_RCV_ERRORS'
      }
      if (waitRatio >= 5) {
        return 'XMIT_SEVERE_CONGESTION'
      }
      if (waitRatio >= 1) {
        return 'XMIT_MODERATE_CONGESTION'
      }
      if (linkCompliance === 'downshift') {
        // Check if it's speed or width downshift
        const activeWidth = Number(row.ActiveLinkWidthValue) || 0
        const supportedWidth = Number(row.SupportedLinkWidthValue) || 0
        if (activeWidth < supportedWidth && activeWidth > 0) {
          return 'XMIT_LINK_WIDTH_DOWNSHIFT'
        }
        return 'XMIT_LINK_DOWNSHIFT'
      }
      if (linkDowned > 0) {
        return 'XMIT_LINK_DOWN_COUNTER'
      }
      if (Number(row.FECNCount) > 0 || Number(row.BECNCount) > 0) {
        return 'XMIT_FECN_BECN'
      }
      break
    }

    case 'hca': {
      const fwCompliant = row.FW_Compliant
      const psidCompliant = row.PSID_Compliant

      if (fwCompliant === false || fwCompliant === 'false') {
        return 'HCA_FIRMWARE_OUTDATED'
      }
      if (psidCompliant === false || psidCompliant === 'false') {
        return 'HCA_PSID_UNSUPPORTED'
      }
      break
    }

    case 'histogram': {
      const p99OverMedian = Number(row.RttP99OverMedian) || 0
      const upperRatio = Number(row.RttUpperBucketRatio) || 0
      const minRtt = Number(row.RttMinUs) || 0
      const maxRtt = Number(row.RttMaxUs) || 0

      // Check for jitter (max >> min)
      if (minRtt > 0 && maxRtt > minRtt * 10) {
        return 'HISTOGRAM_JITTER'
      }
      if (p99OverMedian > 5) {
        return 'HISTOGRAM_HIGH_LATENCY'
      }
      if (p99OverMedian > 3) {
        return 'HISTOGRAM_HIGH_LATENCY'
      }
      if (upperRatio > 0.2) {
        return 'HISTOGRAM_UPPER_BUCKET'
      }
      if (upperRatio > 0.1) {
        return 'HISTOGRAM_UPPER_BUCKET'
      }
      break
    }

    case 'fan': {
      const fanSpeed = Number(row.FanSpeed) || 0
      const minSpeed = Number(row.MinSpeed) || 0
      const maxSpeed = Number(row.MaxSpeed) || 0
      const status = String(row.FanStatus || '').toLowerCase()

      if (status === 'alert' || (minSpeed > 0 && fanSpeed < minSpeed)) {
        return 'FAN_SPEED_LOW'
      }
      if (maxSpeed > 0 && fanSpeed > maxSpeed * 0.9) {
        return 'FAN_SPEED_HIGH'
      }
      break
    }
  }

  return null
}

/**
 * 识别行中的所有问题（一行可能有多个问题）
 * Identify all issues in a row (a row may have multiple issues)
 */
export function identifyAllIssues(row, dataType) {
  const issues = []

  switch (dataType) {
    case 'cable': {
      const temp = Number(row['Temperature (c)']) || 0
      if (temp >= 70) issues.push('CABLE_HIGH_TEMPERATURE')

      const txBias = row['TX Bias Alarm and Warning']
      if (txBias && String(txBias).trim() !== '0' && String(txBias).trim() !== '') {
        issues.push('CABLE_TX_BIAS_ALARM')
      }

      const txPower = row['TX Power Alarm and Warning']
      if (txPower && String(txPower).trim() !== '0' && String(txPower).trim() !== '') {
        issues.push('CABLE_TX_POWER_ALARM')
      }

      const rxPower = row['RX Power Alarm and Warning']
      if (rxPower && String(rxPower).trim() !== '0' && String(rxPower).trim() !== '') {
        issues.push('CABLE_RX_POWER_ALARM')
      }

      const voltage = row['Latched Voltage Alarm and Warning']
      if (voltage && String(voltage).trim() !== '0' && String(voltage).trim() !== '') {
        issues.push('CABLE_VOLTAGE_ALARM')
      }

      const compliance = String(row.CableComplianceStatus || '').toLowerCase()
      if (compliance !== 'ok' && compliance !== '') {
        issues.push('CABLE_COMPLIANCE_ISSUE')
      }

      const speedStatus = String(row.CableSpeedStatus || '').toLowerCase()
      if (speedStatus !== 'ok' && speedStatus !== '') {
        issues.push('CABLE_SPEED_MISMATCH')
      }
      break
    }

    case 'xmit': {
      const waitRatio = Number(row.WaitRatioPct) || 0
      const creditWatchdog = Number(row.CreditWatchdogTimeout) || 0
      const portRcvErrors = Number(row.PortRcvErrors) || 0
      const portXmitDiscards = Number(row.PortXmitDiscards) || 0
      const linkDowned = Number(row.LinkDownedCounter) || 0
      const linkCompliance = String(row.LinkComplianceStatus || '').toLowerCase()

      if (creditWatchdog > 0) issues.push('XMIT_CREDIT_WATCHDOG')
      if (portXmitDiscards > 0) issues.push('XMIT_HIGH_DISCARD')
      if (portRcvErrors > 0) issues.push('XMIT_HIGH_RCV_ERRORS')
      if (waitRatio >= 5) issues.push('XMIT_SEVERE_CONGESTION')
      else if (waitRatio >= 1) issues.push('XMIT_MODERATE_CONGESTION')
      if (linkCompliance === 'downshift') issues.push('XMIT_LINK_DOWNSHIFT')
      if (linkDowned > 0) issues.push('XMIT_LINK_DOWN_COUNTER')
      if (Number(row.FECNCount) > 0 || Number(row.BECNCount) > 0) issues.push('XMIT_FECN_BECN')
      break
    }
    // Add more cases as needed
  }

  return issues
}

/**
 * 获取问题类型列表按类别分组
 * Get issue types grouped by category
 */
export function getIssueTypesByCategory() {
  const grouped = {}

  Object.entries(ERROR_KNOWLEDGE_BASE).forEach(([key, value]) => {
    const category = value.category || 'unknown'
    if (!grouped[category]) {
      grouped[category] = []
    }
    grouped[category].push({
      key,
      ...value
    })
  })

  return grouped
}

/**
 * 搜索知识库
 * Search knowledge base
 */
export function searchKnowledgeBase(query) {
  const lowerQuery = query.toLowerCase()
  const results = []

  Object.entries(ERROR_KNOWLEDGE_BASE).forEach(([key, value]) => {
    const searchText = [
      value.title,
      value.titleEn,
      value.why_it_matters,
      value.why_it_matters_en,
      ...(value.likely_causes || []),
      ...(value.likely_causes_en || []),
      ...(value.recommended_actions || []),
      ...(value.recommended_actions_en || [])
    ].join(' ').toLowerCase()

    if (searchText.includes(lowerQuery)) {
      results.push({ key, ...value })
    }
  })

  return results
}
