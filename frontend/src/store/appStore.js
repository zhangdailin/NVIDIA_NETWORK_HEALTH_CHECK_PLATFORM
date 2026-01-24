/**
 * 全局状态管理 - Zustand Store
 * 集中管理应用状态，避免prop drilling
 */

import { create } from 'zustand'

export const useAppStore = create((set) => ({
  // ========== Upload State ==========
  loading: false,
  uploadProgress: 0,
  error: null,
  result: null,

  setLoading: (loading) => set({ loading }),
  setUploadProgress: (progress) => set({ uploadProgress: progress }),
  setError: (error) => set({ error }),
  setResult: (result) => set({ result }),
  clearError: () => set({ error: null }),

  // ========== Navigation State ==========
  activeTab: 'overview',
  navCollapsedGroups: {},

  setActiveTab: (tab) => set({ activeTab: tab }),
  toggleNavGroup: (groupKey) => set((state) => ({
    navCollapsedGroups: {
      ...state.navCollapsedGroups,
      [groupKey]: !state.navCollapsedGroups[groupKey],
    },
  })),

  // ========== Reset Functions ==========
  resetUploadState: () => set({
    loading: false,
    uploadProgress: 0,
    error: null,
    result: null,
  }),

  resetAll: () => set({
    loading: false,
    uploadProgress: 0,
    error: null,
    result: null,
    activeTab: 'overview',
    navCollapsedGroups: {},
  }),
}))
