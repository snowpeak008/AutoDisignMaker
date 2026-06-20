# Governance Documents

本目录包含项目治理文档，定义架构决策、开发规范和最佳实践。

---

## 📂 目录结构

### 执行对象存档架构（2026-06-20 新增）

**核心文档集**：设计工作台与沙盒工作区的标准化存档架构

- **[EXECUTION_OBJECT_INDEX.md](./EXECUTION_OBJECT_INDEX.md)** - 📑 总览索引（从这里开始）
- **[QUICKSTART.md](./QUICKSTART.md)** - 🚀 5分钟快速上手
- **[EXECUTION_OBJECT_SAVE_ARCHITECTURE.md](./EXECUTION_OBJECT_SAVE_ARCHITECTURE.md)** - 📐 完整架构设计
- **[ARCHITECTURE_COMPARISON.md](./ARCHITECTURE_COMPARISON.md)** - 📊 新旧架构对比
- **[UI_INTEGRATION_GUIDE.md](./UI_INTEGRATION_GUIDE.md)** - 🔧 UI集成指南
- **[IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)** - 📝 实施总结

**推荐阅读顺序**：
1. EXECUTION_OBJECT_INDEX.md（总览）
2. QUICKSTART.md（快速上手）
3. ARCHITECTURE_COMPARISON.md（理解变化）
4. 需要实施时再读其他文档

---

### 其他治理文档

- **AI_COLLABORATION.md** - AI 协作规范
- **CODE_NAMING_CONVENTION.md** - 代码命名规范
- **DESIGN_WORKFLOW_GOVERNANCE.md** - 设计工作流治理
- **TESTING_STRATEGY.md** - 测试策略
- ... 等其他规范文档

---

## 🎯 执行对象存档架构概览

### 问题
- 设计项目文件散落在多个目录
- 与流水线存档系统分离
- 无版本历史和追溯能力

### 解决方案
将所有持久化数据统一到**执行对象存储**（Execution Object Store）：

```
设计项目 + 用户导出 + 工作区快照 → ExecutionObjectStore
                                            ↓
                            execution_objects.json
                                            ↓
                            与流水线存档完全集成
```

### 核心优势
- ✅ 统一存储：单一真相源
- ✅ 版本历史：完整可追溯
- ✅ 状态机工作流：draft → verified
- ✅ 类型安全：Schema 验证
- ✅ 深度集成：与流水线同步

### 立即开始
```bash
# 1. 阅读快速开始指南
cat knowledge/governance/QUICKSTART.md

# 2. 运行数据迁移（预览）
python tools/scripts/migrate_design_projects_to_execution_objects.py --dry-run

# 3. 正式迁移
python tools/scripts/migrate_design_projects_to_execution_objects.py
```

---

## 📚 文档维护

### 更新频率
- 架构决策文档：重大变更时更新
- 规范文档：持续维护
- 最佳实践：定期回顾

### 贡献指南
1. 新增文档：添加到对应分类
2. 更新索引：修改本 README.md
3. 保持简洁：避免冗余

---

**导航**：[返回项目根目录](../../README.md) | [AI 导读](../../AI_README.md)
