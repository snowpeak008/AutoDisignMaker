# 字段命名规范 Field Naming Convention

你在定义数据实体的字段名或接口的输入/输出字段名时，必须遵守以下规则。这份文档是命名唯一权威来源，禁止使用文档列出的任何反例。

---

## 规则 1：类型/种类字段必须带实体前缀

字段名中包含实体名的前缀，明确表示"谁的类型"。

| 反例（禁止） | 正例（必须使用） | 所属实体示例 |
|---|---|---|
| type | threat_type | ThreatInstance |
| type | module_type | ShipModule |
| type | weather_type | WorldEnvironment |
| type | container_type | InventoryContainer |
| type | skill_type | Survivor |

---

## 规则 2：引用 ItemDefinition 的 ID 字段统一用 item_def_id

| 反例（禁止） | 正例（必须使用） | 所属实体示例 |
|---|---|---|
| def_id | item_def_id | InventorySlot, ConveyorItem |
| definition_id | item_def_id | 同上 |

---

## 规则 3：进度字段必须带领域前缀

| 反例（禁止） | 正例（必须使用） | 所属实体示例 |
|---|---|---|
| progress | research_progress | TechNodeState |
| progress | production_progress | ProductionMachineStatus |
| progress_on_path | path_progress | ConveyorItem |

---

## 规则 4：等级/级别字段必须以 _level 结尾

| 反例（禁止） | 正例（必须使用） | 所属实体示例 |
|---|---|---|
| reinforcement | reinforcement_level | ShipModule |
| danger | danger_level | OceanRegion |

---

## 规则 5：生成/刷出类速率统一用 _spawn_rate

| 反例（禁止） | 正例（必须使用） | 所属实体示例 |
|---|---|---|
| iceberg_rate | iceberg_spawn_rate | OceanRegion |
| iceberg_density | iceberg_spawn_rate | OceanRegion（密度也用 _spawn_rate，值是 0~1） |
| spawn_chance | spawn_rate | 通用 |

---

## 规则 6：动态物品实例 ID 统一用 item_instance_id

适用于传送带、掉落物等动态生成的物品实例（区别于库存槽位中的静态引用）。

| 反例（禁止） | 正例（必须使用） |
|---|---|
| instance_id | item_instance_id |
| drop_id | item_instance_id |

---

## 规则 7：布尔值字段以 is_ 或 has_ 开头

| 反例（禁止） | 正例（必须使用） |
|---|---|
| structural | is_structural |
| night | is_night |
| dead | is_dead |
| traversable | is_traversable |
| underwater | is_underwater |
| food_satisfied | is_food_satisfied |
| owner_exists | has_owner |
| currents (作为"是否有洋流"的布尔值) | has_currents |

---

## 规则 8：跨实体引用字段使用具体实体名

引用其他实体时，字段名应包含目标实体名，使关系一目了然。

| 反例（禁止） | 正例（必须使用） | 说明 |
|---|---|---|
| owner_id | player_id 或 ship_id | 按实际引用对象命名 |
| target_id | target_ship_id 或 target_module_id | 明确目标类型 |
| assigned_to | assigned_module_id | 含模块语义 |

唯一例外：`owner_type` + `owner_id` 组合（多态引用模式）可以保留 `owner_id`，因为 `owner_type` 字段已表明具体类型。

---

## 规则 9：字段名统一 snake_case

禁止使用 camelCase（如 `icebergSpawnRate`）或空格分隔。

---

## 规则 10：禁止在字段名中使用缩写

| 反例（禁止） | 正例（必须使用） |
|---|---|
| amt | amount |
| qty | quantity |
| max_hp | max_health |
| cur_hp | current_health |
| def_id | item_def_id（见规则 2） |
| temp | temperature |
| pos_x | position_x |

---
*所有 agent 在产出 entities 或 interfaces 时必须对照本文档逐条检查。违反任何一条即为命名错误。*
