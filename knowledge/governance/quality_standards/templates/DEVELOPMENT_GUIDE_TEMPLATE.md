# 开发指南模板

## 开发原则

- 先读计划和现有实现。
- 优先复用项目内模式。
- 小阶段完成后立即自检。
- 不提交本地计划、bug 文档和运行产物。

## 常用命令

```bash
python -m pytest core\tests -q
python -m compileall core pipeline tools\validators\pipeline_quality.py
git diff --check
```

## 记录要求

将可复用经验写入治理文档，将本次执行摘要写入 AI 记忆。
