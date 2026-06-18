# Git 提交规范与自动化

> 项目规则：每次优化内容必须提交到 Git  
> 生效日期：2026-06-18

---

## 📜 核心规则

### ⚠️ 强制要求

**每次优化、修复、功能添加后，必须立即提交到 Git。**

不允许的行为：
- ❌ 累积多个修改后一次性提交
- ❌ 完成工作后忘记提交
- ❌ 只在本地保存不推送到远程

必须遵守：
- ✅ 修复一个 Bug → 立即提交
- ✅ 完成一个功能 → 立即提交
- ✅ 更新一个文档 → 立即提交
- ✅ 优化一段代码 → 立即提交
- ✅ 每天结束工作前 → 确保推送到远程

---

## 🔄 标准工作流程

### 工作流程模板

```bash
# 1. 开始工作前：拉取最新代码
cd E:/workwork/CrewAi/AutoDesignMaker
git pull origin master

# 2. 进行修改（修复 Bug / 添加功能 / 优化代码）
# ... 你的工作 ...

# 3. 查看修改内容
git status
git diff

# 4. 添加修改的文件
git add <修改的文件>
# 或添加所有修改
git add .

# 5. 提交（使用规范的提交信息）
git commit -m "类型: 简短描述

详细说明（可选）

关联 Issue（可选）"

# 6. 推送到远程（必须！）
git push origin master

# 7. 确认推送成功
git status
```

---

## 📝 提交信息规范

### 格式

```
<类型>: <简短描述> (<Issue编号，可选>)

<详细说明>（可选，换行）

<Footer>（可选）
- Fixes #<Issue编号>
- Closes #<Issue编号>
- See #<Issue编号>
```

### 类型（Type）

| 类型 | 说明 | 示例 |
|------|------|------|
| `fix` | Bug 修复 | `fix: 修复开发阶段插件导入路径 (ISSUE-004)` |
| `feat` | 新功能 | `feat: 实现 D1 项目画像数据收集` |
| `refactor` | 代码重构 | `refactor: 统一路径管理逻辑` |
| `perf` | 性能优化 | `perf: 优化设计引擎计算速度` |
| `docs` | 文档更新 | `docs: 更新插件开发指南` |
| `style` | 代码格式 | `style: 格式化 config_loader.py` |
| `test` | 测试相关 | `test: 添加路径解析单元测试` |
| `chore` | 构建/工具 | `chore: 更新 .gitignore` |
| `revert` | 回滚 | `revert: 回滚 commit abc123` |

### 提交信息示例

**Bug 修复**：
```bash
git commit -m "fix: 修复开发阶段插件导入路径错误

- 修改 src/plugins/stages/development/base.py 第29行
- 添加动态项目根目录解析到 sys.path
- 所有开发阶段 (00-15) 现在可以正常执行

Fixes #4"
```

**功能实现**：
```bash
git commit -m "feat: 实现 D1 项目画像阶段

- 添加项目元数据收集表单 (9个字段)
- 实现必填字段验证
- 输出 design_portrait.json 产物
- 添加单元测试

Implements #1"
```

**重构**：
```bash
git commit -m "refactor: 统一设计数据路径管理

- 重构 design_tool.data_loader.data_dir()
- 使用 src.core.paths.DESIGN_DATA_DIR 作为唯一路径来源
- 移除重复的路径解析逻辑

See #7"
```

**文档更新**：
```bash
git commit -m "docs: 更新 Git 提交规范文档

- 添加自动化提交检查列表
- 补充提交信息示例
- 添加常用命令快速参考"
```

---

## ✅ 提交前检查清单

每次提交前必须检查：

### 代码质量
- [ ] 代码可以正常运行（无语法错误）
- [ ] 相关测试通过
- [ ] 没有引入新的 bug
- [ ] 代码格式符合规范
- [ ] 没有遗留的调试代码（`print()`, `console.log()`）

### 文件检查
- [ ] 只提交相关的修改文件
- [ ] 没有提交敏感信息（密码、API密钥）
- [ ] 没有提交大型二进制文件（除非必要）
- [ ] 没有提交临时文件（`.pyc`, `.log`, `.tmp`）

### 提交信息
- [ ] 提交信息清晰描述了修改内容
- [ ] 使用了正确的类型前缀
- [ ] 引用了相关的 Issue 编号（如果有）
- [ ] 提交信息使用中文或英文（保持一致）

---

## 🚀 快速提交命令

### 单文件修复

```bash
# 修复单个文件并提交
git add src/plugins/stages/development/base.py
git commit -m "fix: 修复开发阶段导入路径"
git push origin master
```

### 多文件功能开发

```bash
# 添加多个相关文件
git add src/plugins/stages/design/step_d1_project_portrait.py
git add data/schemas/design_portrait.schema.json
git add tests/test_d1_plugin.py

git commit -m "feat: 完整实现 D1 项目画像阶段

- 实现 execute() 方法
- 添加 Schema 验证
- 添加单元测试"

git push origin master
```

### 批量提交所有修改

```bash
# ⚠️ 谨慎使用：确保所有修改都相关
git add .
git commit -m "fix: 修复多个路径相关问题

- 修复 ISSUE-004 导入路径
- 修复 ISSUE-007 路径解析重复
- 统一使用 src.core.paths"

git push origin master
```

---

## 📅 日常提交节奏

### 推荐的提交频率

