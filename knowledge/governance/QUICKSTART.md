# 快速开始：执行对象存档架构

> 5分钟快速上手指南

---

## 第一步：理解新架构

### 旧方式 ❌
```
设计工作台 → 保存按钮 → 文件对话框 → projects/test__001.json
```

### 新方式 ✅
```
设计工作台 → 保存按钮 → 执行对象存储 → execution_objects.json
                                      ↓
                              自动进入流水线存档
```

**关键变化**：
- 不再弹出文件对话框
- 不再保存到散落的 JSON 文件
- 所有数据统一存储在执行对象系统
- 自动版本历史和备份

---

## 第二步：运行数据迁移

### 方式1：预览模式（推荐先执行）

```bash
cd E:/workwork/CrewAi/AutoDesignMaker
python tools/scripts/migrate_design_projects_to_execution_objects.py --dry-run
```

**输出示例**：
```
🔍 预览模式（不会实际迁移）

找到 1 个项目文件:
  • E:\workwork\CrewAi\AutoDesignMaker\projects\test__001.json (test__001)
```

### 方式2：正式迁移（保留备份）

```bash
python tools/scripts/migrate_design_projects_to_execution_objects.py
```

**输出示例**：
```
==================================================================
设计项目迁移到执行对象存储
==================================================================

📦 加载执行对象存储...
✅ 存储路径: E:\...\saves\save_xxx\workspace\outputs\execution_objects\execution_objects.json

🔍 扫描设计项目文件...
✅ 找到 1 个项目文件

🚀 开始迁移...

  📄 迁移: test__001.json (test__001)
    💾 备份: test__001.json.bak
    ✅ 已创建执行对象: EO-000001
    📊 状态: verified

==================================================================
迁移完成
==================================================================
✅ 成功: 1 个项目
❌ 失败: 0 个项目

已迁移的项目:
  • test__001 → EO-000001
```

### 迁移完成后

**检查备份**：
```bash
ls -lh E:/workwork/CrewAi/AutoDesignMaker/projects/
# 应该看到 test__001.json.bak
```

**验证迁移**：
```python
from core.engines.execution_objects.integration import load_execution_object_store
from core.engines.execution_objects.design_project import list_design_project_versions
from core.paths import PROJECT_ROOT

store = load_execution_object_store(PROJECT_ROOT)
versions = list_design_project_versions(store)

for v in versions:
    print(f"ID: {v['execution_object_id']}")
    print(f"项目: {v['user_content']['projectName']}")
    print(f"状态: {v['state']}")
    print(f"更新时间: {v['updated_at']}")
```

---

## 第三步：测试新的保存/加载

### 测试方式1：Python 脚本测试

创建 `test_execution_object_save.py`：

```python
#!/usr/bin/env python3
"""测试执行对象存档功能"""

from core.paths import PROJECT_ROOT
from core.engines.execution_objects.integration import load_execution_object_store
from core.engines.execution_objects.design_project import (
    save_design_project,
    load_latest_design_project,
    list_design_project_versions,
)

# 1. 加载存储
print("📦 加载执行对象存储...")
store = load_execution_object_store(PROJECT_ROOT)
print(f"✅ 存储路径: {store.path}")

# 2. 创建测试项目
print("\n🚀 创建测试项目...")
test_project = {
    "projectName": "测试项目_001",
    "profile": {
        "businessModel": "free_to_play",
        "operationModel": "live_service",
    },
    "nodes": {},
    "domains": {},
}

execution_obj = save_design_project(
    store,
    test_project,
    title="测试保存功能",
    save_type="manual"
)

print(f"✅ 已创建: {execution_obj['execution_object_id']}")
print(f"📊 状态: {execution_obj['state']}")

# 3. 加载最新项目
print("\n📂 加载最新项目...")
latest = load_latest_design_project(store)
if latest:
    print(f"✅ 已加载: {latest['projectName']}")
else:
    print("❌ 没有找到项目")

# 4. 列出所有版本
print("\n📋 所有版本:")
versions = list_design_project_versions(store)
for v in versions:
    project_name = v['user_content']['projectName']
    print(f"  • {v['execution_object_id']} | {project_name} | {v['updated_at'][:19]}")

print("\n✅ 测试完成！")
```

运行测试：
```bash
python test_execution_object_save.py
```

### 测试方式2：交互式 Python

```python
python
>>> from core.paths import PROJECT_ROOT
>>> from core.engines.execution_objects.integration import load_execution_object_store
>>> from core.engines.execution_objects.design_project import *

# 加载存储
>>> store = load_execution_object_store(PROJECT_ROOT)

# 列出现有项目
>>> versions = list_design_project_versions(store)
>>> for v in versions:
...     print(v['execution_object_id'], v['user_content']['projectName'])

# 加载最新项目
>>> latest = load_latest_design_project(store)
>>> latest['projectName']
'test__001'

# 保存新版本
>>> latest['projectName'] = 'test__002'
>>> obj = save_design_project(store, latest, save_type="manual")
>>> obj['execution_object_id']
'EO-000002'
```

