# 实体扩展手册 v1.0.0

## 输入

- 目标模板 JSON。
- 覆盖率报告或节点列表。
- `ENTITY_COVERAGE_STANDARD.md`。

## 步骤

1. 统计已覆盖节点。
2. 优先补齐 P0 16 节点。
3. 按 complete 39 节点补齐关键体验。
4. 如需 phase2 quality，扩展到 80+ 节点。
5. 每个新增实体写明 `supplement_basis`。

## 验证

- JSON 可解析。
- 覆盖率达到目标。
- 实体结构满足 schema。
- 运行模板覆盖单元测试。
