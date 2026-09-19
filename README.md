# 雪绪 · 桌面宠物（Claude Code 版）

白发蓝眼的管家少女“雪绪”待在 macOS 桌面右下角，跟着 **Claude Code** 当前在做的事切换动作：思考、读文件、看图片、写文件、跑测试、看网页、递交回答；其余工作坐在电脑前敲键盘，出错时沮丧，要你拿主意时立起问号卡，答完举起勾选卡等你——举着牌子时点她一下就跳回那条聊天，没有任务时空闲。同时开着好几个聊天时，谁答完、谁在等你拿主意就先显示谁，其余的挂成一叠小卡压着气泡往上叠、点一张就去那条聊天，也可以在菜单里挑定一条只跟它。每个动作都在小幅、连续地动（写字、敲键盘、转头、眨眼），头顶的小气泡显示当前任务和进度。

原生 Swift / AppKit，只需要 Xcode Command Line Tools，没有第三方依赖。

## 下载（不用编译）

到 [Releases](https://github.com/leozhang8654/yukio-desktop-pet/releases/latest) 下载对应的那个：

| 系统 | 文件 | 怎么开 |
| --- | --- | --- |
| macOS 13 或更新 | `Yukio-0.1.0-macOS.zip`（约 6 MB） | 解压后把 `Yukio.app` 拖进「应用程序」，按下面放行一次 |
| Windows 10/11（64 位） | `Yukio-0.1.0-Windows.exe`（约 21 MB） | 直接双击。第一次可能弹「Windows 已保护你的电脑」，点「更多信息」→「仍要运行」 |

macOS 版跟随 Claude Code，Windows 版跟随 DeepSeek 的 Deep Code CLI（也认 Claude Code）。下面先讲 macOS；Windows 的说明见 [YukioWin/README.md](YukioWin/README.md)。

`Yukio-0.1.0-macOS.zip` 是 Apple 芯片与 Intel 通用二进制，需要 macOS 13 或更新。

第一次打开会被系统拦下：「Apple 无法验证“Yukio”是否包含可能危害 Mac 安全或泄漏隐私的恶意软件」。这是因为它只有本机临时签名、没有做苹果公证（要 Apple 开发者账号），不是因为它做了什么。放行一次，以后正常双击：

1. 双击 `Yukio.app`，在提示框上点「完成」；
2. 打开「系统设置 › 隐私与安全性」，往下滚到「安全性」一栏，会看到一行“已阻止使用「Yukio」…”，点右边的「仍要打开」，在弹窗里再点一次并输入密码。

macOS 15 起，右键→「打开」这个老办法已经不能绕过 Gatekeeper，只能走上面的系统设置。用终端也可以一行解决：

```sh
xattr -dr com.apple.quarantine /Applications/Yukio.app
```

自己编译出来的 `Yukio.app` 不带隔离标记，不会有这个提示。

打开后雪绪出现在屏幕右下角，菜单栏多一个她的小头像。菜单有三个入口：菜单栏小头像、在雪绪身上右键、再次打开 `Yukio.app`。退出也在菜单里。

## 自己编译

```sh
cd YukioPlayer
swift test                     # 核心测试
./scripts/build-app.sh         # 生成 build/Yukio.app
open build/Yukio.app
./scripts/package-release.sh   # 打发布用的通用二进制压缩包 dist/Yukio-<版本>-macOS.zip
```

默认只读本机的 Claude Code 会话记录（`~/.claude/projects`），不修改 Claude 的任何文件或设置；点击跳转另外只读桌面版 Claude 的会话记录，用它自己注册的深链打开那条聊天。活动映射、头顶气泡、动作生成、事件来源与调度参数见 [YukioPlayer/README.md](YukioPlayer/README.md)。

## Windows / DeepSeek 版

同一只雪绪也有 Windows 版，跟随 **DeepSeek 的 Deep Code CLI**（`deepcode`，DeepSeek 文档里给的终端版编码助手），也能跟 Claude Code——把 Claude Code 指向 DeepSeek 的 Anthropic 兼容端点时同样有效。素材、活动映射、防抖与保持时间、焦点规则、举着的勾选卡、头顶那摞别的聊天、被大手拎着的晃动，都和 macOS 版一样，换掉的是读谁的会话记录和用什么画窗口（Windows 分层窗口，逐像素透明）。两边只剩两处不同：那边「大小」是一条滑条、这边是七个整档加 ±5%（Win32 的原生菜单塞不进滑条）；点一下跳回聊天只在 macOS 上实机验过。

```bat
cd YukioWin
pip install pillow
python run.py
```

也可以用 `scripts\build-exe.ps1` 打成一个 `Yukio.exe` 发给别人双击。细节、活动映射与已知限制见 [YukioWin/README.md](YukioWin/README.md)。

## 目录

| 路径 | 内容 |
| --- | --- |
| `YukioPlayer/` | 播放器工程：源码、测试、打包进应用的素材与应用图标、动作与图标生成脚本（`tools/motion/`、`tools/icon/`）、打包与发布脚本（`scripts/`） |
| `YukioWin/` | Windows / DeepSeek 版播放器（Python + ctypes，只依赖 Pillow）：跟随 Deep Code 与 Claude Code 的会话记录，共用同一套素材 |
| `assets/` | 最终透明素材：七套活动图条、电脑桌、问号卡与勾选卡底图、基础动作 |
| `sources/` | 高分辨率生成源图（洋红底，需要抠图后使用） |
| `references/` | 动作总览、平板修正图、生成提示词、图片清单 |
| `native-current/` | Codex 内置宠物用的单宠物图集快照，仅供参考 |
| `preview.html` | 可离线打开的手动预览页 |
| `HANDOFF.md` | 需求、用户反馈与进度记录 |
| `START_HERE.md`、`PLAYER_REQUIREMENTS.md`、`CONTINUE_PROMPT.txt` | 最初的接续包说明（写于播放器实现之前，“尚未实现”等描述已过时） |
