# Gameplay Framework

- Source: source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md
- Rule: no Subway Surfers case selections are inherited; only current project selections are used.

## Core Experience

- 核心循环：load design knowledge -> choose structured decisions -> export Concept package -> run DevFlow stages -> review artifacts (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:26)
  - Purpose: make each design-to-development handoff explicit and testable.
- 压力来源：manual handoff drift, stale absolute paths, missing source packages, and unverifiable development outputs (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:30)
  - Purpose: turn migration risks into validation checks before actual Unity project mutation.
- 奖励节奏：immediate stage summaries, validation reports, package manifests, and build artifacts (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:34)
  - Purpose: give operators fast feedback after every design or development stage.

## Selected Systems

- SEL-008 system_layer：Design Engine [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:41)
- SEL-009 system_layer：DevFlow Orchestrator [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:45)
- SEL-010 system_layer：Artifact Layer [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:49)
- SEL-011 system_layer：UCOS Memory [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:53)
- SEL-012 内容：design domains, entity schemas, project templates, prompt frameworks, saved projects, source packages, and exported reports [content] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:60)
- SEL-013 资源：Python modules, JSON schemas, TOML configuration, Markdown documents, Unity project settings, and PyInstaller build output [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:67)
- SEL-014 运行时：GUI launch, D-stage plugin execution, Concept package export, DevFlow stage execution, preflight checks, tests, and packaging [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:74)
- SEL-015 表现：Tkinter desktop shell, stage summaries, validation JSON, Markdown reviews, and command output reports [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:81)
- SEL-016 技术：root-marker path resolution, TOML/JSON config loading, manifest-based plugins, legacy adapters, pytest checks, and PyInstaller packaging [platform] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:88)
- SEL-017 生产：migrate legacy assets, validate structure, run smoke stages, export Concept package, preflight Unity settings, run tests, and build executable [gameplay] (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:95)

## Resource Flow

- RES-001 资源：Python modules, JSON schemas, TOML configuration, Markdown documents, Unity project settings, and PyInstaller build output storage=none producers=none consumers=none

## Implementation Phases

### core_playable
- 项目定位：AI-assisted design-to-development automation workspace (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:7)
- 平台：Windows desktop application with Python CLI pipeline support (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:11)
- 目标玩家：game designers, technical designers, and Unity developers (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:15)
- 商业模式：internal production tool and reusable automation framework (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:19)
- 核心循环：load design knowledge -> choose structured decisions -> export Concept package -> run DevFlow stages -> review artifacts (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:26)
- 压力来源：manual handoff drift, stale absolute paths, missing source packages, and unverifiable development outputs (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:30)
- 奖励节奏：immediate stage summaries, validation reports, package manifests, and build artifacts (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:34)
- system_layer：Design Engine (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:41)
- system_layer：DevFlow Orchestrator (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:45)
- system_layer：Artifact Layer (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:49)
- system_layer：UCOS Memory (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:53)
- 资源：Python modules, JSON schemas, TOML configuration, Markdown documents, Unity project settings, and PyInstaller build output (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:67)
- 运行时：GUI launch, D-stage plugin execution, Concept package export, DevFlow stage execution, preflight checks, tests, and packaging (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:74)
- 表现：Tkinter desktop shell, stage summaries, validation JSON, Markdown reviews, and command output reports (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:81)
- 技术：root-marker path resolution, TOML/JSON config loading, manifest-based plugins, legacy adapters, pytest checks, and PyInstaller packaging (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:88)
- 生产：migrate legacy assets, validate structure, run smoke stages, export Concept package, preflight Unity settings, run tests, and build executable (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:95)
- 影响：path independence, source package compatibility, legacy save preservation, stage contract stability, and Unity mutation boundary (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:102)
### progression
- none
### economy
- none
### content_ops
- 内容：design domains, entity schemas, project templates, prompt frameworks, saved projects, source packages, and exported reports (source_artifacts/s00_cpt_v2/attachments/autodesignmaker_concept.md:60)
### social
- none
### launch_ops
- none
