# 实体覆盖标准 v1.0.0

## 覆盖等级

- P0 partial: 至少覆盖 16 个核心节点。
- complete: 至少覆盖 39 个关键节点。
- phase2 quality: 至少覆盖 80 个节点。

## 核心 P0 节点

`action_rule_decision`、`input_control_decision`、`objective_system_decision`、
`settlement_system_decision`、`progression_system_decision`、`build_system_decision`、
`character_unit_decision`、`item_resource_content_decision`、`level_space_decision`、
`meta_structure_decision`、`content_type_decision`、`randomness_system_decision`、
`balance_model_decision`、`ux_information_architecture_decision`、
`hud_feedback_decision`、`audio_experience_decision`。

## 结构要求

- 每个实体必须包含 `kind`、`schema`、`id`、`label`。
- 每个补充实体必须包含 `supplement_basis`。
- numeric curve 至少 4 个有序采样点。
- loop 至少 3 个节点。
- encounter 至少 2 个阶段。
- system 必须包含 inputs 和 outputs。
