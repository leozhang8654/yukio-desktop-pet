# 待机隐身 / Hide when idle

设置 → 显示 → **待机时隐身**，默认开启；开关记住本机选择。

- 空闲时隐藏雪绪、任务气泡和聊天卡片，不占鼠标点击区域。菜单栏／托盘仍可打开设置。
- 继续读取助手活动；进入工作、提问、完成举牌或出错状态时自动现形，沿用已有状态防抖，保持原位置。
- 完成牌保留到用户放下；放下后没有工作和提醒便再次隐身。
- 拖拽、松手后的摆动、演示期间保持可见；支持抛掷互动的开发版本也会等待互动结束。
- 「收起雪绪」仍是手动隐藏，工作不会强行打开。选择「显示雪绪」会在本次待机期间保持可见，下一轮工作后恢复自动隐身。
- 关闭此开关恢复空闲常驻。暂停跟随后视为空闲；隐身不影响任务读取或提醒计时。

## 验证

macOS 的 `IdleVisibilityTests` 使用隔离偏好、注入事件和真实 AppKit 窗口，验证启动待机、工作往返、子窗口隐藏、开关、手动收起／显示、拖拽、演示、提问、完成及失败提醒。

Windows 的 `test_idle_visibility.py` 验证相同行为和设置持久化，使用窗口替身；在 macOS 上执行不构成 Windows 原生窗口或 EXE 的实机验收。

## 发布状态（2026-10-18 核对）

待机隐身已随 [v0.4.6](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.6) 发布，源码见 [b2fceaf](https://github.com/leozhang8654/yukio-desktop-pet/commit/b2fceaf92c735bbdfdaa490cd07289667555e75c)。上述测试描述保留本地开发阶段的范围；后续公开版的 Windows 原生与下载复验见[0.4.6 验证记录](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/validation/plugin-signs-0.4.6.md)。

本地开发目录另有带抛掷互动的实现；抛掷仍未发布，不能用公开版待机隐身的验证代替它的 Windows 验收。历史 0.4.4 桌面候选与当前实际运行程序不是同一状态，本次未检查桌面运行版本。
