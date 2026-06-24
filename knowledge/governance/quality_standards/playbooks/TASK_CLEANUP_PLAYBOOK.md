# 任务清理手册 v1.0.0

## 适用场景

Step07/08 任务标题包含重复范本说明、长免责声明或无法扫描的段落。

## 修复原则

- 在生成源头清理标题。
- 保留 `source_refs` 作为完整追溯入口。
- 泛词标题应替换为可读 fallback。
- 输出公共说明文件，避免每条任务重复说明。

## 验证

- 标题不含重复噪声。
- 任务保留 source_refs。
- 程序任务包含 category/priority。
- 美术任务包含 asset_type/category/priority/complexity。
