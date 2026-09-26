# 0.3.2 整体测试记录

2026-09-26，功能代码 `ef094c3`。仅本轮已执行的检查记为通过。

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| Windows 核心与播放器回归 | 219 项通过；macOS 本地和 Windows runner 各运行一轮 | 三种编码助手解析、聊天路由、问题卡、输入保护、提醒存储／恢复、设置持久化、启动项状态、窗口播放器逻辑 |
| macOS Swift 测试 | 172 项通过 | 解析、状态路由、提醒、剪贴板／前台保护、渲染边界、右键和 Control-click、启动项接口、问题卡状态 |
| 动画深度检查 | 12 个常规动作全部通过 | 固定头颈区域、循环衔接、透明度、眨眼合成、眼角固定、双眼视线、帧间连续性 |
| 素材清单 | 通过 | 51 个源素材文件、13 段可播放动画 |
| macOS 发布 ZIP | 通过 | 解压后严格签名检查、0.3.2 版本、arm64 / x86_64 通用二进制、内置素材 |
| macOS 界面 | 通过 | 设置页截图；问题卡布局、选项、输入、发送、关闭和打开聊天的命中区域 |
| Windows 实际 EXE | 29 项检查通过 | 原生右键打开小设置、置顶标志、切换到助手、登录启动注册／删除、提醒新增／编辑／响铃／稍后／完成／删除、关闭主窗口继续提醒、重开窗口、个性化保存 |
| Windows 桌宠画面 | 100% / 150% 尺寸通过 | 原生透明窗口、尺寸、会话状态及屏幕像素；两档匹配率均为 100% |

[Windows 构建、测试和截图记录](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/36272447929)。该 runner 是 Windows Server 2025；没有把它表述为所有 Windows 10/11 设备的实机覆盖。

## 可重复执行

```sh
swift test --package-path YukioPlayer
python3 YukioWin/run.py --selftest
python3 YukioWin/run.py --check
python3 scripts/verify_package.py
python3 YukioPlayer/tools/motion/check_motion.py --before YukioPlayer/Resources/Assets/motion --after YukioPlayer/Resources/Assets/motion --out YukioPlayer/build/motion-check
python3 YukioPlayer/tools/motion/check_gaze.py --before YukioPlayer/Resources/Assets/motion --after YukioPlayer/Resources/Assets/motion --out YukioPlayer/build/gaze-check
```

动画检查需要 Pillow、NumPy、OpenCV 和源码内的 approved animation rig。`build-windows.yml` 构建并运行真实 EXE；`verify-windows-release.yml` 在发布后重新下载公开 EXE，核对 SHA-256，并复测 29 项界面流程及 100% / 150% / 200% 桌宠尺寸。发布后结果链接随版本 Release 说明更新。

## 测试边界

- Windows 登录启动的实测使用独立临时名称注册当前测试 EXE，完成或失败后删除；没有替用户开启启动项。macOS 登录项接口使用依赖注入验证，未在本机切换真实登录项。
- 真实注销／重新登录、全屏 App、多个显示器及全部系统 DPI 组合尚未覆盖。桌宠尺寸倍率不等于系统 DPI 倍率。
- Codex 真实页面切换与问题表单提交尚未做端到端实测。模拟按键完成并不表示服务端已经接收答案；自动输入会在前台应用或剪贴板变化时停止。
- AI API、屏幕监测、新闻和日历是规划功能，不计入已实现功能的测试通过范围。
