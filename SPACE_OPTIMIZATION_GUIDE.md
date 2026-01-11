# 项目空间优化指南

## 📊 当前空间占用分析

```
总计: 1.5GB
├── .git/              819MB  (55%)  ← Git 历史记录
│   ├── node_modules 历史    ~200MB
│   ├── test_data 历史       ~4MB
│   ├── 代码历史             ~615MB
│
├── backend/.venv/     490MB  (33%)  ← Python 虚拟环境（本地）
├── node_modules/      179MB  (12%)  ← Node.js 依赖（本地）
└── 其他                12MB  (1%)
```

## 🎯 问题根源

### 1. Git 历史过大 (819MB)
- **node_modules** 被提交到了 Git 历史中
- **test_data** 测试数据被提交
- 大量的代码历史版本

### 2. 本地文件占用 (669MB)
- `backend/.venv/` - Python 虚拟环境 (490MB) ✅ 已在 .gitignore 中
- `node_modules/` - Node.js 依赖 (179MB) ✅ 已在 .gitignore 中

## 🔧 清理方案

### 方案 1：完全清理（推荐）

**适用场景**：你想要彻底清理 Git 历史，减小仓库大小

**步骤**：

1. **备份当前代码**（重要！）
   ```bash
   # 创建备份
   cd ..
   cp -r NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM_backup
   ```

2. **运行清理脚本**
   ```bash
   # Windows
   cleanup_git.bat

   # Linux/Mac
   bash cleanup_git.sh
   ```

3. **验证清理效果**
   ```bash
   du -sh .git
   # 预期：从 819MB 减少到 ~100MB
   ```

4. **推送到远程（如果需要）**
   ```bash
   git push origin --force --all
   git push origin --force --tags
   ```

**预期效果**：
- `.git/` 从 819MB 减少到 ~100MB
- 总项目大小从 1.5GB 减少到 ~800MB

### 方案 2：保守清理（安全）

**适用场景**：你不想修改 Git 历史，只想清理本地文件

**步骤**：

1. **删除 Python 虚拟环境**
   ```bash
   rm -rf backend/.venv
   ```

2. **重新创建虚拟环境**
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   pip install -r requirements.txt
   ```

**预期效果**：
- 本地文件从 1.5GB 减少到 ~1GB
- Git 历史不变

### 方案 3：重新开始（最彻底）

**适用场景**：你想要一个全新的、干净的 Git 仓库

**步骤**：

1. **备份代码**
   ```bash
   cd ..
   cp -r NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM_backup
   ```

2. **删除 .git 目录**
   ```bash
   cd NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM
   rm -rf .git
   ```

3. **重新初始化 Git**
   ```bash
   git init
   git add .
   git commit -m "Initial commit - clean repository"
   ```

4. **推送到远程**
   ```bash
   git remote add origin <your-repo-url>
   git push -u origin main --force
   ```

**预期效果**：
- `.git/` 从 819MB 减少到 ~10MB
- 总项目大小从 1.5GB 减少到 ~700MB
- ⚠️ 失去所有 Git 历史

## 📝 清理后的最佳实践

### 1. 确保 .gitignore 正确

你的 `.gitignore` 已经包含了必要的规则：

```gitignore
# Python virtual environment
venv/
.venv/
env/
.env/

# Dependencies
node_modules/

# Uploaded files
uploads/*
results/*

# Build outputs
frontend/dist/
frontend/.vite/
```

### 2. 避免提交大文件

**不应该提交的文件**：
- ❌ `node_modules/` - Node.js 依赖
- ❌ `backend/.venv/` - Python 虚拟环境
- ❌ `test_data/` - 测试数据
- ❌ `uploads/` - 上传的文件
- ❌ `frontend/dist/` - 构建输出

**应该提交的文件**：
- ✅ 源代码 (`.py`, `.js`, `.jsx`)
- ✅ 配置文件 (`package.json`, `requirements.txt`)
- ✅ 文档 (`.md`)
- ✅ 小型示例数据 (< 1MB)

### 3. 使用 Git LFS 管理大文件

如果需要在 Git 中存储大文件（如测试数据），使用 Git LFS：

```bash
# 安装 Git LFS
git lfs install

# 跟踪大文件
git lfs track "*.csv"
git lfs track "*.pdf"

# 提交 .gitattributes
git add .gitattributes
git commit -m "Add Git LFS tracking"
```

## 🚀 执行清理

### 推荐步骤（方案 1）

1. **备份代码**
   ```bash
   cd ..
   cp -r NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM_backup
   cd NVIDIA_NETWORK_HEALTH_CHECK_PLATFORM
   ```

2. **运行清理脚本**
   ```bash
   # Windows
   cleanup_git.bat

   # 或者手动执行
   git filter-branch --force --index-filter "git rm -r --cached --ignore-unmatch node_modules" --prune-empty --tag-name-filter cat -- --all
   git filter-branch --force --index-filter "git rm -r --cached --ignore-unmatch test_data" --prune-empty --tag-name-filter cat -- --all
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```

3. **验证结果**
   ```bash
   du -sh .git
   du -sh .
   ```

4. **推送到远程（可选）**
   ```bash
   git push origin --force --all
   ```

## 📊 预期清理效果

| 项目 | 清理前 | 清理后 | 节省 |
|------|--------|--------|------|
| .git/ | 819MB | ~100MB | 719MB (88%) |
| 总大小 | 1.5GB | ~800MB | 700MB (47%) |

## ⚠️ 注意事项

1. **备份重要**：清理 Git 历史是不可逆的操作，务必先备份
2. **团队协作**：如果是团队项目，需要通知所有成员重新克隆仓库
3. **远程推送**：使用 `--force` 推送会覆盖远程历史，需谨慎
4. **虚拟环境**：清理后需要重新创建 Python 虚拟环境

## 🔍 验证清理效果

```bash
# 查看 Git 仓库大小
du -sh .git

# 查看项目总大小
du -sh .

# 查看各目录大小
du -sh * .git | sort -hr

# 查看 Git 历史中的大文件
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  awk '/^blob/ {print substr($0,6)}' | \
  sort -k2 -n -r | head -20
```

## 📚 相关文档

- [Git 大文件清理官方文档](https://git-scm.com/docs/git-filter-branch)
- [Git LFS 使用指南](https://git-lfs.github.com/)
- [.gitignore 最佳实践](https://github.com/github/gitignore)

---

**创建时间**：2026-01-11
**适用版本**：v1.1.1
