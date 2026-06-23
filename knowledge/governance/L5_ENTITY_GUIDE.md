# L5 实体录入规范

## 目标

L5 实体用于把 L4 设计决策落到具体游戏对象，使 Step 02 之后的程序需求和美术需求从“设计选择”升级为“可实现对象”。

## 录入位置

1. 在 DesignEngine 打开当前项目。
2. 进入需要细化的 L4 设计节点。
3. 点击“添加 L5 实体”。
4. 为每个实体填写 `label`、`kind`、`schema` 和依赖节点。

## 字段规范

| 字段 | 示例 | 说明 |
|------|------|------|
| `label` | `短剑` | 具体游戏对象名，不写抽象类别。 |
| `kind` | `weapon` | 使用 `weapon/character/enemy/ability/room/resource/ui/scene/system/config/audio`。 |
| `schema` | `weapon.v1` | 与 kind 对应的数据契约版本。 |
| `dependencies` | `weapon_design_node` | 指向产生该实体的设计节点。 |

## 最低录入范围

| 设计节点 | 最低数量 | 推荐 kind |
|----------|----------|-----------|
| `weapon_design_node` | 3 | `weapon` |
| `enemy_design_node` | 3 | `enemy` |
| `ability_design_node` | 5 | `ability` |
| `room_design_node` | 3 | `room` |
| `resource_design_node` | 2 | `resource` |

## 质量要求

- 一个实体只表达一个具体对象，例如“短剑”“骷髅弓手”“冲刺祝福”。
- 不使用“武器系统”“敌人配置”这类 L4 名称作为 L5 label。
- `purpose` 中保留 `kind=...；schema=...`，便于导出解析。
- 每个核心玩法系统至少有一个 L5 实体映射。

## 验证命令

```bash
python tools/validators/pipeline_quality.py --check plan-002
```

若真实 L5 实体数量达到 40 个以上，期望 `entity_coverage_rate >= 0.75`。
