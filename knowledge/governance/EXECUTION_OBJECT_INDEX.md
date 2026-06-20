# 执行对象存档架构 - 文档索引

> **最标准化的存档架构设计**  
> 将设计工作台项目与沙盒工作区完全整合到执行对象系统

---

## 📚 文档导航

### 🚀 快速开始
**适合**：想立即上手的开发者

📖 **[QUICKSTART.md](./QUICKSTART.md)**  
5分钟快速上手指南
- 理解新架构
- 运行数据迁移
- 测试新功能
- 验证存档集成

---

### 📐 架构设计
**适合**：想深入理解设计的架构师

📖 **[EXECUTION_OBJECT_SAVE_ARCHITECTURE.md](./EXECUTION_OBJECT_SAVE_ARCHITECTURE.md)**  
完整的架构设计文档（最核心）
- 核心设计原则
- 执行对象类型定义
- 存档系统重构方案
- 核心模块接口
- UI 层集成方案
- 数据迁移策略
- 实施路线图

📖 **[ARCHITECTURE_COMPARISON.md](./ARCHITECTURE_COMPARISON.md)**  
新旧架构对比分析
- 数据流对比
- 目录结构对比
- 操作流程对比
- 技术指标对比
- 迁移成本评估

---

### 🔧 实施指南
**适合**：准备动手实施的开发者

📖 **[UI_INTEGRATION_GUIDE.md](./UI_INTEGRATION_GUIDE.md)**  
UI 层集成详细指南
- `save_project()` 重构代码
- `open_project()` 重构代码
- 版本选择对话框实现
- 自动保存功能
- 导出功能集成
- 兼容性策略

📖 **[IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)**  
实施总结与任务清单
- 已完成工作清单
- 核心架构变更
- 关键优势
- 待实施任务（Phase 1-5）
- 风险评估
- 回滚方案

---

## 🗂️ 代码文件索引

### 核心模块
```
core/engines/execution_objects/
├── type_registry.py         ✅ 已创建 - 执行对象类型注册表
├── design_project.py        ✅ 已创建 - 设计项目管理器
├── user_artifact.py         ✅ 已创建 - 用户制品管理器
└── workspace_snapshot.py    ✅ 已创建 - 工作区快照管理器
```

### 数据迁移
```
tools/scripts/
└── migrate_design_projects_to_execution_objects.py  ✅ 已创建
```

### UI 集成
```
core/ui/
└── app_window.py           ⏳ 待修改 - 参考 UI_INTEGRATION_GUIDE.md
```

### 存档系统
```
core/save/
└── manager.py              ⏳ 待更新 - 已包含执行对象存储路径
```

---

## 📊 执行对象类型一览

| 类型 | 用途 | 确认级别 | 状态 | 管理器 |
|------|------|----------|------|--------|
| **design_project** | 设计工作台项目 | elevated_confirm | 新增 ✨ | design_project.py |
| **workspace_snapshot** | 工作区快照 | normal_confirm | 新增 ✨ | workspace_snapshot.py |
| **user_artifact** | 用户导出制品 | normal_confirm | 新增 ✨ | user_artifact.py |
| program_task | 程序开发任务 | normal_confirm | 已有 | integration.py |
| art_task | 美术制作任务 | t3_art_confirm | 已有 | integration.py |
| rollback_plan | 回滚计划 | destructive_confirm | 已有 | integration.py |
| asset_contract_change | 资产契约变更 | elevated_confirm | 已有 | - |
| reference_migration | 引用迁移 | elevated_confirm | 已有 | - |
| unity_replacement_batch | Unity批量替换 | destructive_confirm | 已有 | - |
| relationship_graph_correction | 关系图修正 | elevated_confirm | 已有 | - |

---

## 🎯 核心优势总结

### 1. 统一存储 🗄️
- **单一真相源**：所有持久化数据在一个 JSON 文件
- **不再散落**：消除 projects/, workspace/, exports/ 的文件散落
- **易于管理**：统一的查询、过滤、排序接口

### 2. 版本历史 📚
- **完整历史**：每次保存都有 state_history
- **可追溯性**：知道谁在什么时候做了什么改动
- **可回滚**：支持恢复到任意历史版本

### 3. 状态机工作流 🔄
```
draft → submitted → analyzing → awaiting_confirmation → 
approved → executing → verified
```

### 4. 类型安全 🛡️
- **Schema 验证**：保存时自动验证数据结构
- **防止损坏**：早期发现数据问题
- **类型化**：每种数据有明确的类型定义

