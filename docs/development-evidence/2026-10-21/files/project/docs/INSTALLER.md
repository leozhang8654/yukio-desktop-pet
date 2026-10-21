# macOS 拖拽安装包

正式 macOS 产物为 `Yukio-<版本>-macOS.dmg`。双击后在 Finder 安装窗口中，将左侧 Yukio 拖到右侧「应用程序 Applications」，再从「应用程序」启动。窗口背景直接展示安装、更新和首次打开的说明。

## 构建

在项目根目录首次准备打包工具（用户安装 Yukio 不需要 Python）：

```sh
python3 -m venv YukioPlayer/build/dmg-tools
YukioPlayer/build/dmg-tools/bin/python -m pip install -r YukioPlayer/scripts/dmg-requirements.txt
```

完整通用应用构建仍使用 `YukioPlayer/scripts/package-release.sh`。分页素材准备要求不变，输出到 `YukioPlayer/dist/`。打包脚本拒绝覆盖同名产物，重新打包时使用新的输出路径。

仅改变安装外壳、保留已有应用内容及签名：

```sh
sh YukioPlayer/scripts/package-macos-dmg.sh /path/to/Yukio.app /path/to/Yukio-macOS.dmg
```

`installer-background.swift` 生成 720×460 点、2 倍清晰度背景；`build-dmg.py` 使用 [dmgbuild](https://github.com/dmgbuild/dmgbuild) 直接写入 Finder 窗口大小、图标位置和背景信息，不需要控制 Finder 的自动化权限。生成后校验镜像并写入 SHA-256 文件。可通过 `YUKIO_DMG_PYTHON` 指定已安装这些依赖的 Python。

## 检查

挂载最终 DMG，核对窗口设置、应用和 Applications 链接；比较包内应用与输入文件哈希，并执行 `codesign --verify --deep --strict`。安装包采用应用原有临时签名，DMG 本身不会免除 macOS 首次运行的来源检查。
