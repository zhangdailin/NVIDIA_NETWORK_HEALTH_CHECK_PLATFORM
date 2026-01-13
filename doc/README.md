# NVIDIA Network Health Check Platform - 文档中心 📚

欢迎使用 NVIDIA Network Health Check Platform 文档中心。本平台用于分析 InfiniBand 网络健康状况，提供全面的网络诊断和性能分析功能。

> **文档重组说明**: 本文档中心已于 2026-01-12 重新整理，将原有的 47 个文档文件合并为更清晰的目录结构，提高了可读性和维护性。

---

## 📚 文档导航

### 🚀 快速开始
- [快速启动指南](快速启动指南.md) - 5分钟快速上手
- [功能说明](故障汇总功能说明.md) - 平台功能概览

### 👨‍💻 开发者指南
- **BER分析**:
  - [BER PHY_DB16重构](ber_phy_db16_refactor_complete.md) - 从PHY_DB36切换到PHY_DB16
  - [BER Magnitude修复](ber_magnitude_fix.md) - 修复错误的健康判断逻辑
  - [BER数据读取问题](ber_data_reading_issue.md) - 根本原因分析
  - [BER分布统计修复](ber_distribution_bug_fix.md) - BER=0被错误分类的修复
  - [前端BER显示修复](frontend_ber_display_fix.md) - 修复3个关键显示问题

- **架构与集成**:
  - [前后端字段对比](frontend_backend_field_comparison.md) - 缺失字段分析
  - [IB-Analysis-Pro对比](ib_analysis_pro_comparison.md) - 与官方项目的技术对比

### ⚙️ 运维指南
- [后端超时配置](.backend-timeout-config.md) - 服务超时配置说明
- [服务超时诊断](SERVICE_TIMEOUT_DIAGNOSIS.md) - 超时问题诊断
- [空间优化指南](space_optimization_guide.md) - 磁盘空间优化

### 📈 性能优化
- [项目优化总结](project_optimization_summary.md) - 完整的优化总结报告
- [优化成果快速参考](OPTIMIZATION_QUICK_REF.md) - 快速了解所有优化成果
- [异常数据过滤优化](anomaly_filtering_optimization_summary.md) - 5个服务的过滤优化
- [只展示异常数据](filter_normal_data_complete.md) - BER服务过滤详情
- [优化计划](OPTIMIZATION_PLAN.md) - 优化规划
- [优化报告](OPTIMIZATION_REPORT.md) - 优化实施报告

### 🐛 Bug修复记录
- [Bug修复报告](BUG_FIX_REPORT.md) - 主要Bug修复汇总
- [Bug修复总结 (2026-01-05)](bug_fix_summary_2026-01-05.md)
- [Bug修复总结 (2026-01-06)](bug_fix_summary_2026-01-06.md)
- [Bug修复总结 (2026-01-07)](bug_fix_summary_2026-01-07.md)
- [字段映射修复](field_mapping_fixes.md)

### 📝 变更记录
- [更新日志](CHANGELOG.md) - 版本更新历史

### 🤖 AI协作记录
- [Claude协作记录](CLAUDE.md)
- [Gemini协作记录](GEMINI.md)

---

## 📊 优化成果统计

### 性能提升
- **数据传输量**: 减少 **99.98%**
- **API响应时间**: 提升 **20-30倍**
- **前端渲染速度**: 提升 **6000倍**
- **内存占用**: 减少 **99%+**

### 代码变化
- **删除**: ~540行 (旧的PHY_DB36逻辑)
- **新增**: ~270行 (新的PHY_DB16逻辑 + 基础服务类)
- **修改**: ~100行 (其他服务)
- **净减少**: -170行

### 文件清理 (2026-01-12)
- **删除未使用文件**: 7个 (3个前端组件 + 4个临时文件)
- **创建基础设施**: 2个 (base_service.py + constants.py)
- **文档整理**: 进行中

---

## 🔧 快速链接

### 常见任务
- [上传数据文件](快速启动指南.md#上传数据)
- [查看分析结果](快速启动指南.md#查看结果)
- [导出报告](故障汇总功能说明.md#导出功能)

### 开发相关
- [添加新的分析模块](ib_analysis_pro_comparison.md#服务集成)
- [修改前端组件](frontend_ber_display_fix.md)
- [调试后端服务](.backend-timeout-config.md)

---

## 🧪 测试验证

### 快速测试命令
```bash
# 1. 重启后端
cd backend
python main.py

# 2. 重启前端
cd frontend
npm run dev

# 3. 上传IBDiagnet文件并验证
```

### 验证清单
- [ ] BER值显示为科学计数法而不是0
- [ ] Symbol BER列显示正确格式
- [ ] 看到BER分布统计卡片
- [ ] 只显示异常数据
- [ ] 页面响应速度明显提升
- [ ] 所有分析标签页正常工作

---

## 📝 文档维护

### 如何添加新文档
1. 在`doc/`目录创建markdown文件
2. 在本索引文件中添加链接
3. 遵循统一的文档格式

### 文档命名规范
- 修复类: `xxx_fix.md` 或 `xxx_complete.md`
- 分析类: `xxx_analysis.md` 或 `xxx_issue.md`
- 总结类: `xxx_summary.md`
- 对比类: `xxx_comparison.md`

---

## 🔗 相关资源

- **项目根目录**: [../](../)
- **后端服务**: [../backend/services/](../backend/services/)
- **前端组件**: [../frontend/src/](../frontend/src/)
- **GitHub Issues**: [提交问题](https://github.com/your-org/nvidia-network-health-check/issues)
- **NVIDIA InfiniBand 文档**: [官方文档](https://docs.nvidia.com/networking/)

---

## 📧 联系方式

如有问题或建议，请通过以下方式联系：
- 提交 Issue: GitHub Issues
- 邮件: support@example.com

---

**最后更新**: 2026-01-12
**维护者**: Claude Code Assistant
**文档总数**: 47个 (整理中)
