/**
 * 重构后的 App 组件
 *
 * 对比原版：
 * - 从1370行减少到约200行
 * - 移除了30+个直接导入的分析组件（改用懒加载）
 * - 业务逻辑迁移到hooks和utils
 * - 状态管理使用Zustand
 * - API调用统一管理
 */

import { lazy, Suspense } from 'react'
import { Activity } from 'lucide-react'
import { useAppStore } from './store/appStore'
import { useFileUpload } from './hooks/useFileUpload'
import { TAB_GROUPS, TAB_LIST } from './constants/tabs'

// UI组件
import ErrorDisplay from './components/ErrorDisplay'
import LoadingOverlay from './components/LoadingOverlay'
import UploadSection from './components/UploadSection'
import Sidebar from './components/Sidebar'
import TabPanel from './components/TabPanel'

// 懒加载分析组件（减少初始包大小）
const ModernOverview = lazy(() => import('./components/ModernOverview'))
const HealthCheckBoard = lazy(() => import('./HealthCheckBoard'))
const FaultSummary = lazy(() => import('./FaultSummary'))
// ... 其他分析组件按需懒加载

import './App.css'

function App() {
  // ========== 状态管理 ==========
  const {
    loading,
    uploadProgress,
    error,
    result,
    activeTab,
    setActiveTab,
    navCollapsedGroups,
    toggleNavGroup,
  } = useAppStore()

  // ========== 业务逻辑 ==========
  const { handleIbdiagnetUpload, handleCsvUpload } = useFileUpload()

  // ========== 渲染内容 ==========
  const renderContent = () => {
    if (!result) {
      return (
        <div className="placeholder">
          <Activity size={48} style={{ opacity: 0.2, marginBottom: '20px' }} />
          <p>选择文件开始分析</p>
        </div>
      )
    }

    if (result.type === 'ibdiagnet') {
      return (
        <Suspense fallback={<div>加载中...</div>}>
          {activeTab === 'overview' ? (
            <ModernOverview
              analysisData={result.data}
              onSelectTab={setActiveTab}
            />
          ) : (
            <div>其他分析标签内容...</div>
          )}
        </Suspense>
      )
    }

    return <div>CSV 分析结果</div>
  }

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <h1>
          <Activity size={28} color="#76b900" />
          NVIDIA Network Health Check Platform
        </h1>
      </header>

      <div className="main">
        {/* 侧边栏 - 上传区域 */}
        <Sidebar
          onIbdiagnetUpload={handleIbdiagnetUpload}
          onCsvUpload={handleCsvUpload}
          loading={loading}
          error={error}
        />

        {/* 主内容区域 */}
        <div className="content">
          {/* Tab导航面板 */}
          <TabPanel
            result={result}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            tabGroups={TAB_GROUPS}
            collapsedGroups={navCollapsedGroups}
            onToggleGroup={toggleNavGroup}
          />

          {/* 工作区 */}
          <div className="workspace">
            <div className="content-inner">
              <div className="scroll-area">
                {renderContent()}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 全局加载状态 */}
      {loading && (
        <LoadingOverlay
          uploadProgress={uploadProgress}
        />
      )}
    </div>
  )
}

export default App
