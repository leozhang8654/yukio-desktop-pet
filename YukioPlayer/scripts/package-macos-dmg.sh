#!/bin/sh
# Create a Finder drag-to-install window around an existing signed app.
# Build dependencies: macOS Command Line Tools and scripts/dmg-requirements.txt.
set -eu
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 /path/to/Yukio.app /path/to/output.dmg" >&2
  exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
test -f "$APP/Contents/Info.plist"
codesign --verify --deep --strict "$APP"
mkdir -p "$(dirname "$2")"
DMG="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
if [ -e "$DMG" ]; then
  echo "Output already exists: $DMG" >&2
  exit 1
fi
DMG_PYTHON="${YUKIO_DMG_PYTHON:-$SCRIPT_DIR/../build/dmg-tools/bin/python}"
if ! "$DMG_PYTHON" -c 'import dmgbuild' 2>/dev/null; then
  echo "先安装 DMG 打包工具（只在开发机需要）：" >&2
  echo "python3 -m venv YukioPlayer/build/dmg-tools" >&2
  echo "YukioPlayer/build/dmg-tools/bin/python -m pip install -r YukioPlayer/scripts/dmg-requirements.txt" >&2
  exit 1
fi
STAGING="$(mktemp -d "${TMPDIR:-/tmp}/yukio-dmg-artwork.XXXXXX")"
trap 'rm -rf "$STAGING"' EXIT
swift "$SCRIPT_DIR/installer-background.swift" "$STAGING/install.tiff"
"$DMG_PYTHON" "$SCRIPT_DIR/build-dmg.py" "$APP" "$DMG" "$STAGING/install.tiff"
hdiutil verify "$DMG"
shasum -a 256 "$DMG" > "$DMG.sha256"
echo "$DMG"
