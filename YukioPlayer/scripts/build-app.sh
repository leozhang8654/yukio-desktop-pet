#!/bin/sh
# 构建 build/Yukio.app（显示名“雪绪”）。只需要 Xcode Command Line Tools，无第三方依赖。
# 可选参数 $1：已经编好的可执行文件（发版脚本用它塞进通用二进制），不给就现场编译。
# 资源随应用打包在 Contents/Resources/Assets，不依赖本机其他路径。
# 可选环境变量 YUKIO_PAGED_ASSETS 指向 prepare-windows-assets.py 生成的 Assets；
# 正式包用它附加低内存分页，源码图集仍保留作权威素材与兼容回退。
# 图标是 Resources/AppIcon.icns（tools/icon/make_icon.py 生成），一并打进去。
set -eu
ARG_BIN="${1:-}"
[ -n "$ARG_BIN" ] && ARG_BIN="$(cd "$(dirname "$ARG_BIN")" && pwd)/$(basename "$ARG_BIN")"   # 先转绝对路径，下面要换目录
cd "$(dirname "$0")/.."

if [ -n "$ARG_BIN" ]; then
  BIN="$ARG_BIN"
else
  swift build -c release
  BIN="$(swift build -c release --show-bin-path)/YukioPlayer"
fi
APP="build/Yukio.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/YukioPlayer"
cp -R Resources/Assets "$APP/Contents/Resources/Assets"
if [ -n "${YUKIO_PAGED_ASSETS:-}" ]; then
  PAGE_SOURCE="$YUKIO_PAGED_ASSETS/motion/windows-pages"
  if [ ! -f "$PAGE_SOURCE/manifest.json" ]; then
    echo "找不到分页素材清单：$PAGE_SOURCE/manifest.json" >&2
    exit 1
  fi
  rm -rf "$APP/Contents/Resources/Assets/motion/windows-pages"
  cp -R "$PAGE_SOURCE" "$APP/Contents/Resources/Assets/motion/windows-pages"
fi
cp Resources/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"   # 访达里显示的封面，tools/icon/make_icon.py 生成

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>local.yukio.player</string>
  <key>CFBundleName</key><string>雪绪</string>
  <key>CFBundleDisplayName</key><string>雪绪</string>
  <key>CFBundleExecutable</key><string>YukioPlayer</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.2.2</string>
  <key>CFBundleVersion</key><string>4</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# 本机自用的临时签名；分发给他人需要正式签名与公证。
codesign --force --sign - "$APP" >/dev/null
echo "$APP"
