# 雪绪 · 桌面宠物（Claude Code 版）

白发蓝眼的管家少女“雪绪”待在 macOS 桌面右下角，跟着 **Claude Code** 当前在做的事切换动作：思考、读文件、看图片、写文件、跑测试、看网页、递交回答；其余工作坐在电脑前敲键盘，出错时沮丧，没有任务时空闲。每个动作都在小幅、连续地动（写字、敲键盘、转头、眨眼），头顶的小气泡显示当前任务和进度。

原生 Swift / AppKit，只需要 Xcode Command Line Tools，没有第三方依赖。

## 快速开始

```sh
cd YukioPlayer
swift test                 # 核心测试
./scripts/build-app.sh     # 生成 build/Yukio.app
open build/Yukio.app
```

默认只读本机的 Claude Code 会话记录（`~/.claude/projects`），不修改 Claude 的任何文件或设置。活动映射、头顶气泡、动作生成、事件来源与调度参数见 [YukioPlayer/README.md](YukioPlayer/README.md)。

## 目录

| 路径 | 内容 |
| --- | --- |
| `YukioPlayer/` | 播放器工程：源码、测试、打包进应用的素材、动作生成脚本（`tools/motion/`） |
| `assets/` | 最终透明素材：七套活动图条、电脑桌、基础动作 |
| `sources/` | 高分辨率生成源图（洋红底，需要抠图后使用） |
| `references/` | 动作总览、平板修正图、生成提示词、图片清单 |
| `native-current/` | Codex 内置宠物用的单宠物图集快照，仅供参考 |
| `preview.html` | 可离线打开的手动预览页 |
| `HANDOFF.md` | 需求、用户反馈与进度记录 |
| `START_HERE.md`、`PLAYER_REQUIREMENTS.md`、`CONTINUE_PROMPT.txt` | 最初的接续包说明（写于播放器实现之前，“尚未实现”等描述已过时） |
