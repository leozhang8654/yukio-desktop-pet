#!/bin/sh
# Package an existing app with a drag-to-install shortcut, without rebuilding it.
set -eu
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 /path/to/Yukio.app /path/to/output.zip" >&2
  exit 1
fi
APP="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
test -f "$APP/Contents/Info.plist"
mkdir -p "$(dirname "$2")"
ZIP="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
if [ -e "$ZIP" ]; then
  echo "Output already exists: $ZIP" >&2
  exit 1
fi
STAGING="$(mktemp -d "${TMPDIR:-/tmp}/yukio-installer.XXXXXX")"
trap 'rm -rf "$STAGING"' EXIT
PACKAGE="$STAGING/$(basename "$ZIP" .zip)"
mkdir -p "$PACKAGE"
ditto "$APP" "$PACKAGE/Yukio.app"
ln -s /Applications "$PACKAGE/应用程序 Applications"
cat > "$PACKAGE/安装说明 Installation.txt" <<'TEXT'
把 Yukio.app 拖到旁边的「应用程序 Applications」，然后从「应用程序」打开 Yukio。
如果已安装旧版，请先退出 Yukio，再拖入并选择替换。

首次打开若提示 Apple 无法验证，确认信任下载来源后：
打开「系统设置 → 隐私与安全性」，找到 Yukio，点击「仍要打开」。

Drag Yukio.app onto “应用程序 Applications” next to it, then open Yukio from Applications.
If upgrading, quit Yukio first, then drag it over and choose Replace.

If macOS cannot verify the app and you trust the download:
Go to System Settings → Privacy & Security, find Yukio, and click Open Anyway.
TEXT
# Keep the app and shortcut together when Archive Utility extracts the ZIP.
ditto -c -k --sequesterRsrc --keepParent "$PACKAGE" "$ZIP"
shasum -a 256 "$ZIP" > "$ZIP.sha256"
echo "$ZIP"
