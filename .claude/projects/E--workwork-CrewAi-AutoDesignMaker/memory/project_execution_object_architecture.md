---
name: execution-object-architecture-implementation
description: 执行对象存档架构实施记录，包括核心问题发现和解决方案
metadata:
  type: project
---

# 执行对象存档架构实施 (2026-06-20)

## 发现的核心问题

用户提出了深刻的质疑：

> "权威存档优先，为什么保存会指向 sandbox？难道你会允许 sandbox 向权威状态的存档进行覆盖？"

这揭示了旧架构的根本缺陷：

**旧架构问题**：
- `save_project()` 只保存到 `sandbox/workspace/projects/`（易失）
- 没有调用 `sync_current_save()`（不立即持久化）
- 依赖流水线步骤触发 sync（可能丢失数据）
- 用户以为已保存，实际上没有持久化到权威位置

**Why: 架构设计缺陷**
- "权威"存档的真实含义是"持久化的、可靠的"，不是"不可覆盖的"
- 类似 Git：工作区修改后 commit 覆盖仓库
- 但设计工作台的保存没有自动 commit，导致数据风险

**How to apply: 实施方案B**
- 改为直接使用执行对象存储
- 保存路径：`saves/{save_id}/workspace/outputs/execution_objects/execution_objects.json`
- 立即持久化，不依赖 sync
- 原子性操作，不会丢失数据

## 两套文件系统的明确分离

**系统1：用户导出文件（外部分享）**
- 用途：分享、归档、文档化
- 默认路径：`Documents/`（用户完全控制）
- 存档管理：❌ 不参与存档系统
- 流水线：❌ 不参与流水线

**系统2：项目工作文件（内部协作）**
- 用途：设计迭代、流水线输入
- 固定路径：`saves/{save_id}/workspace/outputs/execution_objects/`
- 存档管理：✅ 完整备份
- 流水线：✅ 参与流水线

**Why: 职责分离**
- 用户导出是外部分享，应该独立于项目存档
- 项目工作文件是内部协作，需要版本管理和备份

## sandbox 与存档功能的关系验证

经过深度审查，确认架构完全正确：

**关键发现**：
- 流水线数据：`saves/.../sandbox/outputs/`（通过 sync 同步）
- 执行对象：`saves/.../outputs/execution_objects/`（直接写入）
- 路径不同，不会冲突

**混合架构合理性**：
- 设计项目：用户数据，需要立即持久化
- 流水线：批处理数据，可以批量同步
- 使用场景不同，架构合理

**Why: 两种数据特性不同**
- 用户数据（设计项目）：交互式、高频、需要立即保存
- 批处理数据（流水线）：非交互、低频、可以批量同步

**How to apply: 维护混合架构**
- 不需要统一为单一架构
- 继续保持设计项目直接持久化
- 继续保持流水线批量同步

## 修改的文件清单

**核心模块**：
1. `core/design/data_loader.py` - 修复路径返回
2. `core/save/manager.py` - 调整存档范围
3. `core/ui/app_window.py` - 重构保存/打开/导出逻辑

**新增模块**（4个）：
- `core/engines/execution_objects/type_registry.py`
- `core/engines/execution_objects/design_project.py`
- `core/engines/execution_objects/user_artifact.py`
- `core/engines/execution_objects/workspace_snapshot.py`

**新增文档**（8个）：
- 完整的执行对象存档架构设计
- 实施指南、快速开始、对比分析等

## 相关记忆

与 [[存档系统设计]] 和 [[设计工作台架构]] 相关。
