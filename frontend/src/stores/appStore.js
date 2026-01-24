/**
 * 全局应用状态管理（Zustand）
 * 统一管理上传状态、分析结果、UI状态等
 */

import { create } from 'zustand'

export const useAppStore = create((set, get) => ({
  // ============ 上传状态 ============
  loading: false,
  uploadProgress: 0,
  error: null,

  setLoading: (loading) => set({ loading }),
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),
  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),

  // ============ 分析结果 ============
  result: null,
  resultType: null, // 'ibdiagnet' | 'csv'

  setResult: (result, type) => set({
    result,
    resultType: type,
    error: null
  }),
  clearResult: () => set({
    result: null,
    resultType: null
  }),

  // ============ UI 状态 ============
  activeTab: 'overview',
  navCollapsedGroups: {},

  setActiveTab: (tab) => set({ activeTab: tab }),
  toggleNavGroup: (groupKey) => set((state) => ({
    navCollapsedGroups: {
      ...state.navCollapsedGroups,
      [groupKey]: !state.navCollapsedGroups[groupKey]
    }
  })),

  // ============ 重置所有状态 ============
  reset: () => set({
    loading: false,
    uploadProgress: 0,
    error: null,
    result: null,
    resultType: null,
    activeTab: 'overview',
    navCollapsedGroups: {}
  })
}))
