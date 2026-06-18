# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\workwork\\CrewAi\\AutoDesignMaker\\src\\gui_app.py'],
    pathex=['E:\\workwork\\CrewAi\\AutoDesignMaker'],
    binaries=[],
    datas=[('E:\\workwork\\CrewAi\\AutoDesignMaker\\data', 'data')],
    hiddenimports=['design_tool.ui.app_window'],
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
    name='AutoDesignMaker',
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
