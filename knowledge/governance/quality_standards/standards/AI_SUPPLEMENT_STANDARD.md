# AI 补全标准 v1.0.0

## 配置要求

- `settings/project_settings.json` 的 `pipeline_adapter` 必须明确为 `codex`、`claude`、`openai` 或 `none`。
- Step02 L5 补全调用 Codex 时必须使用可读取 stdout 的 sandbox 策略。
- 无 adapter 或 adapter 失败时允许 fallback，但报告必须记录 `fallback_used` 和错误原因。

## 质量要求

- AI 补全实体必须包含 `supplement_basis`。
- 项目特定范本应优先生成项目特定名称，而不是通用品类名称。
- 缓存命中必须保留原始 adapter、fallback 状态和实体列表。

## 验证要求

- 检查 `entity_coverage_report.json.ai_supplement`。
- 检查新增实体的 label、node_id、kind、schema。
- 对 adapter 配置错误和 fallback 路径保留回归测试。
