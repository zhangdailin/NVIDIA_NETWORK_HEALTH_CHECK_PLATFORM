import { AlertTriangle, Activity, Shield, Database } from 'lucide-react'
import UnifiedAnalysisPage from './UnifiedAnalysisPage'
import { formatCount, toNumber, ensureArray } from './analysisUtils'

const normalizeValue = (value, fallback = 'N/A') => {
  if (value === null || value === undefined) {
    return fallback
  }
  const str = String(value).trim()
  return str.length ? str : fallback
}

const formatExponent = (exp) => {
  const sign = exp >= 0 ? '+' : '-'
  const absValue = Math.abs(exp)
  return `${sign}${String(absValue).padStart(3, '0')}`
}

const formatBer = (value) => {
  const num = Number(value)
  if (!Number.isFinite(num) || num < 0) {
    return 'N/A'
  }
  if (num === 0) {
    return '0.00E+00'
  }
  const exponent = Math.floor(Math.log10(num))
  const mantissa = num / Math.pow(10, exponent)
  return `${mantissa.toFixed(2)}E${formatExponent(exponent)}`
}

const pickFormattedBer = (directCandidates = [], numericCandidates = [], logCandidates = []) => {
  for (const candidate of directCandidates) {
    if (candidate === null || candidate === undefined) continue
    const text = String(candidate).trim()
    if (text.length && text !== 'nan') {
      return text
    }
  }
  for (const candidate of numericCandidates) {
    const num = Number(candidate)
    if (Number.isFinite(num)) {
      return formatBer(num)
    }
  }
  for (const candidate of logCandidates) {
    const logValue = Number(candidate)
    if (Number.isFinite(logValue)) {
      return formatBer(Math.pow(10, logValue))
    }
  }
  return 'N/A'
}

