# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


project_root = Path(SPECPATH).resolve().parent

datas = []
datas += collect_data_files("src", includes=["assets/*.png", "assets/*.ico"])
datas += copy_metadata("PySide6")
datas += copy_metadata("websockets")
datas += copy_metadata("prometheus_client")

binaries = []
binaries += collect_dynamic_libs("PySide6")

hiddenimports = []
hiddenimports += collect_submodules("PySide6")
hiddenimports += collect_submodules("websockets")


a = Analysis(
    ["zones.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="ZONES",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "src" / "assets" / "Zones.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ZONES",
)
