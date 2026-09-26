# Changelog / 更新记录

## 0.3.1 — 2026-09-26

- Both platforms recognize the selected Codex desktop chat from local view diagnostics. Only that chat suppresses its completion card; background conversations retain their reminders.
- Focus is checked against the running process; switching apps clears the selection immediately. Missing or stale diagnostics keep reminders enabled.
- Windows reads view logs off the animation thread and fixes 64-bit foreground-window/process handle declarations.
- 双平台同步最新 Codex「当前聊天不举完成牌」修复，并增加切换聊天、多个窗口、后台任务、日志续读和重启回归测试。

## 0.3.0 — 2026-09-25

- Personal assistant windows on macOS and Windows: Home, Reminders, Personalization and planned Extensions. / 双平台个人助手主窗口：首页、提醒、个性化与规划中的扩展。
- Local one-time reminders with edit/delete, five-minute snooze, completion, restart recovery and catch-up after sleep. Closing the main window keeps reminders running. / 本地单次提醒支持编辑、删除、稍后五分钟、确认完成、重启恢复和唤醒补提醒；关闭主窗口继续运行。
- Windows ships Tk with the exe, adds a pet size slider and show/hide controls, and persists personalization and card switches. / Windows EXE 自带 Tk，补齐桌宠大小滑条、显隐和个性化持久化。
- Codex async questions stay visible while other tools run, clear on structured replies, and use Codex deep links on Windows. Duplicate submissions and stale delivery callbacks are ignored; foreground and clipboard changes stop automatic input. / Codex 异步问题持续显示、结构化回答后收起，Windows 使用 Codex 深链；防止重复送出与旧回调，前台或剪贴板变化时停止自动输入。
- Add packaged assistant UI tests and post-release verification of the public Windows download. / 增加打包助手界面测试及公开下载包发布后复测。
- AI, screen observation, automatic activity records and briefings remain design proposals. / AI、屏幕观察、自动记录与简报仍为设计规划。

## 0.2.2 — 2026-09-25

- Keep the head and neck stationary in all twelve states while preserving hand and prop motion. / 十二种状态固定头颈，保留手部和道具动作。
- Move both irises together within fixed eye openings; preserve independent blinking and remove iris remnants during full blinks. / 固定眼角与眼睛开口，双眼同步转动，保留独立眨眼并去除闭眼残留。
- Redraw the entire transparent macOS pet surface after animation, resizing, dragging and backing changes. / macOS 动画、缩放、拖动和显示环境变化后重绘完整透明画面。
- Ship the same updated animation assets on macOS and Windows, with pixel-identical runtime pages. / 两个平台同步更新动画与逐像素一致的运行时分页。
- Refresh English and Chinese documentation, previews, download links and historical document locations. / 更新中英文文档、预览、下载链接与历史资料路径。

## 0.2.1

Answer pending questions from the card beside Yukio, with foreground checks before sending. / 在雪绪身边的问题卡直接作答，发送前检查目标应用是否在前台。

## 0.2.0

Reviewed component animations, independent eyelids and low-memory artwork paging on both platforms. / 双平台同步已验收的小部件动画、独立眼皮和低内存素材分页。
