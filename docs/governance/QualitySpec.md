# QualitySpec

资产质量验收标准（通用模板）

本文件由人类维护，Agent 只读

```yaml
version: "1.0"
last_modified: "2026-05-20"

general:
  allowed_formats: ["png", "tga", "jpg"]
  color_space: "sRGB"
  min_resolution: 64
  max_resolution: 4096
  power_of_two_recommended: true

by_category:
  illustration:
    dpi: 72
    max_size_kb: 5120
    alpha_channel: false
    compression: "lossless"

  ui_sprite:
    nine_slice_required: false
    alpha_channel: true
    power_of_two: true
    max_size_kb: 1024

  vfx_texture:
    alpha_channel: true
    sequence_length_min: 1
    power_of_two: false
    compression: "lossy_acceptable"

performance:
  max_texture_memory_mobile: 256
  max_draw_calls_ui: 50
  sprite_atlas_max_size: 2048

auto_checks:
  - name: "dimensions_in_range"
    description: "检查图片尺寸是否在 min_resolution 和 max_resolution 之间"
    parameters:
      min: "{{ general.min_resolution }}"
      max: "{{ general.max_resolution }}"
  - name: "format_allowed"
    description: "检查图片格式是否在允许列表中"
    parameters:
      allowed: "{{ general.allowed_formats }}"
  - name: "power_of_two"
    description: "若要求 power_of_two，检查宽高是否为2的幂"
    applies_to: ["ui_sprite"]

manual_review:
  - "色彩一致性：与 VisualDNA 中 primary_palette 无冲突"
  - "风格一致性：无卡通/二次元元素（若项目禁止）"
  - "可读性：UI 元素在目标分辨率下清晰可辨"
```
