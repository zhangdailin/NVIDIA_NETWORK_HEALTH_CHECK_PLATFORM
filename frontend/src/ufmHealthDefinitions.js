export const UFM_GROUPS = [
  {
    key: 'overview',
    label: '总览',
    description: '健康评分与问题汇总',
    tabs: [
      { key: 'overview', label: '总览' }
    ]
  },
  {
    key: 'health',
    label: '健康与状态',
    description: 'BER、链路与环境',
    tabs: [
      { key: 'ber', label: '误码率 (BER)' },
      { key: 'link', label: '链路状态' },
      { key: 'temp', label: '温度监控' },
    ]
  },
  {
    key: 'inventory',
    label: '资产信息',
    description: '线缆与端口',
    tabs: [
      { key: 'cable', label: '线缆信息' },
    ]
  },
  {
    key: 'performance',
    label: '性能与错误',
    description: '性能计数器与错误',
    tabs: [
      { key: 'errors', label: '端口错误' },
      { key: 'performance', label: '性能分析' },
    ]
  }
]