### 5. 与流水线深度集成 🔗
- **自动备份**：随流水线存档自动备份
- **切换存档**：切换存档时自动切换设计项目
- **快照历史**：完整的时间线记录

---

## 📈 实施进度

### Phase 1: 核心模块开发 ✅ 完成
- ✅ type_registry.py
- ✅ design_project.py
- ✅ user_artifact.py
- ✅ workspace_snapshot.py

### Phase 2: 数据迁移 ✅ 完成
- ✅ 迁移脚本开发
- ⏳ 执行迁移（待运行）

### Phase 3: UI 集成 ⏳ 待开始
- ⏳ save_project() 重构
- ⏳ open_project() 重构
- ⏳ 版本选择对话框
- ⏳ 自动保存功能

### Phase 4: 存档系统集成 ⏳ 待开始
- ⏳ 更新 ACTIVE_DIRS
- ⏳ 测试存档流程

### Phase 5: 测试和优化 ⏳ 待开始
- ⏳ 端到端测试
- ⏳ 性能测试
- ⏳ 用户体验优化

---

## 🚦 下一步行动

### 立即可做
1. **运行迁移脚本**
   ```bash
   cd E:/workwork/CrewAi/AutoDesignMaker
   python tools/scripts/migrate_design_projects_to_execution_objects.py --dry-run
   python tools/scripts/migrate_design_projects_to_execution_objects.py
   ```

2. **测试核心模块**
   ```python
   from core.engines.execution_objects.design_project import *
   from core.engines.execution_objects.integration import load_execution_object_store
   from core.paths import PROJECT_ROOT
   
   store = load_execution_object_store(PROJECT_ROOT)
   versions = list_design_project_versions(store)
   print(f"找到 {len(versions)} 个设计项目版本")
   ```

3. **验证数据完整性**
   - 检查执行对象存储文件
   - 比对原文件与执行对象内容
   - 确认所有项目已迁移

### 准备工作
1. **备份数据**
   ```bash
   cp -r E:/workwork/CrewAi/AutoDesignMaker/projects E:/workwork/CrewAi/AutoDesignMaker/projects.backup
   cp -r E:/workwork/CrewAi/AutoDesignMaker/saves E:/workwork/CrewAi/AutoDesignMaker/saves.backup
   ```

2. **阅读文档**
   - 快速开始：QUICKSTART.md
   - UI 集成：UI_INTEGRATION_GUIDE.md

3. **准备测试环境**
   - 创建测试存档
   - 准备测试项目数据

---

## 💡 常见问题

### Q: 为什么选择方案C（执行对象）而不是方案A/B？

**A**: 方案C是最标准化的方案：
- **统一模型**：所有持久化数据用同一套系统
- **深度集成**：与流水线状态机完全集成
- **可扩展**：未来功能（协作、云同步）的最佳基础
- **类型安全**：Schema 验证，防止数据损坏

### Q: 会影响现有功能吗？

**A**: 不会。
- 设计采用渐进式迁移
- 保留兜底方案（从文件加载）
- 可随时回滚到旧方式

### Q: 性能如何？

**A**: 单个 JSON 文件性能足够。
- 执行对象存储是结构化 JSON
- 读写操作轻量级
- 未来可优化（分片、索引）

### Q: 如何回滚？

**A**: 三步回滚：
1. 恢复备份文件
2. 恢复 UI 代码（如已修改）
3. 重启应用

---

## 📞 支持与反馈

### 问题报告
如遇到问题，请提供：
- 错误信息和堆栈跟踪
- 操作步骤
- 相关文件（execution_objects.json）

### 改进建议
欢迎提出：
- UI 体验优化建议
- 功能增强建议
- 文档改进建议

---

## 📝 变更日志

### 2026-06-20 - 初始版本
- ✅ 完成架构设计
- ✅ 完成核心模块实现
- ✅ 完成数据迁移脚本
- ✅ 完成所有文档

---

## 📖 相关资源

### 项目文档
- `AI_README.md` - 项目总体说明
- `knowledge/ai_memory/INDEX.md` - AI 会话记忆

### 相关模块
- `core/engines/execution_objects/workflow.py` - 状态机核心
- `core/engines/execution_objects/integration.py` - 流水线集成
- `core/save/manager.py` - 存档管理器

### Schema 定义
- `knowledge/schemas/execution_object_workflow.schema.json` - 执行对象 Schema

---

**开始实施吧！** 🚀

从 [QUICKSTART.md](./QUICKSTART.md) 开始 →
