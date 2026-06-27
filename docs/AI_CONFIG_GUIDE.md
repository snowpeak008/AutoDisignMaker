# AI 配置指南

## 概览

AutoDesignMaker 使用 `settings/ai_config.json` 管理所有 AI 相关配置。一个 Profile 同时包含适配器类型、LLM 配置和图片生成配置。

`settings/ai_config.json` 是本地敏感配置，已被 `.gitignore` 忽略。可提交模板为 `settings/ai_config.example.json`。

## 主窗口入口

主窗口底部状态栏显示当前激活的 AI Profile 和适配器。绿色表示字段验证通过，红色表示配置缺失或异常。点击该状态可打开统一 AI 配置弹窗。

弹窗左侧 Profile 列表会高亮当前激活项；右侧详情区会实时显示字段验证结果。切换 Codex CLI 或 Claude Code CLI Profile 时，CLI 可用性检测在后台执行，不阻塞界面。

`应用` 会保存配置但保留弹窗，`保存` 会保存后关闭弹窗。保存成功后主窗口状态栏会立即刷新。

## Profile 字段

- `adapter`：`openai`、`codex`、`claude`、`local` 或 `none`
- `llm.source`：`api`、`cli` 或 `none`
- `image.source`：`api`、`cli_builtin` 或 `none`
- `image.enabled`：图片生成唯一开关

## 适配器

### OpenAI API

用于 OpenAI 兼容接口。需要填写：

- `base_url`
- `api_key`
- `model`

### Codex CLI

用于本地 Codex CLI。需要先在系统中安装并登录 Codex CLI，并在 Profile 中设置：

- `adapter = "codex"`
- `llm.source = "cli"`
- `llm.cli_path = "codex"`

Codex Profile 可将图片来源设为 `cli_builtin`。

### Claude Code CLI

用于本地 Claude Code CLI。需要先安装并登录 Claude CLI，并在 Profile 中设置：

- `adapter = "claude"`
- `llm.source = "cli"`
- `llm.cli_path = "claude"`

### 本地 Ollama

Ollama 走 OpenAI 兼容 API：

- `adapter = "openai"`
- `llm.source = "api"`
- `llm.base_url = "http://127.0.0.1:11434/v1"`
- `llm.api_key = "local"`

## 迁移

启动完整性检查会在 `settings/ai_config.json` 不存在时尝试迁移旧配置：

- `settings/ai_profiles.json`
- `settings/api_config.toml`
- `settings/app.toml` 的旧 `[model]` 节
- `settings/project_settings.json` 的旧 `pipeline_adapter`

迁移备份写入 `settings/.backup_*/`，迁移日志写入 `logs/config_migration.log`，二者均不提交。

## 故障排查

- API Profile 报缺少 Key：在 AI 配置对话框填写 `api_key`。
- CLI Profile 报不可用：确认命令在 PATH 中，并已完成登录。
- 图片不生成：确认当前 Profile 的 `image.enabled = true`，并且 `image.source` 与适配器匹配。
- 旧工具仍调用 `get_api_config()`：该接口保留兼容，但新代码应使用 `get_active_ai_profile()` 或 `get_pipeline_adapter()`。