function BERAnalysis({ berData = [], showOnlyProblematic = false }) {
  const rows = ensureArray(berData)

  // 定义严重度判断逻辑
  const getSeverity = (row) => {
    const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
    if (severity === 'critical' || severity === 'error') {
      return 'critical'
    }
    if (severity === 'warning' || severity === 'warn') {
      return 'warning'
    }

    // 检查是否有 Symbol Error
    const hasSymbolErrors = toNumber(row['Symbol Err'] ?? row.SymbolErr ?? row.symbolErr) > 0
    if (hasSymbolErrors) {
      const anomaly = row['IBH Anomaly'] || row.IBHAnomaly
      if (anomaly) {
        return 'warning'
      }
    }

    return 'ok'
  }

  // 定义问题描述逻辑
  const getIssueReason = (row) => {
    const severity = String(row.SymbolBERSeverity || row.Severity || '').toLowerCase()
    const hasSymbolErrors = toNumber(row['Symbol Err'] ?? row.SymbolErr ?? row.symbolErr) > 0
    const anomaly = row['IBH Anomaly'] || row.IBHAnomaly

    if (severity === 'critical' || severity === 'error') {
      const symbolBer = pickFormattedBer(
        [row['Symbol BER'], row.SymbolBER, row.symbolBer],
        [row.SymbolBERValue],
        [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
      )
      return `严重 BER 问题 (Symbol BER: ${symbolBer})`
    }

    if (hasSymbolErrors && anomaly) {
      return anomaly
    }

    if (severity === 'warning' || severity === 'warn') {
      const symbolBer = pickFormattedBer(
        [row['Symbol BER'], row.SymbolBER, row.symbolBer],
        [row.SymbolBERValue],
        [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
      )
      return `BER 警告 (Symbol BER: ${symbolBer})`
    }

    if (hasSymbolErrors) {
      return `Symbol Error: ${formatCount(row['Symbol Err'] ?? row.SymbolErr)}`
    }

    return '正常'
  }

  // 计算统计
  const criticalCount = rows.filter(r => getSeverity(r) === 'critical').length
  const warningCount = rows.filter(r => getSeverity(r) === 'warning').length
  const problemCount = rows.filter(r => {
    const hasSymbolErrors = toNumber(r['Symbol Err'] ?? r.SymbolErr ?? r.symbolErr) > 0
    const anomaly = r['IBH Anomaly'] || r.IBHAnomaly
    return hasSymbolErrors && anomaly
  }).length

  // 指标卡片配置
  const metricCards = [
    {
      key: 'total',
      label: '总端口数',
      value: rows.length,
      description: '全部检测端口',
      icon: Database,
    },
    {
      key: 'problem',
      label: '异常端口',
      value: problemCount,
      description: 'Symbol Error > 0 的端口',
      icon: AlertTriangle,
    },
    {
      key: 'critical',
      label: '严重 BER 问题',
      value: criticalCount,
      description: 'BER 超过严重阈值',
      icon: Shield,
    },
    {
      key: 'warning',
      label: '警告 BER 问题',
      value: warningCount,
      description: 'BER 超过警告阈值',
      icon: Activity,
    },
  ]

  // 预览表列配置
  const previewColumns = [
    { key: 'IssueSeverity', label: '严重度' },
    { key: 'IssueReason', label: '问题描述' },
    {
      key: 'Node Name',
      label: 'Node Name',
      render: (row) => normalizeValue(row['Node Name'] || row.NodeName),
    },
    {
      key: 'Port Number',
      label: 'Port',
      render: (row) => normalizeValue(row.PortNumber || row['Port Number']),
    },
    {
      key: 'Symbol BER',
      label: 'Symbol BER',
      render: (row) => pickFormattedBer(
        [row['Symbol BER'], row.SymbolBER, row.symbolBer],
        [row.SymbolBERValue],
        [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
      ),
    },
    {
      key: 'Symbol Err',
      label: 'Symbol Err',
      render: (row) => formatCount(row['Symbol Err'] ?? row.SymbolErr),
    },
  ]

  // 优先显示的列（添加处理逻辑以显示格式化的 BER 值）
  const preferredColumns = [
    'Node Name',
    'Port Number',
    'Symbol BER',
    'Symbol Err',
    'IBH Anomaly',
    'Raw BER',
    'Effective BER',
    'Effective Err',
    'Node GUID',
    'LID',
    'Peer LID',
  ]

  // 为数据添加格式化的 BER 字段
  const enrichedData = rows.map(row => ({
    ...row,
    'Symbol BER': pickFormattedBer(
      [row['Symbol BER'], row.SymbolBER, row.symbolBer],
      [row.SymbolBERValue],
      [row.SymbolBERLog10Value, row['Log10 Symbol BER']]
    ),
    'Raw BER': pickFormattedBer(
      [row['Raw BER'], row.RawBER, row.rawBer],
      [row.RawBERValue],
      [row['Log10 Raw BER']]
    ),
    'Effective BER': pickFormattedBer(
      [row['Effective BER'], row.EffectiveBER, row.effectiveBer],
      [row.EffectiveBERValue],
      [row['Log10 Effective BER']]
    ),
    'IBH Anomaly': normalizeValue(row['IBH Anomaly'] || row.IBHAnomaly, '—'),
    'Symbol Err': formatCount(row['Symbol Err'] ?? row.SymbolErr),
    'Effective Err': formatCount(row['Effective Err'] ?? row.EffectiveErr),
    'Node Name': normalizeValue(row['Node Name'] || row.NodeName),
    'Port Number': normalizeValue(row.PortNumber || row['Port Number']),
    'Node GUID': normalizeValue(row.NodeGUID || row['Node GUID']),
    'LID': normalizeValue(row.LID || row['LID']),
    'Peer LID': normalizeValue(row['Peer LID'] || row.PeerLID || row.ConnLID || row['Conn LID (#)']),
  }))

  return (
    <UnifiedAnalysisPage
      title="BER Analysis"
      description="误码率 (BER) 分析与诊断"
      emptyMessage="未检测到 BER 测试数据"
      emptyHint="请确认采集的数据包中包含 BER 相关表格。"
      data={enrichedData}
      totalRows={enrichedData.length}
      metricCards={metricCards}
      getSeverity={getSeverity}
      getIssueReason={getIssueReason}
      topPreviewLimit={10}
      previewColumns={previewColumns}
      preferredColumns={preferredColumns}
      searchPlaceholder="搜索 NodeGUID、端口、节点或 IBH Anomaly..."
      pageSize={20}
    />
  )
}

export default BERAnalysis
