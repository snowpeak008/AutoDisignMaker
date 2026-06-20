# 执行对象存档架构设计 (Execution Object Save Architecture)

> **设计目标**：将设计工作台项目与沙盒工作区完全整合到执行对象系统中，实现最标准化的存档机制。
> **版本**：1.0.0  
> **日期**：2026-06-20

---

## 一、架构总览

### 1.1 核心设计原则

**统一存储模型**：所有持久化数据通过执行对象存储 (Execution Object Store)

**类型化对象**：不同类型的数据对应不同类型的执行对象
- `design_project` - 设计工作台项目
- `workspace_snapshot` - 沙盒工作区快照
- `user_artifact` - 用户导出制品
- `program_task` - 程序开发任务（已有）
- `art_task` - 美术制作任务（已有）
- `rollback_plan` - 回滚计划（已有）

**状态机工作流**：所有对象遵循统一的状态转换

draft → submitted → analyzing → awaiting_confirmation → approved → executing → verified

**存档范围明确**：
- 执行对象存储：`saves/{save_id}/workspace/outputs/execution_objects/execution_objects.json`
- 源包：`saves/{save_id}/workspace/sandbox/source_artifacts/`
- 制品：`saves/{save_id}/workspace/sandbox/outputs/artifacts/`
- 运行日志：`saves/{save_id}/workspace/gate_log.yaml`

---

## 二、执行对象类型定义

### 2.1 设计项目执行对象 (design_project)

**用途**：存储设计工作台的完整项目状态

**object_type**: `"design_project"`

**confirmation_level**: `"elevated_confirm"`（设计决策影响整个流水线）

**数据结构示例**：
```json
{
  "execution_object_id": "EO-000001",
  "object_type": "design_project",
  "title": "Coin Master 类游戏设计项目",
  "state": "verified",
  "created_at": "2026-06-20T10:30:00",
  "updated_at": "2026-06-20T11:45:00",
  "source_diagnostic_id": "workbench:design_project:001",
  
  "prefilled_content": {},
  "user_content": {
    "projectName": "test__001",
    "profile": {
      "businessModel": "free_to_play",
      "operationModel": "live_service"
    },
    "nodes": {},
    "domains": {}
  },
  
  "related_facts": {
    "engine_version": "DesignEngine v1.0",
    "domain_count": 17,
    "completed_nodes": 45,
    "total_entities": 128
  },
  
  "write_scope": [
    "design:project_state",
    "design:nodes",
    "design:domains"
  ],
  
  "metadata": {
    "stage": "design",
    "business_id": "design_project:test__001",
    "created_by": "design_workbench",
    "auto_save_version": 12,
    "last_manual_save": "2026-06-20T11:45:00"
  }
}
```

**状态转换规则**：
- `draft`: 设计工作台自动保存时创建
- `submitted`: 用户点击"保存"按钮
- `verified`: 保存成功，作为权威版本

---

### 2.2 沙盒工作区快照 (workspace_snapshot)

**用途**：捕获沙盒工作区 (`sandbox/workspace/`) 的文件状态

**object_type**: `"workspace_snapshot"`

**confirmation_level**: `"normal_confirm"`

**触发时机**：
- 用户手动保存设计项目
- 用户导出制品
- 步骤执行后自动快照

---

### 2.3 用户导出制品 (user_artifact)

**用途**：存储用户从设计工作台导出的内容

**object_type**: `"user_artifact"`

**confirmation_level**: `"normal_confirm"`

---

## 三、存档系统重构

### 3.1 新的存档目录结构

```
saves/{save_id}/
├── save_manifest.json              # 存档元数据
├── timeline.jsonl                  # 时间线事件
│
├── workspace/                      # 权威工作区
│   ├── sandbox/
│   │   ├── source_artifacts/       # 源包（保留）
│   │   └── outputs/
│   │       ├── artifacts/          # 制品（保留）
│   │       ├── runtime_control/    # 运行控制（保留）
│   │       └── execution_objects/  # ★ 核心：执行对象存储
│   │           └── execution_objects.json
│   │
│   └── gate_log.yaml               # 门日志（保留）
│
└── snapshots/                      # 历史快照（保留）
    └── {seq}_{event}/
        ├── snapshot_manifest.json
        ├── full/
        └── delta/
```

**关键变化**：
- ❌ 移除 `sandbox/workspace/projects/`（不再存储文件）
- ❌ 移除 `sandbox/workspace/exports/`（不再存储文件）
- ✅ 所有数据存储在 `execution_objects.json` 中
- ✅ 文件型制品仅作为执行对象的附加证据

---

### 3.2 新的 ACTIVE_DIRS 定义

```python
# core/save/manager.py

ACTIVE_DIRS = (
    "sandbox/source_artifacts",
    "sandbox/outputs",
    # 移除 sandbox/workspace，不再直接备份文件
)

EMPTY_DIRS = (
    "sandbox/source_artifacts",
    "sandbox/source_artifacts/operator_drafts",
    "sandbox/outputs",
    "sandbox/outputs/artifacts",
    "sandbox/outputs/run_logs",
    "sandbox/outputs/checkpoints",
    "sandbox/outputs/artifact_layer",
    "sandbox/outputs/runtime_control",
    "sandbox/outputs/execution_objects",  # 新增
)
```


