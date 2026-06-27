# AutoDesignMaker

AutoDesignMaker merges the migrated DevFlow development pipeline with the
commercial game design decision tool.

## ⚠️ Git 提交规则（强制）

**每次优化、修复或功能添加后，必须立即提交到 Git。**

详细规范请参考：[docs/GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md)

快速提交：
```bash
git add .
git commit -m "类型: 描述修改内容"
git push origin master
```

## 快速开始

```bash
python gui_app.py
```

首次启动后在主窗口右上角点击 `AI` 状态，打开统一 AI 配置：

- `OpenAI API`：填写 `base_url`、`api_key`、模型名。
- `Codex CLI` / `Claude Code CLI`：填写 CLI 命令路径，确保已安装并登录。
- 图片生成只看当前 Profile 的图片开关和来源。

正式 DevFlow 运行仍需要在“项目配置”中填写项目路径和编辑器路径。

## 配置文件

- `settings/app.toml`：应用、UI、插件、人工门控等非敏感配置。
- `settings/ai_config.example.json`：可提交的 AI 配置模板。
- `settings/ai_config.json`：本地统一 AI 配置，包含 API Key，已忽略，禁止提交。
- `settings/project_settings.json`：本地项目路径配置，已忽略。
- `settings/api_config.toml`：旧版 API 配置，仅作为迁移来源保留兼容。

## Layout

- `core/`: path, configuration, context, adapters, runtime, and UI infrastructure.
- `pipeline/`: D1-D4 design plugins and Step00-17 development stage plugins.
- `knowledge/`: design data, schemas, governance, skills, and AI memory.
- `settings/`: local and committed configuration files.
- `tools/`: validation, migration, memory, build, and asset production utilities.
- `drafts/`, `sandbox/`, `saves/`, `logs/`: runtime output and local state.
