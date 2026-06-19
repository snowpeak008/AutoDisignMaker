#!/usr/bin/env python3
"""
项目脚手架工具
一键生成完整的 AI 游戏工业流水线项目结构。
使用：python scaffold.py
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path.cwd()


def create_dirs():
    """创建所有必需的文件夹"""
    dirs = [
        "Docs/governance",
        "tools",
        "source_artifacts",
        "source_artifacts/.snapshots",
        "outputs/artifacts",
    ]
    for d in dirs:
        path = BASE_DIR / d
        path.mkdir(parents=True, exist_ok=True)
        print(f"✅ {d}/")


TEMPLATES = {
    ".gitignore": """# API 密钥
api_config.md

# 流水线产物
source_artifacts/

# Python
__pycache__/
*.pyc
venv/

# 日志
logs/
*.log

# 构建产物
Build/
""",

    "api_config.template.md": """# API 统一配置模板
# 复制为 api_config.md 并填入真实密钥
providers:
  llm:
    provider: "openai"
    api_key: ""
    base_url: "https://vip.auto-code.net/v1"
    default_model: "gpt-5.5"
    models:
      chat: "gpt-5.5"
  image2:
    api_key: ""
    base_url: "https://vip.auto-code.net/v1"
    default_model: "gpt-image-2"

project:
  dev_work_dir: "D:/YourGame/Project"
""",

    "my_game_idea.txt": """# 在这里用任意形式描述你的游戏核心想法
# 可以包含：玩家做什么、情感目标、世界观约束、禁止风格等
"""
}


def create_files():
    """写入所有模板文件"""
    for filename, content in TEMPLATES.items():
        filepath = BASE_DIR / filename
        if filepath.exists():
            print(f"⚠️  {filename} 已存在，跳过。")
            continue
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ {filename}")


def main():
    print("=" * 60)
    print("AI 游戏工业流水线 - 项目脚手架")
    print("=" * 60)
    print()

    # 检查是否已存在关键文件
    if (BASE_DIR / "orchestrator.py").exists():
        print("⚠️  当前目录已存在流水线入口，建议在新的空目录下运行。")
        confirm = input("是否继续？(y/n)：").strip().lower()
        if confirm != 'y':
            print("已取消。")
            return

    print("正在创建项目结构...")
    create_dirs()
    create_files()

    print()
    print("=" * 60)
    print("项目骨架已就绪！")
    print()
    print("下一步：")
    print("1. 编辑 api_config.md，填入你的 API 密钥和游戏项目路径")
    print("2. 编辑 my_game_idea.txt，写下你的游戏核心想法")
    print("3. 将 orchestrator.py、steps/、artifact_layer/ 复制到当前目录")
    print("4. 将所有工具脚本复制到 tools/ 目录")
    print("5. 将所有治理文档复制到 Docs/governance/ 目录")
    print("6. 运行 python orchestrator.py --list 检查流水线")
    print("=" * 60)


if __name__ == "__main__":
    main()
