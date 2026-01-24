# 架构重构指南

## 🎯 重构目标

将原本1370行的庞大App.jsx拆分为模块化、可维护的架构。

## 📁 新的文件结构

```
frontend/src/
├── config/              # 配置管理
│   └── index.js        # 统一配置（API、业务、UI）
├── services/            # API服务层
│   └── api.js          # 统一的API客户端
├── store/               # 状态管理
│   └── appStore.js     # Zustand全局状态
├── hooks/               # 自定义Hooks
│   └── useFileUpload.js # 文件上传逻辑
├── utils/               # 工具函数
│   └── dataProcessing.js # 数据处理函数
├── constants/           # 常量定义
│   └── tabs.js         # Tab配置
└── components/          # UI组件
    └── ModernOverview.jsx
```

## ✅ 已完成的优化

### 1. **配置管理** (`config/index.js`)
- ✅ 集中管理API配置
- ✅ 文件上传限制配置
- ✅ 业务配置常量
- ✅ UI主题配置

### 2. **API服务层** (`services/api.js`)
- ✅ 统一的axios实例
- ✅ 请求/响应拦截器
- ✅ 错误格式化
- ✅ 文件验证函数
- ✅ `uploadIbdiagnetFile()` - 上传IBDiagnet文件
- ✅ `uploadCsvFile()` - 上传CSV文件
- ✅ `validateFile()` - 文件验证

### 3. **状态管理** (`store/appStore.js`)
- ✅ Zustand轻量级状态管理
- ✅ 上传状态（loading, progress, error, result）
- ✅ 导航状态（activeTab, navCollapsedGroups）
- ✅ 重置函数

### 4. **自定义Hooks** (`hooks/useFileUpload.js`)
- ✅ `useFileUpload()` - 封装上传逻辑
- ✅ `uploadIbdiagnet()` - 上传IBDiagnet
- ✅ `uploadCsv()` - 上传CSV
- ✅ 与store集成，自动管理状态

### 5. **工具函数** (`utils/dataProcessing.js`)
- ✅ `extractHostLabel()` - 提取主机标签
- ✅ `buildFrequentRebootHosts()` - 构建重启主机列表
- ✅ `buildActionPlan()` - 构建推荐操作
- ✅ `getScoreColor()` - 健康度颜色
- ✅ `getStatusColor()` - 状态颜色

### 6. **常量定义** (`constants/tabs.js`)
- ✅ `TAB_ICON_MAP` - Tab图标映射
- ✅ `TAB_GROUPS` - Tab分组
- ✅ `TAB_LIST` - Tab列表
- ✅ `resolveTabMeta()` - 解析Tab元数据

## 🔄 下一步：重构App.jsx

原来的App.jsx：
```jsx
// ❌ 问题：1370行，33个导入，所有逻辑混在一起
import { useState } from 'react'
import axios from 'axios'
// ... 30+ imports

function App() {
  const [loading, setLoading] = useState(false)
  // ... 大量useState

  const handleUpload = async (file) => {
    // ... 直接在组件中处理上传
  }

  // ... 1370行代码
}
```

重构后的App.jsx：
```jsx
// ✅ 优化：清晰、模块化、易维护
import { useAppStore } from './store/appStore'
import { useFileUpload } from './hooks/useFileUpload'
import UploadPanel from './components/UploadPanel'
import NavigationPanel from './components/NavigationPanel'
import ContentArea from './components/ContentArea'

function App() {
  const { loading, error, result, activeTab } = useAppStore()
  const { uploadIbdiagnet, uploadCsv } = useFileUpload()

  return (
    <div className="container">
      <Header />
      <div className="main">
        <UploadPanel onUpload={uploadIbdiagnet} />
        <NavigationPanel />
        <ContentArea data={result} tab={activeTab} />
      </div>
      {loading && <LoadingOverlay />}
    </div>
  )
}
```

## 📊 优化效果

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| App.jsx行数 | 1,370 | ~200 | ⬇️ 85% |
| 直接导入组件 | 33个 | ~5个 | ⬇️ 85% |
| useState数量 | 10+ | 0 | ✅ 全部迁移到store |
| API调用位置 | 分散在组件 | 集中在services | ✅ 统一管理 |
| 配置分散度 | 多处硬编码 | 1个配置文件 | ✅ 集中配置 |

## 🚀 使用示例

### 在组件中使用新架构：

```jsx
import { useAppStore } from '@/store/appStore'
import { useFileUpload } from '@/hooks/useFileUpload'
import { API_CONFIG } from '@/config'

function MyComponent() {
  // 获取状态
  const { loading, error, result } = useAppStore()

  // 使用上传hook
  const { uploadIbdiagnet } = useFileUpload()

  // 使用配置
  console.log('Max file size:', API_CONFIG.MAX_FILE_SIZE)

  return (
    <div>
      {loading && <Spinner />}
      {error && <ErrorAlert message={error} />}
      <input type="file" onChange={(e) => uploadIbdiagnet(e.target.files[0])} />
    </div>
  )
}
```

## 🎉 优势

✅ **可维护性** - 模块化，职责明确
✅ **可测试性** - 纯函数易于单元测试
✅ **可扩展性** - 新增功能不影响现有代码
✅ **性能** - 懒加载、代码分割
✅ **开发体验** - 清晰的结构，易于理解

## 📝 迁移计划

- [x] 创建配置管理
- [x] 创建API服务层
- [x] 创建状态管理
- [x] 创建自定义Hooks
- [x] 提取工具函数
- [x] 提取常量定义
- [ ] 重构App.jsx（拆分为小组件）
- [ ] 实现路由懒加载
- [ ] 添加TypeScript类型定义
- [ ] 后端引入依赖注入
