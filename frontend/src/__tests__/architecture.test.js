/**
 * 架构验证测试
 * 确保新架构符合设计规范
 */

import { describe, test, expect } from 'vitest'

describe('架构规范验证', () => {
  test('API 服务层应该正确导出', () => {
    const api = require('../services/api')
    expect(api.uploadIbdiagnetFile).toBeDefined()
    expect(api.uploadCsvFile).toBeDefined()
    expect(api.validateFile).toBeDefined()
  })

  test('配置管理应该正确导出', () => {
    const config = require('../config')
    expect(config.API_CONFIG).toBeDefined()
    expect(config.FILE_CONSTRAINTS).toBeDefined()
    expect(config.BUSINESS_RULES).toBeDefined()
  })

  test('状态管理应该正确初始化', () => {
    const { useAppStore } = require('../store/appStore')
    const store = useAppStore.getState()

    expect(store.loading).toBe(false)
    expect(store.uploadProgress).toBe(0)
    expect(store.error).toBeNull()
  })

  test('工具函数应该正确工作', () => {
    const { extractHostLabel, buildFrequentRebootHosts } = require('../utils/dataProcessing')

    expect(extractHostLabel('host123 HCA-1')).toBe('host123')
    expect(extractHostLabel('')).toBe('Unknown')
  })
})
