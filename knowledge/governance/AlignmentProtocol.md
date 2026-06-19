# Alignment Protocol

```yaml
alignment_version: "1.0"
source_program_plan: "Plans_20260519_143022"
source_art_plan: "ArtPlans_20260519_150010"
unified_assets:
  - uid: "player_idle"
    type: "animation"
    frames: 8
    size: [256, 256]
    format: "png"
    naming_pattern: "player_idle_{frame:03d}.png"
    program_ref: "hero_controller.idle_anim"
    art_ref: "PlayerIdle"
  ...
unresolved_conflicts:
  - type: "spec_mismatch"
    asset: "boss_death"
    program_requires: "explosion_fx: 16 frames"
    art_provides: "explosion_fx: 8 frames"
    human_decision_required: true
orphan_art_assets:
  - art_uid: "extra_ui_icon"
    reason: "No matching program dependency"
```
