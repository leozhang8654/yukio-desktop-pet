#!/bin/sh
# 打一个可以直接发给别人的压缩包：dist/Yukio-<版本>-macOS.zip（Apple 芯片 + Intel 通用二进制）。
# 只需要 Xcode Command Line Tools。完整 Xcode 才支持 swift build --arch，所以这里分两次编译再用 lipo 合并。
set -eu
cd "$(dirname "$0")/.."

echo "编译 arm64…"
swift build -c release
ARM="$(swift build -c release --show-bin-path)/YukioPlayer"

echo "编译 x86_64…"
swift build -c release --triple x86_64-apple-macosx13.0
X86="$(swift build -c release --triple x86_64-apple-macosx13.0 --show-bin-path)/YukioPlayer"

mkdir -p build
FAT="$PWD/build/YukioPlayer-universal"
lipo -create "$ARM" "$X86" -output "$FAT"
lipo -info "$FAT"

./scripts/build-app.sh "$FAT" >/dev/null
APP="build/Yukio.app"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"

rm -rf dist
mkdir -p dist
ZIP="dist/Yukio-$VERSION-macOS.zip"
# ditto 保留签名与符号链接；--keepParent 让别人解压后直接得到 Yukio.app
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
shasum -a 256 "$ZIP" | tee "$ZIP.sha256"

codesign -v "$APP" && echo "签名自检通过（临时签名，别人下载后第一次打开仍需右键→打开）"
echo "$ZIP"
