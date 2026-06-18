#!/usr/bin/env python3
"""
差量更新包生成器
对比新旧版本的构建产物，生成差量补丁包和更新清单。
"""

import os
import hashlib
import zipfile
from datetime import datetime
from pathlib import Path

from tools.structured_md import read_structured_or_text, write_data

BASE_DIR = Path(__file__).parent.parent
BUILD_ROOT = BASE_DIR / "outputs" / "builds"
RELEASE_DIR = BASE_DIR / "outputs" / "release_history"


def _compute_file_hash(filepath):
    """计算文件的 SHA256 Hash"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def scan_files(directory):
    """扫描目录下所有文件，返回 {相对路径: hash}"""
    result = {}
    base = Path(directory)
    for root, dirs, filenames in os.walk(base):
        for fn in filenames:
            fp = Path(root) / fn
            rel = fp.relative_to(base)
            result[str(rel).replace("\\", "/")] = _compute_file_hash(fp)
    return result


def save_version_snapshot(version, build_dir):
    """保存某个版本的 Hash 快照到 release_history"""
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    version_dir = RELEASE_DIR / f"v{version}"
    version_dir.mkdir(exist_ok=True)

    files = scan_files(build_dir)
    snapshot = {
        "version": version,
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": [{"path": p, "hash": h} for p, h in files.items()]
    }
    snapshot_path = version_dir / "file_hashes.md"
    write_data(snapshot_path, snapshot, title="File Hashes")
    return snapshot_path


def load_last_snapshot():
    """加载最近一次发布的版本快照"""
    if not RELEASE_DIR.exists():
        return None
    versions = sorted([d for d in os.listdir(RELEASE_DIR) if d.startswith('v')], reverse=True)
    if not versions:
        return None
    snapshot_path = RELEASE_DIR / versions[0] / "file_hashes.md"
    if not snapshot_path.exists():
        snapshot_path = RELEASE_DIR / versions[0] / "file_hashes.json"
    if snapshot_path.exists():
        return read_structured_or_text(snapshot_path)
    return None


def generate_patch(last_snapshot, current_build_dir, old_ver, new_ver):
    """生成差量补丁包"""
    old_files = {f["path"]: f["hash"] for f in last_snapshot["files"]}
    new_files = scan_files(current_build_dir)

    changed_files = []
    for path, new_hash in new_files.items():
        old_hash = old_files.get(path)
        if old_hash != new_hash:
            changed_files.append(path)

    deleted_files = [p for p in old_files if p not in new_files]

    # 打包
    patch_dir = RELEASE_DIR / f"v{new_ver}"
    patch_dir.mkdir(exist_ok=True)
    patch_file = patch_dir / f"patch_v{old_ver}_to_v{new_ver}.zip"

    with zipfile.ZipFile(patch_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in changed_files:
            fp = Path(current_build_dir) / path
            zf.write(fp, path)

    # 更新清单
    manifest = {
        "latest_version": new_ver,
        "min_supported_version": old_ver,
        "update_url": f"https://your-server.com/patches/patch_v{old_ver}_to_v{new_ver}.zip",
        "patch_size_mb": round(os.path.getsize(patch_file) / (1024 * 1024), 2),
        "release_notes": "",
        "changed_files": [
            {"path": p, "action": "modified"} for p in changed_files
        ] + [{"path": p, "action": "deleted"} for p in deleted_files]
    }

    manifest_path = RELEASE_DIR / "update_manifest.md"
    write_data(manifest_path, manifest, title="Update Manifest")

    return patch_file, manifest_path


def run_delta_pipeline():
    """主流程"""
    # 1. 找最新的构建目录
    build_dirs = sorted(BUILD_ROOT.glob("devflow_Build_*"), reverse=True)
    if not build_dirs:
        print("未找到当前项目构建目录，请先生成 outputs/builds/devflow_Build_*。")
        return
    current_build_dir = build_dirs[0]
    print(f"📂 当前构建：{current_build_dir}")

    # 2. 确定版本号（从构建报告读取）
    report_path = current_build_dir / "build_report.md"
    new_version = "1.0"
    if report_path.exists():
        with open(report_path, 'r', encoding='utf-8') as f:
            from tools.md_parser import parse_md_output
            report = parse_md_output(f.read(), output_name="build_report")
            new_version = report.get("package", {}).get("version", "1.0")

    # 3. 先读取上一版，再保存当前版本快照，避免把刚写入的版本拿来和自己对比。
    last_snapshot = load_last_snapshot()
    snapshot_path = save_version_snapshot(new_version, current_build_dir)
    print(f"📸 版本快照已保存：{snapshot_path}")

    # 4. 对比旧版本生成补丁
    if last_snapshot is None:
        print("ℹ️ 这是首次发布，未生成补丁包。")
        return

    old_version = last_snapshot["version"]
    print(f"对比版本：{old_version} → {new_version}")

    patch_file, manifest_path = generate_patch(last_snapshot, current_build_dir, old_version, new_version)
    print(f"✅ 差量补丁已生成：{patch_file}")
    print(f"✅ 更新清单已生成：{manifest_path}")


if __name__ == "__main__":
    run_delta_pipeline()
