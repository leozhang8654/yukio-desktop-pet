# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包脚本：把雪绪打成一个 Yukio.exe（素材一起塞进去）。

用法（Windows，在 YukioWin 目录）：
    pyinstaller --noconfirm scripts\yukio.spec
产物：dist\Yukio\Yukio.exe（由 Velopack 生成安装包）
"""

import os
import json
import hashlib
import subprocess
from pathlib import Path
import velopack  # Fail packaging early if the updater dependency is missing.
from PyInstaller.utils.hooks import collect_all

uia_datas, uia_binaries, uia_hiddenimports = collect_all("uiautomation")

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
REPO = os.path.dirname(ROOT)

# 素材优先用 YukioWin/Assets（自带副本），否则用仓库里 macOS 版的那一份。
ASSET_CANDIDATES = [
    os.path.join(ROOT, "build", "windows-assets", "Assets"),
    os.path.join(ROOT, "Assets"),
    os.path.join(REPO, "YukioPlayer", "Resources", "Assets"),
    os.path.join(REPO, "assets"),
]
ASSETS = next((p for p in ASSET_CANDIDATES
               if os.path.isfile(os.path.join(p, "activities", "activities.json"))), None)
if not ASSETS:
    raise SystemExit("找不到素材目录 Assets，找过：\n  " + "\n  ".join(ASSET_CANDIDATES))

ICON = os.path.join(ROOT, "Resources", "Yukio.ico")

# Keep the actual source commit and exact packaged resources inside each installer.
provenance_path = Path(ROOT) / "build" / "build-provenance.json"
provenance_path.parent.mkdir(parents=True, exist_ok=True)
provenance_path.write_text(json.dumps({
    "sourceRevision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
    "assetSha256": {p.relative_to(ASSETS).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(Path(ASSETS).rglob("*")) if p.is_file()},
}, indent=2), encoding="utf-8")

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=uia_binaries,
    datas=[(str(provenance_path), "."), (ASSETS, "Assets"), (os.path.join(REPO, "YukioPlayer", "integrations", "deepseek"), "integrations/deepseek")] + uia_datas,
    hiddenimports=uia_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # 用不上的大件全部排掉，exe 能小一半。
    excludes=["numpy", "scipy", "matplotlib", "PyQt5", "PySide2",
              "pytest", "setuptools", "pip", "PIL.ImageQt", "PIL.ImageTk"],
    noarchive=False,
)
# PyInstaller 6 起 Analysis 不再有 zipped_data / zipfiles，5.x 还有，这里两边都认。
try:
    pyz = PYZ(a.pure, a.zipped_data)
except AttributeError:
    pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Yukio", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=ICON if os.path.exists(ICON) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Yukio")
