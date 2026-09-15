#!/bin/sh
# 构建 build/Yukio.app（显示名“雪绪”）。只需要 Xcode Command Line Tools，无第三方依赖。
# 资源随应用打包在 Contents/Resources/Assets，不依赖本机其他路径。
set -eu
cd "$(dirname "$0")/.."

swift build -c release
BIN="$(swift build -c release --show-bin-path)/YukioPlayer"
APP="build/Yukio.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/YukioPlayer"
cp -R Resources/Assets "$APP/Contents/Resources/Assets"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>local.yukio.player</string>
  <key>CFBundleName</key><string>雪绪</string>
  <key>CFBundleDisplayName</key><string>雪绪</string>
  <key>CFBundleExecutable</key><string>YukioPlayer</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# 本机自用的临时签名；分发给他人需要正式签名与公证。
codesign --force --sign - "$APP" >/dev/null
echo "$APP"
