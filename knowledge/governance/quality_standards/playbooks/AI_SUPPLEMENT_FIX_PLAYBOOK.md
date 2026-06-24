# AI 补全修复手册 v1.0.0

## 适用场景

- `ai_supplement.fallback_used = true`。
- 生成实体缺乏项目特异性。
- adapter 配置错误导致 Step02 降级。

## 诊断

1. 检查 `settings/project_settings.json` 的 `pipeline_adapter`。
2. 检查 `core/adapters/*` 是否透传 timeout 和 sandbox。
3. 读取 `entity_coverage_report.json.ai_supplement`。
4. 检查缓存是否记录了旧错误。

## 修复

- Codex 可用时，确保 Step02 使用 `sandbox="none"`。
- Claude 可用时，确保使用 `task.timeout_seconds`。
- adapter 不可用时，fallback 必须有明确错误记录。

## 验证

运行 adapter 单元测试和 Step02 supplement 单元测试。
