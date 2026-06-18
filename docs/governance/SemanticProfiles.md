# SemanticProfiles

视觉语义 Token 库（通用模板）

供美术团队引用，保持视觉语言一致性
每个 profile 代表一组预定义的视觉参数

```yaml
version: "1.0"
last_modified: "2026-05-20"

profiles:
  MAT_DARK_GLASS_01:
    description: "深色半透明玻璃"
    roughness: 0.9
    metallic: 0.1
    base_color: "#0A1A1F"
    opacity: 0.6

  MAT_BRUSHED_METAL:
    description: "拉丝金属"
    roughness: 0.4
    metallic: 0.9
    base_color: "#8899AA"

  MAT_ORGANIC_FLESH:
    description: "有机血肉质感"
    roughness: 0.7
    metallic: 0.0
    subsurface_scattering: true
    base_color: "#4A2C2C"

  LIGHT_COLD_BLUE:
    description: "冷蓝光，深海/科技感"
    color_temp: 9000
    intensity: 0.8
    shadow_type: "hard"

  LIGHT_WARM_AMBER:
    description: "暖琥珀光，复古/温馨感"
    color_temp: 3500
    intensity: 1.0
    shadow_type: "soft"

  BORDER_CYBER_THIN:
    description: "赛博朋克细边框"
    inner_width: 2
    outer_width: 0
    color: "#00F0FF"
    glow: true

  BORDER_ORGANIC_THICK:
    description: "有机风格粗边框"
    inner_width: 6
    outer_width: 2
    color: "#5C3A3A"
    glow: false

  PARTICLE_DRIFTING_SPARKS:
    description: "漂浮火花粒子"
    count: 20
    size_range: [2, 8]
    color_ramp: ["#FFAA00", "#FF4400", "#000000"]
    lifetime: 1.5

  POST_FILM_GRAIN:
    description: "胶片颗粒效果"
    grain_intensity: 0.15
    vignette_strength: 0.3
    color_filter: "#1A2B3C"
```