| 场景 | 提交时机 | 示例 |
|------|---------|------|
| **Bug 修复** | 修复完成后立即提交 | 修复一个 Issue → 提交 |
| **功能开发** | 功能点完成后提交 | 实现一个 Stage 插件 → 提交 |
| **重构** | 重构完成且测试通过后提交 | 重构一个模块 → 提交 |
| **文档更新** | 文档编写完成后提交 | 更新一份文档 → 提交 |
| **每日结束** | 工作结束前必须推送到远程 | 下班前 → `git push` |

### 不建议的做法

| ❌ 不建议 | ✅ 建议 |
|----------|---------|
| 一天只提交一次 | 每完成一个任务就提交 |
| 多个不相关的修改一次提交 | 每个修改单独提交 |
| 提交后不推送到远程 | 提交后立即推送 |
| 提交信息写 "update" | 提交信息清晰描述修改 |

---

## 🛠️ Git 别名（快捷命令）

在项目根目录创建 `.git/config` 别名：

```bash
cd E:/workwork/CrewAi/AutoDesignMaker

# 添加别名
git config alias.st status
git config alias.co checkout
git config alias.br branch
git config alias.cm commit
git config alias.ps push
git config alias.pl pull
git config alias.lg "log --oneline --graph --decorate --all"

# 快速提交别名
git config alias.quick "!git add . && git commit -m"
```

### 使用别名

```bash
# 查看状态
git st

# 快速提交所有修改
git quick "fix: 修复导入路径"

# 推送
git ps origin master

# 查看日志
git lg
```

---

## 🔔 自动化提交检查

### 创建 Pre-commit Hook（可选）

创建 `.git/hooks/pre-commit` 文件（Windows 下需要 Git Bash）：

```bash
#!/bin/bash
# Pre-commit hook: 提交前检查

echo "🔍 执行提交前检查..."

# 检查是否有 Python 语法错误
echo "检查 Python 语法..."
python -m py_compile $(git diff --cached --name-only --diff-filter=ACM | grep '\.py$') 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Python 语法错误，提交取消"
    exit 1
fi

# 检查是否提交了敏感文件
echo "检查敏感文件..."
if git diff --cached --name-only | grep -E '(\.env|secrets|credentials|\.key|\.pem)'; then
    echo "⚠️  警告：检测到敏感文件，请确认是否要提交"
    read -p "继续提交？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ 检查通过"
exit 0
```

赋予执行权限：
```bash
chmod +x .git/hooks/pre-commit
```

---

## 📊 提交统计

### 查看提交历史

```bash
# 查看最近10次提交
git log --oneline -10

# 查看今天的提交
git log --since="midnight" --oneline

# 查看某个作者的提交
git log --author="YourName" --oneline

# 查看提交统计
git shortlog -sn
```

### 查看修改统计

```bash
# 查看代码行数变化
git diff --stat

# 查看今天的修改量
git diff --shortstat "@{yesterday}"
```

---

## 🆘 常见问题

### Q1: 忘记提交了怎么办？

```bash
# 1. 检查是否有未提交的修改
git status

# 2. 如果有，立即提交
git add .
git commit -m "补充提交：之前遗漏的修改"
git push origin master
```

### Q2: 提交信息写错了怎么办？

```bash
# 修改最后一次提交信息（未推送前）
git commit --amend -m "fix: 正确的提交信息"

# 如果已经推送，只能再提交一次
git commit --allow-empty -m "docs: 更正上一次提交信息描述"
git push origin master
```

### Q3: 不小心提交了错误的文件怎么办？

```bash
# 撤销最后一次提交（保留修改）
git reset --soft HEAD~1

# 移除不需要的文件
git reset HEAD <错误的文件>

# 重新提交
git commit -m "fix: 正确的提交"
git push origin master
```

### Q4: 推送失败怎么办？

```bash
# 拉取远程最新代码
git pull --rebase origin master

# 解决冲突（如果有）
# 编辑冲突文件，解决冲突后：
git add <冲突文件>
git rebase --continue

# 重新推送
git push origin master
```

---

## 📋 每日工作流程模板

### 早上开始工作

```bash
# 1. 进入项目目录
cd E:/workwork/CrewAi/AutoDesignMaker

# 2. 拉取最新代码
git pull origin master

# 3. 查看当前状态
git status

# 4. 开始工作...
```

### 完成一个任务

```bash
# 1. 查看修改
git status
git diff

# 2. 测试修改是否正常
python src/main.py --test

# 3. 提交修改
git add <修改的文件>
git commit -m "类型: 描述"
git push origin master

# 4. 确认推送成功
git status
```

### 晚上结束工作

```bash
# 1. 查看是否有未提交的修改
git status

# 2. 如果有，提交所有修改
git add .
git commit -m "chore: 保存今日工作进度"
git push origin master

# 3. 查看今日提交
git log --since="midnight" --oneline

# 4. 退出
```

---

## 🎯 总结

### 核心原则

1. **小步快走**：每完成一个小任务就提交
2. **清晰描述**：提交信息清晰说明修改内容
3. **及时推送**：提交后立即推送到远程
4. **保持同步**：开始工作前先拉取最新代码
5. **每日推送**：每天结束工作前必须推送

### 记住这个循环

```
拉取 → 修改 → 测试 → 提交 → 推送 → 重复
 ↑                                  ↓
 └──────────────────────────────────┘
```

---

**遵守这些规则，保持代码库的整洁和可追溯性！** 🚀
