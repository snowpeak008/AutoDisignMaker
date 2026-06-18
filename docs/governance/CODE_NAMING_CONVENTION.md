# 代码命名规范 Code Naming Convention

你在编写 C# 代码时，必须遵守以下命名规则。类名、文件名、变量名、方法名等所有标识符均在此列。

---

## 规则 1：文件与类名必须一致

一个 `.cs` 文件只放一个顶层类/接口/结构体，文件名与类型名逐字相同。

| 类型 | 文件名 | 类名 |
|---|---|---|
| 玩家生存状态 | PlayerSurvival.cs | PlayerSurvival |
| 库存管理器 | InventoryManager.cs | InventoryManager |
| 威胁接口 | IThreat.cs | IThreat |
| 天气枚举 | WeatherType.cs | WeatherType |

**禁止**：一个文件放多个 public 类型；文件名与类名不一致（如 `player.cs` 包含 `PlayerSurvival`）。

---

## 规则 2：类型命名（类/结构体/接口/枚举/委托）

| 类型 | 规则 | 示例 |
|---|---|---|
| 类 (class) | PascalCase，名词或名词短语 | ShipBuilder, OceanPhysics, CrewMember |
| 结构体 (struct) | PascalCase，名词 | GridPosition, DamageResult |
| 接口 (interface) | 以 I 开头，PascalCase | IThreat, IDamageable, ILootProvider |
| 枚举 (enum) | PascalCase，单数名词 | WeatherType, ThreatTier, ModuleCategory |
| 枚举值 | PascalCase | Storm, Calm, AcidRain |
| 委托 (delegate) | PascalCase，以 Handler/Callback/Factory 结尾 | ThreatEventHandler, DamageCallback |
| 抽象类 (abstract) | PascalCase，以 Base 开头 | BaseShipModule, BaseThreat |

**禁止**：类名用 snake_case；接口不加 I 前缀；枚举值用 ALL_CAPS。

---

## 规则 3：方法命名

| 上下文 | 规则 | 示例 |
|---|---|---|
| 公共方法 | PascalCase，动词或动词短语 | GetThreatInRegion(), BuildModule() |
| 私有方法 | PascalCase，动词 | CalculateBuoyancy(), SpawnDebris() |
| 事件处理方法 | On + 事件名，PascalCase | OnShipDamaged(), OnModulePlaced() |
| 回调方法 | 以 On 开头 | OnInventoryChanged(), OnWeatherUpdated() |
| 布尔返回值方法 | 以 Is/Has/Can/Should 开头 | IsInDangerZone(), HasResources() |
| 异步方法 | 以 Async 结尾 | LoadShipAsync(), SaveBlueprintAsync() |

**禁止**：方法名用 snake_case；无意义的动词如 Do/Process/Handle 用于具体操作。

---

## 规则 4：字段与属性命名

| 访问级别 | 规则 | 示例 |
|---|---|---|
| public 属性 | PascalCase | CurrentHealth, MaxSpeed |
| public 字段 | PascalCase（尽量避免 public 字段） | — |
| [SerializeField] private 字段 | _camelCase | _currentHealth, _maxSpeed |
| private 字段（非序列化） | _camelCase | _cachedTransform, _threatList |
| static 字段 | s_ 前缀 + PascalCase | s_Instance, s_ActiveModules |
| const 字段 | PascalCase | MaxModuleCount, DefaultWaveHeight |

**Unity 序列化字段模板**：
```csharp
[SerializeField] private float _currentHealth;
[SerializeField] private int _maxModuleCount;
```

**禁止**：private 字段不加 `_` 前缀；public 字段用 camelCase；序列化字段用 public。

---

## 规则 5：局部变量与参数命名

| 上下文 | 规则 | 示例 |
|---|---|---|
| 局部变量 | camelCase | moduleCount, targetPosition |
| 方法参数 | camelCase | damageAmount, targetShipId |
| 循环变量 | camelCase，单字母仅限 i/j/k | i, j, loopIndex, moduleIndex |
| out 参数 | camelCase | isValid, foundModule |

---

## 规则 6：常量命名

| 上下文 | 规则 | 示例 |
|---|---|---|
| 类内 const | PascalCase | MaxHealth, DefaultGravity |
| 全局/共享常量 | PascalCase，放在 Constants 类中 | Constants.MaxModuleCount |

---

## 规则 7：命名空间命名

格式：`{Company}.{Project}.{Module}`

```
Wrecker.Survival
Wrecker.ShipBuilding
Wrecker.OceanPhysics
Wrecker.ThreatCombat
Wrecker.Inventory
```

项目根命名空间由 `PROJECT_SEMANTIC_REGISTRY.md` 定义。所有代码必须在该命名空间内。

---

## 规则 8：禁止的命名

| 禁止 | 原因 |
|---|---|
| 拼音命名 | 不是英语，不可读 |
| 单字母变量（非循环） | 无意义，如 `a`, `x`, `tmp` |
| 匈牙利命名法 | 过时，不用 `m_`, `g_`, `lpsz` |
| 缩写（通用简写除外） | 用 `GetComponent` 不用 `GetComp`，用 `health` 不用 `hp` |
| 关键字冲突名 | 不用 `@class`, `@event`，选替代词 |
| Manager/Helper/Utility 类名滥化 | 具体的管理器要有领域名，如 `ThreatManager` 而非 `Manager` |

**允许的通用简写**：Id, Hp（仅限 UI/本地化文本）, UI, VFX, IO, Json, Xml。

---

## 规则 9：文件夹命名

代码文件夹与命名空间层级对应：

```
Assets/Scripts/
├── Survival/           → Wrecker.Survival
│   ├── Player/
│   │   └── PlayerSurvival.cs
│   └── UI/
│       └── HudManager.cs
├── ShipBuilding/       → Wrecker.ShipBuilding
├── OceanPhysics/       → Wrecker.OceanPhysics
├── ThreatCombat/       → Wrecker.ThreatCombat
├── Inventory/          → Wrecker.Inventory
└── Core/               → Wrecker.Core（基础类型/工具）
```

文件夹名用 PascalCase，与命名空间段名一致。

---
*所有产出代码的 agent 必须在生成 .cs 文件时逐项对照此文档。违反任何一条即为命名错误。*
