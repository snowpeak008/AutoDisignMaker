# Step 01 — 玩法框架 实施指南

## 现状评估

| 指标 | 当前值 | 目标 |
|------|--------|------|
| core_loop source_kind | template_fallback | explicit（有显式循环时）|
| 显式系统名称 | 含 "system_layer：" 前缀 | 规范名称 |
| 品类覆盖 | roguelike/fps/puzzle/generic | +strategy/rpg |
| system_count | 7 | 3-8 |
| _load_templates 调用次数 | 2次/调用 | 1次（BUG-008 修复）|

---

## 核心类说明

### `LoopExtractor.extract()`

**职责**: 提取核心游戏循环节点列表。

**优先级**:
1. 用户显式输入（`item_type = "核心循环"`）→ source_kind = "explicit"
2. 品类模板 → source_kind = "template_fallback"
3. 硬编码通用循环 → source_kind = "template_fallback"

**BUG-008 修复**（_load_templates 双重调用）:
```python
def extract(self, parsed: dict) -> dict:
    templates = _load_templates()                                    # 只读一次
    template_key = _pick_template_key(...)
    template = templates.get(template_key) or templates.get("generic", {})
    ...
```

---

### `SystemDeducer.deduce()`

**职责**: 从系统图和品类模板合并推导系统列表，上限 8 个。

**系统名称规范化**（修复 "system_layer：" 前缀问题）:
```python
def _systems_from_graph(self, system_graph: dict) -> list[dict]:
    for node in system_graph.get("nodes", []):
        name = _text(node.get("name"))
        # 清理导出格式前缀
        for prefix in ("system_layer：", "system_layer:", "system：", "system:"):
            if name.lower().startswith(prefix.lower()):
                name = name[len(prefix):].strip()
                break
```

---

## genre_templates.json 完整结构（目标状态）

```json
{
  "roguelike_action": {
    "core_loop": ["进入房间", "战斗清场", "选择奖励", "升级构筑", "挑战首领", "死亡后永久成长"],
    "systems": [
      {"id": "SYS-COMBAT", "name": "即时战斗系统", "responsibility": "处理攻击受击移动与战斗反馈"},
      {"id": "SYS-ROOM",   "name": "房间推进系统", "responsibility": "组织房间节点遭遇出口和选择"},
      {"id": "SYS-REWARD", "name": "奖励选择系统", "responsibility": "清场后提供祝福资源成长奖励"},
      {"id": "SYS-BUILD",  "name": "构筑成长系统", "responsibility": "累计武器技能祝福和被动组合效果"},
      {"id": "SYS-META",   "name": "局外成长系统", "responsibility": "失败后沉淀永久资源解锁和叙事进度"},
      {"id": "SYS-BOSS",   "name": "首领挑战系统", "responsibility": "阶段性高压战斗和关卡进度检查"}
    ]
  },
  "fps": {
    "core_loop": ["发现目标", "移动占位", "射击消灭", "占领区域", "获取装备"],
    "systems": [
      {"id": "SYS-SHOOTING",  "name": "射击系统",   "responsibility": "射线检测命中伤害与后坐力反馈"},
      {"id": "SYS-MOVEMENT",  "name": "移动系统",   "responsibility": "玩家移动跳跃和视角控制"},
      {"id": "SYS-INVENTORY", "name": "武器背包系统","responsibility": "武器持有切换弹药和后勤管理"},
      {"id": "SYS-OBJECTIVE", "name": "目标系统",   "responsibility": "回合目标胜负判定和进度追踪"},
      {"id": "SYS-SPAWN",     "name": "生成系统",   "responsibility": "玩家和AI的重生位置与波次管理"}
    ]
  },
  "puzzle": {
    "core_loop": ["观察局面", "尝试操作", "获得反馈", "解锁下一关"],
    "systems": [
      {"id": "SYS-PUZZLE",    "name": "谜题系统",   "responsibility": "关卡规则状态变换与解法验证"},
      {"id": "SYS-HINT",      "name": "提示系统",   "responsibility": "渐进式提示引导和失败辅助"},
      {"id": "SYS-PROGRESS",  "name": "进度系统",   "responsibility": "关卡解锁星级评定和重玩管理"},
      {"id": "SYS-UI",        "name": "游戏界面",   "responsibility": "谜题展示计时器和操作反馈"}
    ]
  },
  "strategy": {
    "core_loop": ["规划部署", "执行操作", "观察结果", "调整策略", "争夺胜利"],
    "systems": [
      {"id": "SYS-UNIT",    "name": "单位系统",   "responsibility": "单位属性行为和生产管理"},
      {"id": "SYS-MAP",     "name": "地图系统",   "responsibility": "地形资源区域控制和视野管理"},
      {"id": "SYS-ECONOMY", "name": "经济系统",   "responsibility": "资源采集消耗和科技发展"},
      {"id": "SYS-AI",      "name": "AI系统",     "responsibility": "敌方AI决策行为和难度调整"},
      {"id": "SYS-COMBAT",  "name": "战斗解算",   "responsibility": "战斗碰撞伤害计算和结果判定"}
    ]
  },
  "generic": {
    "core_loop": ["理解目标", "执行核心动作", "获得反馈", "推进下一目标"],
    "systems": [
      {"id": "SYS-CORE",      "name": "核心玩法系统","responsibility": "游戏核心机制和主要交互"},
      {"id": "SYS-PROGRESS",  "name": "进度系统",   "responsibility": "目标达成进度追踪和解锁"},
      {"id": "SYS-UI",        "name": "界面系统",   "responsibility": "玩家信息展示和操作反馈"}
    ]
  }
}
```

---

## 实施检查清单

- [ ] 修复 BUG-008：`_load_templates()` 每次调用只读一次磁盘
- [ ] 修复系统名称规范化（清理 "system_layer：" 前缀）
- [ ] 在 `genre_templates.json` 中添加 strategy 和 rpg 品类
- [ ] 验证 Hades 存档 Step 01 system_definitions.json 中系统名均规范
- [ ] 单元测试：`test_system_name_cleaned_of_prefix`