---

## 第四步：UI 集成（可选）

如果你想立即体验新的 UI，可以手动修改 `core/ui/app_window.py`。

### 最小修改（仅保存功能）

在 `app_window.py` 中找到 `save_project` 方法（约1813行），替换为：

```python
def save_project(self):
    """保存设计项目到执行对象存储"""
    from core.engines.execution_objects.design_project import save_design_project
    from core.engines.execution_objects.integration import load_execution_object_store
    
    self.save_visible_notes()
    
    try:
        store = load_execution_object_store(self.project_root)
        execution_obj = save_design_project(
            store,
            self.project_state,
            title=f"设计项目: {self.project_name.get()}",
            save_type="manual"
        )
        
        self.status_text.set(f"已保存: {execution_obj['execution_object_id']}")
        messagebox.showinfo("保存成功", f"版本ID: {execution_obj['execution_object_id']}")
        
    except Exception as error:
        messagebox.showerror("保存失败", f"{error}")
        import traceback
        traceback.print_exc()
```

**测试**：
1. 启动设计工作台：`python gui_app.py`
2. 修改项目内容
3. 点击"保存"按钮
4. 应该看到弹出"保存成功"对话框，显示版本ID

---

## 第五步：验证存档集成

### 检查执行对象存储文件

```bash
# 找到当前存档ID
cat E:/workwork/CrewAi/AutoDesignMaker/saves/save_index.json | grep "current_save_id"

# 查看执行对象存储
cat "E:/workwork/CrewAi/AutoDesignMaker/saves/{save_id}/workspace/outputs/execution_objects/execution_objects.json"
```

**应该看到**：
```json
{
  "schema_version": 1,
  "save_id": "save_20260620_...",
  "generated_at": "2026-06-20T...",
  "updated_at": "2026-06-20T...",
  "objects": [
    {
      "execution_object_id": "EO-000001",
      "object_type": "design_project",
      "title": "设计项目: test__001",
      "state": "verified",
      ...
    }
  ]
}
```

### 验证存档同步

```python
from core.save import manager
from core.paths import PROJECT_ROOT

# 触发存档同步
manager.sync_current_save(
    PROJECT_ROOT,
    event="test_sync",
    message="测试执行对象存档"
)

# 检查快照
save_id = manager.current_save_id(PROJECT_ROOT)
snapshots_dir = PROJECT_ROOT / "saves" / save_id / "snapshots"
print(f"快照目录: {snapshots_dir}")
print(f"快照数量: {len(list(snapshots_dir.iterdir()))}")
```

---

## 常见问题

### Q1: 迁移后原文件还能用吗？

**A**: 可以！系统保留了兜底方案。

- 新方式：优先从执行对象存储加载
- 旧方式：如果执行对象不存在，仍可从文件加载
- 备份文件：迁移时自动创建 `.bak` 备份

### Q2: 如何回滚到旧方式？

**A**: 三步回滚：

```bash
# 1. 恢复备份
cd E:/workwork/CrewAi/AutoDesignMaker/projects
cp test__001.json.bak test__001.json

# 2. 恢复 UI 代码（如果已修改）
git checkout core/ui/app_window.py

# 3. 重启应用
python gui_app.py
```

### Q3: 执行对象存储在哪里？

**A**: 
```
saves/{save_id}/workspace/outputs/execution_objects/execution_objects.json
```

这个文件会随存档自动备份和恢复。

### Q4: 自动保存会影响性能吗？

**A**: 不会。

- 自动保存仅创建 `draft` 状态对象
- 不触发存档同步
- 轻量级操作，不影响 UI 响应

### Q5: 如何查看历史版本？

**A**: 
```python
from core.engines.execution_objects.design_project import list_design_project_versions
from core.engines.execution_objects.integration import load_execution_object_store
from core.paths import PROJECT_ROOT

store = load_execution_object_store(PROJECT_ROOT)
versions = list_design_project_versions(store)

for v in versions:
    print(f"{v['execution_object_id']} | {v['updated_at']} | {v['state']}")
```

---

## 下一步

✅ **完成迁移后**，你可以：

1. **继续使用设计工作台**：保存/加载功能已升级
2. **查看版本历史**：通过 Python 脚本或未来的 UI
3. **体验自动备份**：每次存档同步都会备份设计项目
4. **完整 UI 集成**：参考 `UI_INTEGRATION_GUIDE.md` 实现完整功能

---

## 相关文档

- 📖 完整架构设计：`knowledge/governance/EXECUTION_OBJECT_SAVE_ARCHITECTURE.md`
- 🔧 UI 集成指南：`knowledge/governance/UI_INTEGRATION_GUIDE.md`
- 📝 实施总结：`knowledge/governance/IMPLEMENTATION_SUMMARY.md`
- 🛠️ 迁移脚本：`tools/scripts/migrate_design_projects_to_execution_objects.py`

---

**祝使用愉快！** 🎉
