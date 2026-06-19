# 美术资产命名规范 Art Asset Naming Convention

你在为美术资产分配 asset_id 或文件名时，必须遵守以下规则。命名格式是合约，所有下游步骤（生产、集成）依赖它来定位和匹配资产。

---

## 命名格式

```
{AssetType}_{Subject}_{Faction}_{State}_{LOD}
```

示例：`SM_Barrel_Wrecker_Worn` — 静态模型，桶，残骸生存者阵营，磨损状态，原始精度

---

## 规则 1：资产类型前缀

| 前缀 | 适用资产 | 示例 |
|---|---|---|
| SM_ | 3D 静态模型（Static Mesh） | SM_Crane_Wrecker_Worn |
| SK_ | 3D 骨骼模型（Skeletal Mesh） | SK_Shark_Reef_Damaged |
| T_ | 纹理贴图（Texture） | T_MetalHull_Wrecker_Worn |
| M_ | 材质球（Material） | M_Wood_Driftwood |
| UI_ | UI 界面元素 | UI_HUD_HungerBar |
| VFX_ | 粒子/视觉效果 | VFX_Welding_Sparks |

---

## 规则 2：阵营/势力标识

| 标识 | 对应阵营 | 参考来源 |
|---|---|---|
| Wrecker | 残骸生存者（玩家阵营） | VisualDNA 势力区分色 |
| Raider | 深潮掠夺者 | 同上 |
| Cult | 海渊教团 | 同上 |
| Exile | 流放者商会 | 同上 |
| Precur | 旧文明（精密永恒） | 同上 |

除 Precur 外，所有阵营资产默认使用 _Worn 状态（见规则 3）。

---

## 规则 3：材质/磨损状态后缀

ArtRules 1.1 要求所有生存者阵营资产包含至少两种磨损细节。状态后缀确保这一要求在命名层面对齐。

| 后缀 | 含义 | 适用阵营 |
|---|---|---|
| _Worn | 风化/磨损（默认） | Wrecker, Raider, Cult（除旧文明外的所有阵营） |
| _Damaged | 严重损坏 | 所有阵营 |
| _Rusted | 深度锈蚀 | Wrecker, Raider |
| _Clean | 无磨损 | **仅** Precur（旧文明）可用 |
| _Bioformed | 生物寄生/融合 | Cult（海渊教团独有） |
| _Polished | 机械精密抛光 | Exile（流放者商会独有） |

---

## 规则 4：LOD 层级后缀

ArtRules 1.3 要求 LOD1 必须保留连接结构剪影和关键材质颜色，不可简化为纯色块。

| 后缀 | 层级 | 约束 |
|---|---|---|
| （无后缀） | LOD0 | 原始精度 |
| _LOD1 | 第一级简化 | 保留轮廓剪影和材质区分色 |
| _LOD2 | 第二级简化 | 不可变为纯色块 |

---

## 规则 5：禁止的命名词根

以下词根在任何资产的 asset_id 或文件名中禁止出现（对齐 VisualDNA Visual Taboos 和 ArtRules 禁止清单）：

| 禁止词根 | 原因 |
|---|---|
| _Clean（用于非 Precur 资产） | 违反绝对磨损原则（ArtRules 1.1） |
| Modern, Sleek | 视觉禁忌：高科技极简风 |
| Flat, Minimal, Helvetica, Arial | 违反 UI 材质物理性（ArtRules 3.1） |
| Holographic, Holo | 视觉禁忌：华而不实的未来科技 |
| Magic, Arcane, Ghost | 视觉禁忌：高魔奇幻元素 |
| Garden, Lawn, Park | 视觉禁忌：人造田园 |
| Marble, GlassWall, Abstract | 视觉禁忌：现代奢华建筑组件 |

---

## 规则 6：UI 资产特别规定

UI 资产遵循 ArtRules 3.1（材质物理性）和 3.2（信息朴素性）。

- UI 元素用 `UI_` 前缀
- 背景板/面板必须引用对应的世界材质纹理名（如 `UI_Panel_MetalPlate_Worn`）
- 字体说明放在规格描述中而非文件名中，但规格中禁止引用 Arial/Helvetica/Inter 等无衬线现代字体

---
*所有美术 agent（requirement_parser, illustration_spec_writer, ui_spec_writer, vfx_spec_writer, doc_assembler）在产出 asset_id 或文件名时必须对照本文档逐条检查。违反任何一条即为命名错误。*
