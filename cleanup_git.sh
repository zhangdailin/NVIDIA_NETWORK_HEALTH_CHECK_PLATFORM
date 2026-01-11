#!/bin/bash
# Git 仓库清理脚本

echo "开始清理 Git 仓库..."

# 1. 从 Git 历史中移除 node_modules
echo "1. 移除 node_modules 历史..."
git filter-branch --force --index-filter \
  "git rm -r --cached --ignore-unmatch node_modules" \
  --prune-empty --tag-name-filter cat -- --all

# 2. 从 Git 历史中移除 test_data
echo "2. 移除 test_data 历史..."
git filter-branch --force --index-filter \
  "git rm -r --cached --ignore-unmatch test_data" \
  --prune-empty --tag-name-filter cat -- --all

# 3. 从 Git 历史中移除 backend/.venv
echo "3. 移除 backend/.venv 历史..."
git filter-branch --force --index-filter \
  "git rm -r --cached --ignore-unmatch backend/.venv" \
  --prune-empty --tag-name-filter cat -- --all

# 4. 清理 reflog 和垃圾回收
echo "4. 清理 reflog..."
git reflog expire --expire=now --all

echo "5. 垃圾回收..."
git gc --prune=now --aggressive

echo "清理完成！"
echo "仓库大小："
du -sh .git

echo ""
echo "如果需要推送到远程仓库，请执行："
echo "git push origin --force --all"
echo "git push origin --force --tags"