## 四、核心模块实现

### 4.1 设计项目执行对象管理器

**文件**：`core/engines/execution_objects/design_project.py`

**核心接口**：
```python
def save_design_project(store, project_state, *, title=None, save_type="manual")
def load_latest_design_project(store)
def list_design_project_versions(store)
def restore_design_project_version(store, execution_object_id)
```

---

### 4.2 工作区快照管理器

**文件**：`core/engines/execution_objects/workspace_snapshot.py`

**核心接口**：
```python
def capture_workspace_snapshot(store, workspace_root, *, trigger_event, reason="")
def get_latest_workspace_snapshot(store)
def compare_workspace_snapshots(snapshot_a, snapshot_b)
```

---

### 4.3 执行对象类型注册表

**文件**：`core/engines/execution_objects/type_registry.py`

定义所有执行对象类型的元数据和确认级别。

---

## 五、UI层集成

### 5.1 设计工作台保存流程

**原流程**：弹出文件对话框 → 保存到文件

**新流程**：
1. 保存可见笔记
2. 加载执行对象存储
3. 创建/更新 design_project 执行对象
4. 触发存档同步
5. 显示成功消息（包含版本ID）

---

### 5.2 设计工作台加载流程

**新流程**：
1. 加载执行对象存储
2. 获取最新的已验证 design_project
3. 恢复项目状态到工作台
4. 渲染UI

---

## 六、数据迁移方案

### 6.1 迁移现有设计项目文件

脚本：`tools/scripts/migrate_design_projects_to_execution_objects.py`

迁移 `projects/*.json` 和 `sandbox/workspace/projects/*.json` 到执行对象存储。

---

### 6.2 迁移现有存档

脚本：`tools/scripts/migrate_saves_to_execution_objects.py`

为每个存档创建对应的执行对象。

---

## 七、优势总结

### 7.1 统一性
- 单一真相源：所有数据在一个 JSON 文件
- 不再有文件散落在多个目录
- 版本控制统一管理

### 7.2 可追溯性
- 完整的审计轨迹
- 每个保存都有 state_history
- 支持回滚到任意历史版本

### 7.3 类型安全
- Schema 验证
- 自动数据结构检查
- 防止数据损坏

### 7.4 工作流集成
- 状态机管理
- 支持自动保存（draft）和手动保存（verified）
- 可扩展审批流程

### 7.5 存档效率
- 减少冗余文件复制
- 执行对象存储自带版本历史
- 快照仅保留必要内容

---

## 八、实施路线图

### Phase 1: 核心模块开发（第1周）
1. 创建 design_project.py
2. 创建 workspace_snapshot.py
3. 创建 user_artifact.py
4. 创建 type_registry.py

### Phase 2: UI集成（第2周）
1. 重构 save_project()
2. 重构 open_project()
3. 添加版本历史查看器
4. 添加自动保存

### Phase 3: 存档系统重构（第3周）
1. 更新 ACTIVE_DIRS
2. 集成执行对象存储到存档流程
3. 测试存档加载和切换

### Phase 4: 数据迁移（第4周）
1. 开发迁移脚本
2. 迁移现有文件
3. 验证数据完整性

### Phase 5: 文档和测试（第5周）
1. 更新文档
2. 编写单元测试
3. 编写集成测试

---

## 九、向后兼容性

在迁移期间，系统同时支持：
- 新方式：从执行对象存储加载（优先）
- 旧方式：从文件加载（兜底）

用户可选择自动迁移或手动迁移。

---

## 十、附录

### A. 执行对象类型完整列表

| 类型 | 用途 | 确认级别 | 状态 |
|------|------|----------|------|
| design_project | 设计工作台项目 | elevated_confirm | 新增 |
| workspace_snapshot | 工作区快照 | normal_confirm | 新增 |
| user_artifact | 用户导出制品 | normal_confirm | 新增 |
| program_task | 程序开发任务 | normal_confirm | 已有 |
| art_task | 美术制作任务 | t3_art_confirm | 已有 |
| rollback_plan | 回滚计划 | destructive_confirm | 已有 |

### B. 相关文件清单

```
core/engines/execution_objects/
├── type_registry.py         # 类型注册表（新增）
├── design_project.py        # 设计项目管理器（新增）
├── workspace_snapshot.py    # 工作区快照管理器（新增）
└── user_artifact.py         # 用户制品管理器（新增）

core/save/
└── manager.py               # 存档管理器（需更新）

core/ui/
└── app_window.py            # 设计工作台（需更新）

tools/scripts/
├── migrate_design_projects_to_execution_objects.py
└── migrate_saves_to_execution_objects.py
```

---

**END OF ARCHITECTURE DOCUMENT**
