#!/usr/bin/env node

/**
 * 自动化架构迁移脚本
 * 一键完成从旧架构到新架构的迁移
 */

const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

console.log('🚀 开始架构迁移...\n')

const steps = [
  {
    name: '备份原文件',
    action: () => {
      const backupDir = path.join(__dirname, 'backup', new Date().toISOString().split('T')[0])
      if (!fs.existsSync(backupDir)) {
        fs.mkdirSync(backupDir, { recursive: true })
      }

      // 备份关键文件
      const filesToBackup = [
        'frontend/src/App.jsx',
        'frontend/src/App.css',
        'package.json'
      ]

      filesToBackup.forEach(file => {
        const src = path.join(__dirname, file)
        const dest = path.join(backupDir, file)
        if (fs.existsSync(src)) {
          fs.mkdirSync(path.dirname(dest), { recursive: true })
          fs.copyFileSync(src, dest)
          console.log(`  ✅ 已备份: ${file}`)
        }
      })
    }
  },
  {
    name: '安装新依赖',
    action: () => {
      console.log('  📦 安装 zustand...')
      execSync('cd frontend && npm install zustand', { stdio: 'inherit' })
    }
  },
  {
    name: '应用新架构文件',
    action: () => {
      const refactoredApp = path.join(__dirname, 'frontend/src/App.refactored.jsx')
      const targetApp = path.join(__dirname, 'frontend/src/App.jsx')

      if (fs.existsSync(refactoredApp)) {
        fs.copyFileSync(refactoredApp, targetApp)
        console.log('  ✅ 已更新 App.jsx')
      }
    }
  },
  {
    name: '验证新架构',
    action: () => {
      const requiredDirs = [
        'frontend/src/config',
        'frontend/src/services',
        'frontend/src/store',
        'frontend/src/hooks',
        'frontend/src/utils',
        'frontend/src/constants'
      ]

      const missing = requiredDirs.filter(dir => !fs.existsSync(path.join(__dirname, dir)))

      if (missing.length > 0) {
        throw new Error(`缺少目录: ${missing.join(', ')}`)
      }

      console.log('  ✅ 架构验证通过')
    }
  },
  {
    name: '重启开发服务器',
    action: () => {
      console.log('  🔄 请手动运行: npm run dev')
    }
  }
]

// 执行迁移步骤
async function migrate() {
  try {
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i]
      console.log(`\n[${i + 1}/${steps.length}] ${step.name}`)
      await step.action()
    }

    console.log('\n✅ 迁移完成！')
    console.log('\n📝 接下来：')
    console.log('  1. 运行 npm run dev 启动开发服务器')
    console.log('  2. 检查控制台是否有错误')
    console.log('  3. 查看 MIGRATION_GUIDE.md 了解更多细节')

  } catch (error) {
    console.error('\n❌ 迁移失败:', error.message)
    console.log('\n💡 请查看备份文件并手动恢复')
    process.exit(1)
  }
}

migrate()
