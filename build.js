#!/usr/bin/env node

/**
 * 统一构建脚本 - 一键构建前端并集成到后端
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('🚀 开始构建 NVIDIA 网络健康检查平台...\n');

// 1. 构建前端
console.log('📦 步骤 1/3: 构建前端...');
try {
  execSync('cd frontend && npm run build', { stdio: 'inherit' });
  console.log('✅ 前端构建完成\n');
} catch (error) {
  console.error('❌ 前端构建失败');
  process.exit(1);
}

// 2. 复制前端构建产物到后端
console.log('📋 步骤 2/3: 复制前端文件到后端...');
const frontendDist = path.join(__dirname, 'frontend', 'dist');
const backendStatic = path.join(__dirname, 'backend', 'static');

try {
  // 删除旧的静态文件
  if (fs.existsSync(backendStatic)) {
    fs.rmSync(backendStatic, { recursive: true, force: true });
  }

  // 复制新的构建产物
  fs.cpSync(frontendDist, backendStatic, { recursive: true });
  console.log('✅ 文件复制完成\n');
} catch (error) {
  console.error('❌ 文件复制失败:', error.message);
  process.exit(1);
}

// 3. 验证构建
console.log('🔍 步骤 3/3: 验证构建...');
const indexPath = path.join(backendStatic, 'index.html');
if (fs.existsSync(indexPath)) {
  console.log('✅ 构建验证通过\n');
  console.log('🎉 构建完成！');
  console.log('\n📝 下一步：');
  console.log('   运行: npm run server');
  console.log('   访问: http://localhost:8000\n');
} else {
  console.error('❌ 构建验证失败：找不到 index.html');
  process.exit(1);
}
