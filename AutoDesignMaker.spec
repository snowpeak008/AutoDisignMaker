# -*- mode: python ; coding: utf-8 -*-

import os


spec_dir = os.path.dirname(os.path.abspath(SPEC))


a = Analysis(
    [os.path.join(spec_dir, "src", "gui_app.py")],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        (os.path.join(spec_dir, "data"), "data"),
        (os.path.join(spec_dir, "config"), "config"),
    ],
    hiddenimports=[
        "design_tool.ui.app_window",
        "design_tool.data_loader",
        "src.core.paths",
        "src.core.config_loader",
        "src.core.data_integrity",
        "src.plugins",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AutoDesignMaker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
