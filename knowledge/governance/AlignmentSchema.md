# AlignmentSchema — 程序·美术资产接口宪法

版本: 3.0 | 协议版本: 2.1

本文件只允许人类修改，任何AI Agent禁止写入。

```yaml
schema_version: "3.0"
contract_version: "2.1"
description: >
  定义所有程序-美术资产的类型系统、状态机、驻留策略、
  变体解析、哈希治理、确定性生成、弃用规则、迁移规则等。
  所有资产对齐组 (Asset Alignment Crew) 必须严格依此执行。

common_required_fields:
  - uid
  - type
  - state
  - stability_level

common_optional_fields:
  - deprecated
  - deprecated_reason
  - replacement_asset_uid
  - generation_params
  - semantic_profiles
  - capabilities

asset_state:
  states:
    - draft
    - generated
    - reviewed
    - approved
    - integrated
    - deprecated
    - archived
  default: draft
  description: >
    资产在流水线中的生命周期。只有状态为 approved 或 integrated
    的资产才能被程序/美术制作团队正式使用。

asset_types:
  animation:
    required_fields: [frames, fps, loop, format]
    optional_fields: [size, pivot, streaming_hint]
    default_values:
      fps: 24
      format: png
      streaming_hint: on_demand
    naming_rule: "{uid}_{frame:04d}.png"

  ui_sprite:
    required_fields: [size, nine_slice, alpha]
    optional_fields: [pivot, scale_to, dynamic_text]
    default_values:
      nine_slice: false
      alpha: true
    naming_rule: "ui_{uid}.png"

  vfx_texture:
    required_fields: [size, format, sequence_length]
    default_values:
      format: png
    naming_rule: "vfx_{uid}_{frame:03d}.png"

asset_residency:
  modes: [resident, streamed, preload_scene, on_demand, transient]
  default: on_demand
  per_mode_defaults:
    resident:
      preload_priority: high
      unload_policy: never
    streamed:
      preload_priority: medium
      unload_policy: distance
    preload_scene:
      unload_policy: scene_exit

variant_resolution:
  priority_order: [event_skin, region, quality_level, platform, default]
  fallback_policy:
    missing_variant: use_parent
    missing_texture: use_placeholder
  supported_variant_dimensions:
    - event_skin
    - region
    - quality_level
    - platform

stability_levels:
  frozen:
    description: "完全锁定，任何字段变更（含 hash）必须人工审批"
    allow_auto_regeneration: false
    allow_hot_update: false
  stable:
    description: "接口不变，内容允许优化"
    allow_auto_regeneration: true
    allow_hot_update: true
  experimental:
    description: "允许自由修改"
    allow_auto_regeneration: true
    allow_hot_update: true

runtime_failure_policy:
  missing_asset:
    action: use_placeholder
  failed_streaming:
    action: retry_3_then_placeholder
  corrupted_asset:
    action: disable_feature
  timeout:
    action: use_low_quality_variant

asset_authority:
  source_of_truth_order: [alignment_protocol, runtime_override, hotfix_patch, dlc_package]
  override_priority:
    - hotfix_patch
    - dlc_package
    - runtime_override
    - alignment_protocol

hash_governance:
  hash_algorithm: sha256
  tracked_fields: [frames, format, size, naming_pattern, stability_level, state]
  mutation_policy:
    on_hash_change: require_human_review
  generation_reproducibility:
    required_fields:
      - seed
      - model_version
      - sampler
      - steps
      - cfg_scale
    deterministic_required_for: [frozen, stable]

deprecation_policy:
  deprecated_asset:
    allow_runtime_loading: false
    allow_reference: false
    retention_days: 180

runtime_binding:
  supported_bindings: [unity_addressable, unreal_soft_ref, custom_bundle_key]
  default_binding: unity_addressable
  required_fields_per_binding:
    unity_addressable:
      - addressable_path
      - preload
      - streaming
    custom_bundle_key:
      - bundle_id
      - priority

capability_tags:
  predefined: [scalable, tintable, localizable, skinnable, compressible, streamable]
  usage: "每个资产至少声明一个 capability"

platform_constraints:
  mobile: { max_texture_size: 1024, allowed_compression: [ASTC, ETC2] }
  pc: { max_texture_size: 4096, allowed_compression: [BC7, BC3] }
  switch: { max_texture_size: 512, allowed_compression: [ASTC] }
  default_platform: pc

localization_binding:
  ui_text:
    embed_text_in_texture: false
    dynamic_text_supported: true
    font_style_uid_required: true
  voice_over:
    language_binding: "{uid}_{lang}.ogg"

dependency_graph:
  auto_generate: true
  fields: [asset_uid, depends_on_uid, relation_type]

schema_migration:
  migration_rules:
    - from: "2.0"
      to: "2.1"
      transforms:
        - field: "frames"
          action: "wrap_to_object"
          new_field: "frames"
          structure:
            count: "$old_frames"
            interpolation: "linear"

# observability:
#   metrics: [load_count, memory_peak, streaming_failures, variant_hit_rate]
```
