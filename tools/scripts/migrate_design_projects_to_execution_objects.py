#!/usr/bin/env python3
"""Migrate existing design project files to execution objects.

This script scans for design project JSON files in:
- projects/
- sandbox/workspace/projects/

And converts them to design_project execution objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT, WORKSPACE_PROJECTS_DIR
from core.engines.execution_objects.design_project import save_design_project
from core.engines.execution_objects.integration import load_execution_object_store


def find_design_project_files() -> list[tuple[Path, dict[str, Any]]]:
    """Find all design project JSON files.

    Returns:
        List of (file_path, project_data) tuples
    """
    projects = []

    # Scan root projects/ directory
    root_projects_dir = PROJECT_ROOT / "projects"
    if root_projects_dir.exists():
        for file_path in root_projects_dir.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "projectName" in data:
                    projects.append((file_path, data))
            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️  跳过无效文件 {file_path}: {e}")

    # Scan sandbox/workspace/projects/
    if WORKSPACE_PROJECTS_DIR.exists():
        for file_path in WORKSPACE_PROJECTS_DIR.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "projectName" in data:
                    projects.append((file_path, data))
            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️  跳过无效文件 {file_path}: {e}")

    return projects


def migrate_design_projects(*, backup: bool = True, delete_originals: bool = False) -> dict[str, Any]:
    """Migrate all design project files to execution objects.

    Args:
        backup: If True, create .bak files before migration
        delete_originals: If True, delete original files after successful migration

    Returns:
        Migration result summary
    """
    print("=" * 70)
    print("设计项目迁移到执行对象存储")
    print("=" * 70)

    # Load execution object store
    print("\n📦 加载执行对象存储...")
    store = load_execution_object_store(PROJECT_ROOT)
    print(f"✅ 存储路径: {store.path}")

    # Find all project files
    print("\n🔍 扫描设计项目文件...")
    project_files = find_design_project_files()
    print(f"✅ 找到 {len(project_files)} 个项目文件")

    if not project_files:
        print("\n✅ 没有需要迁移的项目文件")
        return {"status": "success", "migrated_count": 0}

    # Migrate each project
    print("\n🚀 开始迁移...\n")
    migrated = []
    errors = []

    for file_path, project_data in project_files:
        project_name = project_data.get("projectName", "未命名")
        print(f"  📄 迁移: {file_path.name} ({project_name})")

        try:
            # Backup if requested
            if backup:
                backup_path = file_path.with_suffix(".json.bak")
                backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"    💾 备份: {backup_path.name}")

            # Save to execution object store
            execution_obj = save_design_project(
                store,
                project_data,
                title=f"[迁移] {project_name}",
                save_type="migration",
                auto_verify=True,
            )

            print(f"    ✅ 已创建执行对象: {execution_obj['execution_object_id']}")
            print(f"    📊 状态: {execution_obj['state']}")

            migrated.append({
                "file_path": str(file_path),
                "project_name": project_name,
                "execution_object_id": execution_obj["execution_object_id"],
            })

            # Delete original if requested
            if delete_originals:
                file_path.unlink()
                print(f"    🗑️  已删除原文件")

        except Exception as e:
            print(f"    ❌ 迁移失败: {e}")
            errors.append({
                "file_path": str(file_path),
                "project_name": project_name,
                "error": str(e),
            })

        print()

    # Summary
    print("=" * 70)
    print("迁移完成")
    print("=" * 70)
    print(f"✅ 成功: {len(migrated)} 个项目")
    print(f"❌ 失败: {len(errors)} 个项目")

    if migrated:
        print("\n已迁移的项目:")
        for item in migrated:
            print(f"  • {item['project_name']} → {item['execution_object_id']}")

    if errors:
        print("\n迁移失败的项目:")
        for item in errors:
            print(f"  • {item['project_name']}: {item['error']}")

    return {
        "status": "success" if not errors else "partial",
        "migrated_count": len(migrated),
        "error_count": len(errors),
        "migrated": migrated,
        "errors": errors,
    }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="迁移设计项目到执行对象存储")
    parser.add_argument("--no-backup", action="store_true", help="不创建备份文件")
    parser.add_argument("--delete-originals", action="store_true", help="迁移后删除原文件")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际迁移")

    args = parser.parse_args()

    if args.dry_run:
        print("🔍 预览模式（不会实际迁移）\n")
        project_files = find_design_project_files()
        print(f"找到 {len(project_files)} 个项目文件:")
        for file_path, project_data in project_files:
            project_name = project_data.get("projectName", "未命名")
            print(f"  • {file_path} ({project_name})")
        return

    result = migrate_design_projects(
        backup=not args.no_backup,
        delete_originals=args.delete_originals,
    )

    if result["status"] == "success":
        print(f"\n✅ 所有项目迁移成功！")
    else:
        print(f"\n⚠️  部分项目迁移失败，请检查错误信息")


if __name__ == "__main__":
    main()
