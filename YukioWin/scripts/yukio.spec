# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包脚本：把雪绪打成一个 Yukio.exe（素材一起塞进去）。

用法（Windows，在 YukioWin 目录）：
    pyinstaller --noconfirm scripts\yukio.spec
产物：dist\Yukio.exe
"""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
REPO = os.path.dirname(ROOT)

# 素材优先用 YukioWin/Assets（自带副本），否则用仓库里 macOS 版的那一份。
ASSET_CANDIDATES = [
    os.path.join(ROOT, "Assets"),
    os.path.join(REPO, "YukioPlayer", "Resources", "Assets"),
    os.path.join(REPO, "assets"),
]
ASSETS = next((p for p in ASSET_CANDIDATES
               if os.path.isfile(os.path.join(p, "activities", "activities.json"))), None)
if not ASSETS:
    raise SystemExit("找不到素材目录 Assets，找过：\n  " + "\n  ".join(ASSET_CANDIDATES))

ICON = os.path.join(ROOT, "Resources", "Yukio.ico")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(ASSETS, "Assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # 用不上的大件全部排掉，exe 能小一半。
    excludes=["numpy", "scipy", "tkinter", "matplotlib", "PyQt5", "PySide2",
              "pytest", "setuptools", "pip", "PIL.ImageQt", "PIL.ImageTk"],
    noarchive=False,
)
# PyInstaller 6 起 Analysis 不再有 zipped_data / zipfiles，5.x 还有，这里两边都认。
try:
    pyz = PYZ(a.pure, a.zipped_data)
except AttributeError:
    pyz = PYZ(a.pure)

parts = [pyz, a.scripts, a.binaries]
if hasattr(a, "zipfiles"):
    parts.append(a.zipfiles)
parts += [a.datas, []]

exe = EXE(
    *parts,
    name="Yukio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # 桌面宠物不要黑框
    icon=ICON if os.path.exists(ICON) else None,
)
