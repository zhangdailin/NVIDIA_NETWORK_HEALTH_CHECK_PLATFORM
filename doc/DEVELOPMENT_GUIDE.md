# 开发和部署指南

**最后更新**: 2026-01-24
**用途**: 整合所有开发、部署、使用相关的指南

---

## 目录

1. [快速启动](#快速启动)
2. [开发模式](#开发模式)
3. [生产部署](#生产部署)
4. [Docker 部署](#docker-部署)
5. [架构迁移](#架构迁移)
6. [空间优化](#空间优化)

---

## 快速启动

### 环境要求
- Node.js >= 16
- Python >= 3.8
- npm 或 pnpm

### 安装依赖
```bash
# 统一安装所有依赖（前后端）
npm run install:all

# 或分别安装
cd frontend && npm install
cd backend && pip install -r requirements.txt
```

### 启动服务

#### 开发模式（推荐）
```bash
# 同时启动前后端开发服务器
npm run dev

# 前端: http://localhost:5173 (Vite 热重载)
# 后端: http://localhost:8000 (FastAPI 热重载)
```

#### 生产模式
```bash
# 构建前端
npm run build

# 启动生产服务器（单端口）
npm start

# 访问: http://localhost:8000
```

---

## 开发模式

### 项目结构
```
NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM/
├── frontend/           # 前端代码
│   ├── src/
│   │   ├── config/    # 配置
│   │   ├── services/  # API 服务
│   │   ├── store/     # 状态管理
│   │   ├── hooks/     # 自定义 Hooks
│   │   ├── components/# UI 组件
│   │   └── App.jsx    # 主应用
│   └── package.json
├── backend/            # 后端代码
│   ├── services/      # 业务服务
│   ├── core/          # 核心模块
│   └── main.py        # FastAPI 入口
└── doc/               # 文档
```

### 常用命令
```bash
# 开发
npm run dev              # 启动开发服务器（前后端分离）
npm run backend          # 只启动后端
npm run frontend         # 只启动前端

# 构建
npm run build            # 构建前端
npm run build:prod       # 构建并提示启动命令

# 清理
npm run clean            # 清理所有依赖和构建文件
npm run clean:build      # 只清理构建文件
```

### 添加新功能

#### 1. 添加新的分析页面
```javascript
// 1. 在 frontend/src/routes/lazyComponents.js 添加懒加载
export const MyAnalysis = lazy(() => import('../MyAnalysis'))

// 2. 在 frontend/src/constants/tabs.js 添加配置
export const TAB_ICON_MAP = {
  my_analysis: MyIcon
}

// 3. 在 App.jsx 添加路由
case 'my_analysis':
  return <MyAnalysis data={result.data.my_analysis} />
```

#### 2. 添加新的 API 服务
```python
# backend/services/my_service.py
class MyService:
    def run(self):
        # 实现业务逻辑
        return {"data": [...]}

# backend/main.py
@app.post("/api/my-endpoint")
async def my_endpoint():
    service = MyService(dataset_root)
    return service.run()
```

---

## 生产部署

### 方式1：本地部署

```bash
# 1. 构建前端
npm run build

# 2. 启动后端（自动服务前端）
npm start

# 3. 访问
# http://localhost:8000
```

### 方式2：分离部署

#### 前端（Nginx）
```bash
# 构建前端
cd frontend
npm run build

# 配置 Nginx
server {
    listen 80;
    root /path/to/frontend/dist;

    location /api {
        proxy_pass http://backend:8000;
    }
}
```

#### 后端（Uvicorn）
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 环境变量配置

创建 `backend/.env` 文件：
```bash
# 分析配置
RETURN_ONLY_ISSUES=true
MAX_PREVIEW_ROWS=2000
SERVICE_TIMEOUT_SECONDS=60

# 线缆分析配置
CABLE_TEMP_WARNING_THRESHOLD=70
CABLE_TEMP_CRITICAL_THRESHOLD=80

# 功能开关
ENABLE_TOPOLOGY_VISUALIZATION=true
ENABLE_HEALTH_SCORE=true
```

---

## Docker 部署

### 构建镜像
```bash
# 使用统一镜像
docker build -f Dockerfile.unified -t nvidia-health-check .
```

### 启动容器
```bash
# 使用 docker-compose
docker-compose -f docker-compose.unified.yml up -d

# 或直接运行
docker run -p 8000:8000 \
  -v $(pwd)/uploads:/app/uploads \
  nvidia-health-check
```

### Docker Compose 配置
```yaml
version: '3.8'
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.unified
    ports:
      - "8000:8000"
    volumes:
      - ./uploads:/app/uploads
    environment:
      - RETURN_ONLY_ISSUES=true
      - MAX_PREVIEW_ROWS=2000
```

---

## 架构迁移

### 从旧架构迁移到新架构

#### 自动迁移（推荐）
```bash
# 运行迁移脚本
node migrate.js
```

#### 手动迁移
```bash
# 1. 备份旧文件
cp frontend/src/App.jsx frontend/src/App.backup.jsx

# 2. 安装 Zustand
cd frontend && npm install zustand

# 3. 替换主文件
mv frontend/src/App.refactored.jsx frontend/src/App.jsx

# 4. 测试新架构
npm run dev
```

### 架构对比

| 特性 | 旧架构 | 新架构 |
|------|--------|--------|
| App.jsx 代码行数 | 1,370 | 200 |
| 状态管理 | useState | Zustand |
| 代码分割 | 无 | 懒加载 |
| 初始包大小 | 2.5 MB | 800 KB |
| 首屏加载 | 3.2s | 1.1s |

---

## 空间优化

### 清理策略

#### 1. 清理构建文件
```bash
npm run clean:build
# 删除: frontend/dist/
```

#### 2. 清理依赖
```bash
npm run clean
# 删除: node_modules/, frontend/node_modules/
```

#### 3. 清理缓存
```bash
npm cache clean --force
```

#### 4. 清理上传文件
```bash
# 删除旧的上传文件
find uploads -type f -mtime +30 -delete
```

### 空间占用对比

| 目录 | 优化前 | 优化后 | 减少 |
|------|--------|--------|------|
| node_modules | 190 MB (2个) | 179 MB (1个) | -6% |
| frontend/dist | N/A | 2-3 MB | - |
| 总计 | ~190 MB | ~182 MB | -4% |

### 持续优化建议

1. **使用 pnpm**：进一步节省空间（节省约 30-40%）
2. **定期清理**：设置自动清理脚本
3. **优化依赖**：移除未使用的依赖包
4. **压缩资源**：使用 gzip/brotli 压缩静态文件

---

## 故障排查

### 依赖安装失败
```bash
npm run clean
npm cache clean --force
npm install
```

### 前端构建失败
```bash
npm run clean:build
npm run build
```

### 后端无法启动
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### Docker 容器无法启动
```bash
# 查看日志
docker-compose logs -f

# 重新构建
docker-compose build --no-cache
docker-compose up -d
```

---

## 性能监控

### 前端性能
```javascript
// 使用 Web Vitals
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals'

getCLS(console.log)
getFID(console.log)
getFCP(console.log)
getLCP(console.log)
getTTFB(console.log)
```

### 后端性能
```python
# 在 main.py 添加中间件
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

---

## 相关文档

- [README.md](../README.md) - 项目主文档
- [REFACTORING_GUIDE.md](./REFACTORING_GUIDE.md) - 重构指南
- [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) - 迁移指南
- [OPTIMIZATION_HISTORY.md](./OPTIMIZATION_HISTORY.md) - 优化历史
- [BER_DOCUMENTATION.md](./BER_DOCUMENTATION.md) - BER 文档

---

**维护者**: Development Team
**支持**: 如有问题请提 Issue
