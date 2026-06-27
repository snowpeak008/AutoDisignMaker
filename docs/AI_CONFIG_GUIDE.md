# AI 配置指南

## 概览

AutoDesignMaker 使用 `settings/ai_config.json` 管理所有 AI 相关配置。当前格式为 `schema_version = 3`，按用途拆成三类：

- `dev`：开发 API，用于主流水线开发执行。
- `image`：生图 API，用于图片资产生成。
- `completion`：补全 API，用于 Step02 L5 实体补全等轻量补全任务。

`settings/ai_config.json` 是本地敏感配置，已被 `.gitignore` 忽略。可提交模板为 `settings/ai_config.example.json`。

## 主窗口入口

主窗口底部状态栏显示当前开发 API 和适配器。绿色表示字段验证通过，红色表示配置缺失或异常。点击该状态可打开统一 AI 配置弹窗。

弹窗顶部用 `开发API` / `生图API` / `补全API` 三个 Tab 切换配置类别。左侧列表按当前类别过滤，并用深色背景和 `✦` 标记当前启用项。

右侧表单按配置类型显示本地 CLI 只读提示、API URL / API Key、高级 JSON 或 Codex 多文件路径记录。

`应用` 会保存配置但保留弹窗，`保存` 会保存后关闭弹窗。保存成功后主窗口状态栏会立即刷新。

## 配置字段

- `entries[*].config_type`：配置类型，如 `local_codex_cli`、`openai_dev_api`、`codex_cli_image`。
- `entries[*].api_url` / `api_key`：API 类型配置的基础地址和密钥。
- `entries[*].extra_json`：高级 JSON 配置，可写入 `model`、`provider` 等扩展字段。
- `entries[*].codex_toml_path` / `codex_json_path`：Codex 多文件配置路径，仅记录参考，不编辑文件内容。
- `active_entry_id`：当前类别启用的配置；`image.active_entry_id` 为空时图片生成关闭。

## 配置类型

### 开发 API

- `local_codex_cli`：本地 Codex CLI，只读，无需填写参数。
- `local_claude_cli`：本地 Claude Code CLI，只读。
- `openai_dev_api`：OpenAI 兼容 API，填写 URL 和 Key。
- `custom_dev_api`：自定义 API，填写 URL、Key 和高级 JSON。

### 生图 API

- `codex_cli_image`：Codex CLI 内置生图，只读。
- `openai_image_api`：OpenAI 图片 API。
- `sd_webui_api`：本地 SD WebUI API。
- `custom_image_api`：自定义图片 API。

### 补全 API

- `local_codex_completion_cli`：本地 Codex CLI 补全。
- `local_claude_completion_cli`：本地 Claude CLI 补全。
- `openai_completion_api`：OpenAI 兼容补全 API。
- `custom_completion_api`：自定义补全 API。

## 迁移

启动完整性检查会在 `settings/ai_config.json` 不存在时尝试迁移旧配置：

- `settings/ai_profiles.json`
- `settings/api_config.toml`
- `settings/app.toml` 的旧 `[model]` 节
- `settings/project_settings.json` 的旧 `pipeline_adapter`

迁移备份写入 `settings/.backup_*/`，迁移日志写入 `logs/config_migration.log`，二者均不提交。

## 故障排查

- API 配置报缺少 Key：在对应 Tab 中填写 `API Key`。
- CLI 配置报不可用：确认命令在 PATH 中，并已完成登录。
- 图片不生成：确认 `生图API` Tab 中已经启用一个配置。
- 旧工具仍调用 `get_api_config()`：该接口保留兼容，但新代码应使用 `get_active_ai_profile()` 或 `get_pipeline_adapter()`。
