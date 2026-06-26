# Claude Code 入口

请阅读 **[AI_README.md](AI_README.md)** 获取完整项目导读和开发规则。

进入项目后还需读取 **[knowledge/ai_memory/INDEX.md](knowledge/ai_memory/INDEX.md)** 获取跨会话记忆。

---

## 记忆同步规则（AI 自执行，无需用户触发）

**以下情况立即同步记忆：**
1. 完成一份完整计划或方案文档
2. 做出影响后续开发的架构/设计决策
3. 修复了重要 bug 并验证通过
4. 一轮工作结束，产出了新的文件、结构或规则

**同步操作：**
- 在 `C:\Users\admin\.claude\projects\E--workwork-CrewAi-AutoDesignMaker\memory\` 新建或更新对应记忆文件
- 更新 `MEMORY.md` 索引（在顶部追加新条目）
- 不需要告知用户"我已同步"，静默完成即可

**以下情况不同步，继续工作：**
- 仍在进行中的任务，尚未产出结论
- 只是读取文件、分析问题，没有实质性输出
- 对话性问答，无持久价值
