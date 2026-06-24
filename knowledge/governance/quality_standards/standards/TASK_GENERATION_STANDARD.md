# 任务生成标准 v1.0.0

## 标题要求

- 标题不应包含长篇范本说明、数据来源说明或反推免责声明。
- 平均标题长度目标不超过 80 字符。
- 标题清理不得移除 `source_refs`，可追溯性必须由结构化字段保留。

## 程序任务字段

程序任务应包含 `task_id`、`requirement_id`、`title`、`phase`、`category`、
`priority`、`target_path`、`output_files`、`source_refs`、`acceptance`。

## 美术任务字段

美术任务应包含 `task_id`、`asset_id`、`title`、`asset_type`、`category`、
`priority`、`complexity`、`phase`、`source_refs`。

## 优先级规则

- P0: 核心可玩切片、战斗输入、基础 HUD、关键目标闭环。
- P1: 成长、经济、数据、内容补全。
- P2: 发布、文档、合规、后续运营和润色。
