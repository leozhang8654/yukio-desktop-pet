# 皮肤 / Skins

在桌宠设置的「皮肤 / Skin」中选择「雪绪 / Yukio」或「千夏 / Qianxia」。切换立即生效，重启后保留；现有用户默认继续使用雪绪。位置、大小、跟随的助手、聊天和隐藏设置保持不变。

千夏使用用户提供的 `qianxia-motion-results-2026-10-13.zip` 中最新的 R07：12 个状态，支持独立眨眼的状态使用 12 级眼皮。运行素材逐字节导入，保留原时长、循环入口和状态语义。`task_complete` 沿用原包的静态完成牌，无独立眼皮层。

千夏没有专用的拎起姿势，拖动时保持当前动作，并保存放下的位置。雪绪原来的拎起动画保持不变。两套资源互相独立，切换失败时保留原皮肤；重启时若保存的皮肤不可读则回退雪绪。

## 资源与构建

- `YukioPlayer/Resources/Assets/skins/qianxia/`：完整独立目录，包含 `motion`、最小 `activities` / `base` 兼容索引，以及来源哈希 `provenance.json`。
- `base/held.png` 是 R07 待机的第一帧，仅用于目录兼容；运行时千夏拖动不使用雪绪的抓手动画。
- 导入工具：`YukioPlayer/tools/skins/import_qianxia.py <archive.zip>`，只读取指定 R07 的运行素材，不执行压缩包里的代码。
- `YukioWin/scripts/prepare-windows-assets.py` 同时为两套皮肤生成无损分页，并逐页回读核对像素。macOS 打包通过 `YUKIO_PAGED_ASSETS` 附加同源分页；Windows 包直接使用分页。
- 检查命令接受 `--skin yukio` / `--skin qianxia`，可搭配 `--check`、`--snapshot`；macOS 也支持 `--blink-snapshots`。离线检查不修改已保存的皮肤。

0.4.5 当前为本地开发版本，公开下载链接仍指向已发布版本。Windows 的跨平台逻辑和素材检查不代表 Windows 原生界面或安装包实测。

## English

Choose **Yukio** or **Qianxia** in **Pet settings → Skin**. The change is immediate and persists after restart. Existing users keep Yukio by default. Switching preserves the current activity, position, size and other preferences.

Qianxia uses the supplied R07 assets unchanged, including twelve action states and twelve eyelid levels where present. Dragging keeps the current pose because the set contains no dedicated held artwork. Loading errors retain the previous skin; an unavailable saved skin falls back to Yukio on startup. Native Windows validation and a public release are separate from local source and asset checks.
