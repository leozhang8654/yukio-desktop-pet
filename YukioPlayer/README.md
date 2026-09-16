# 雪绪桌面播放器（Claude 兼容版）

一只雪绪，根据 **Claude Code** 当前在做的事自动切换动作：七类活动各有动作，其余工作显示电脑桌，出错时沮丧，没有任务时空闲。每个动作都在小幅、连续地动（写字、敲键盘、转头、眨眼），头顶的小气泡显示大任务、当前任务和进度。
原生 Swift / AppKit，只需 Xcode Command Line Tools，无第三方依赖。

## 构建与运行

```sh
cd YukioPlayer
swift test                     # 52 个核心测试（路由、防抖、分类、解析、文件跟随、资源、气泡文字、动作时间线）
./scripts/build-app.sh         # 生成 build/Yukio.app（资源已打包进应用）
open build/Yukio.app
```

运行后：屏幕右下角出现雪绪；菜单栏出现她的小头像。菜单里有当前状态、跟随的会话、模拟演示、暂停跟随、头顶显示任务、大小、回到右下角、退出。

菜单的三个入口（任一可用即可）：

1. 菜单栏小头像。首次运行默认放在靠右处（距右边缘约 260 点）；按住 ⌘ 拖动可换位置，系统会记住。
2. 在雪绪身上右键（或 control-点击）。
3. 再次打开 Yukio.app（Finder、Spotlight 或 `open build/Yukio.app`）：菜单在雪绪身旁弹出。

刘海屏菜单栏装满时，macOS 会把放不下的图标挤到刘海下或屏幕外（本机实测：只写文字“雪绪”时被挤到 x=0，完全不可见）。改为头像并靠右放置后可见，但会把最左边的另一个图标挤进刘海。可在“系统设置 › 菜单栏”里关掉不需要的图标腾出位置。

无窗口的检查模式（开发时可用 `swift run YukioPlayer <参数>`）：

| 参数 | 作用 |
| --- | --- |
| `--check` | 加载并裁切全部资源，确认帧不越界 |
| `--snapshot out.png` | 把实际使用的动画画在棋盘格上（帧多的均匀抽 10 帧），检查裁切与透明边缘 |
| `--bubble out.png` | 按 2 倍分辨率画几种头顶气泡样例，检查排版、截断与位置 |
| `--replay 会话.jsonl` | 用虚拟时钟回放一份 Claude 转录，打印雪绪会显示的状态序列；加 `--with-bubble` 同时打印气泡文字（含标题与文件名） |
| `--watch 秒数` | 实时跟随 Claude 转录，打印事件、写入延迟和状态切换（不打印对话内容） |
| `--demo` | 启动后立即播放模拟演示 |

## 活动映射

| 状态 | 动作 | Claude Code 来源 |
| --- | --- | --- |
| `thinking` | A 托腮思考 | 任务进行中且没有工具在执行（模型在生成）；TodoWrite、Task*、计划模式、ToolSearch |
| `read_file` | B 桌前读书 | Read（非图片）、Glob、Grep；只读 shell 命令（cat、sed -n、rg、ls、git status/diff…） |
| `view_image` | B 放大镜检查 | Read 图片文件；MCP 截图类工具 |
| `write_file` | B 纸上书写 | Write、Edit、MultiEdit、NotebookEdit；写入类命令（重定向到文件、sed -i、cp、mv、mkdir、git commit…） |
| `verify` | B 对照检查 | 测试／检查命令（swift test、pytest、npm test、cargo test、`*verify*`/`*test*` 脚本…） |
| `read_web` | B 平板浏览 | WebFetch、WebSearch；浏览器类 MCP；curl/wget |
| `respond` | B 递交报告 | 最终回答（`end_turn` 文本）；递出一次后停住，任务结束后保持 8 秒再回空闲 |
| `default_work` | 稳定电脑桌 | 其他一切工作（构建、安装依赖、Agent、Skill、未知 MCP…） |
| `failed` | 沮丧（基础图条 `failed`，垂眼一次后停住） | 工具报错（非零退出、编辑找不到原文、文件不存在…）：下一个工具开始就接替，最多 4 秒后回思考；API 报错导致本轮中止：停留 8 秒再回空闲。拒绝授权、中断不算失败 |
| `idle` | 基础待机 | 没有进行中的任务；等待用户回答（AskUserQuestion）；失联回退 |

拖动时使用原版左右跑动，松手回到当前活动。分类规则见 `Sources/YukioCore/ClaudeToolClassifier.swift`，有限且逐条有测试；无法确定时回电脑桌，不会把任意命令当成测试。

## 动作

原来每套动作的 4 帧是分别生成的画，整幅线条（连桌腿、椅子）都有 1 像素级漂移，轮播就会“呼吸抽搐”，所以只能长时间停在一帧上。现在每个状态只用其中一张已确认的底图，由 `tools/motion/make_motion.py` 生成连续动作，桌椅逐像素不动（生成时自动检查桌腿一带零变化）：

- 手、笔、放大镜、纸这类要明显移动的东西，从部件内部的点往外选到描边为止，抠成一层单独平移、旋转（2–5 像素），原位置用四周像素补齐；
- 头、眼这类只动 1–2 像素的，用局部平滑变形；
- 每帧 33–67 ms（写字 30 帧/秒，敲键盘、平板、读书 20 帧/秒）。

| 状态 | 动作 |
| --- | --- |
| `thinking` | 托腮，头绕着托下巴的手慢慢歪一点又回来，偶尔往上看，慢眨眼（幅度最小） |
| `read_file` | 指着书的手沿一行从左划到右，读完回到行首，视线和头跟着 |
| `view_image` | 拿放大镜的手带着镜片在照片上方来回扫，微微走弧线，手腕跟着转 |
| `write_file` | 握笔的手一边写笔画、笔杆跟着摆，一边往右移，写完一行回到左边 |
| `verify` | 在两份文件之间左右转头，正在看的那份手指顺着往下点着核对 |
| `read_web` | 手指在平板上往上划两下（翻页），停一会儿，眼睛跟着往下扫 |
| `default_work` | 两只手轮流抬起、敲下，在键位间左右挪，节奏不齐，敲一阵停一下 |
| `respond` | 先整理文件：后面两张没对齐的纸伸在外面，拿着整叠在桌上磕两下、慢慢对齐；然后停住只眨眼，不来回递纸 |
| `idle` | 偶尔向左、向右看一看，头跟着歪，眨眼 |
| `failed` | 垂眼一次后停住，慢慢叹气、慢眨眼 |

所有状态都会眨眼：眼皮用各自姿势脸颊的肤色，闭眼线用各自睫毛的颜色。要改动作或幅度，编辑 `tools/motion/make_motion.py` 里对应的函数后重新运行（需要 numpy、opencv-python、Pillow），图条写到 `Resources/Assets/motion/`；`--parts`、`--eyes`、`--sheet`、`--html` 分别画部件蒙版与补齐背景的检查图、眨眼检查图、局部变形对照图和新旧动作并排的预览页。删掉 `Resources/Assets/motion/motion.json` 就回到原来的图条。

## 头顶气泡

雪绪头顶的小气泡最宽 180 点、两行字，有任务时淡入，没有任务时淡出；菜单“头顶显示任务”可以关掉。

| 位置 | 内容 | 来源 |
| --- | --- | --- |
| 上行（标题） | 大任务 | Claude 的会话标题（桌面版的会话名或 CLI 自动标题）；没有标题时用这一轮请求的第一行 |
| 下行 | 当前任务 | Claude 任务清单（TaskCreate／TaskUpdate 或 TodoWrite）里“进行中”的一项 |
| 下行（没有清单时） | 当前活动 | 正在进行的工具调用：`编辑 main.swift`、`$ swift test`、`浏览 developer.apple.com`、`等你回答`… |
| 右侧数字与底部细条 | 任务进度 | 清单中已完成／总数；一批全部完成后又新建任务时从头算 |

文字跟着雪绪正在显示的动作变（已防抖），不会抢在动作前面；同一动作里细节变得太快时（连续读几个文件），每段文字至少停留 1.2 秒。出错时显示“出错：那次调用”，回答后显示“已回答”。气泡只显示文件名、命令前几个词和网址域名，不显示文件内容；点击会穿透到后面的窗口。

## 结构

```
Sources/YukioCore/            与界面无关，可完整测试
  Events.swift                事件协议（task_start/end/abort/failed、activity_start/end/failed、thinking、final_answer、source_lost、session_title、todo_list/update）
  ActivityRouter.swift        会话隔离、焦点选择、防抖、最短保持、合并窗口、失联回退、气泡内容
  ClaudeToolClassifier.swift  Claude 工具 → 活动与简短说明
  ClaudeParsers.swift         转录行 → 事件；hooks JSON → 事件；任务清单；JSON 流切分
  LiveSources.swift           只读跟随 ~/.claude/projects；可选 hooks 收件箱
  Catalog.swift / SpriteTimeline.swift / HeldValue.swift / DemoScript.swift
Sources/YukioPlayer/          macOS 窗口、头顶气泡、拖动、菜单栏、命令行模式
Resources/Assets/            从接续包复制的最终素材（七套活动、电脑桌、基础动作）
Resources/Assets/motion/     生成的小幅动作图条与 motion.json（覆盖同名动画）
tools/motion/                动作生成脚本（Python：底图 + 局部平滑变形 + 眨眼）
integrations/claude-hooks/   可选的官方 hooks 接入（默认未启用）
```

## 调度参数（`RouterConfig`，均为待调起点）

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `debounceMs` | 400 | 候选状态稳定这么久才切换 |
| `minHoldMs` | 1500 | 每个显示状态至少保持这么久 |
| `toolGraceMs` | 3500 | 工具结束后仍算作该活动，合并连续同类调用（真实转录中调用间隔多为 2–4 秒） |
| `respondLingerMs` | 8000 | 回答后“递交报告”停留时间 |
| `failedHoldMs` | 4000 | 工具失败后沮丧最多显示多久（下一个工具开始就接替），之后回思考 |
| `failedLingerMs` | 8000 | 本轮因 API 报错中止后沮丧停留时间，然后回空闲 |
| `staleNoToolMs` / `staleOpenToolMs` | 10 分钟 / 30 分钟 | 无事件多久视为失联，回空闲 |

多个会话同时工作时只跟随一个：当前会话仍在进行就不换；它结束、被中断或失联后，才换到最近有动静的会话。

## 事件来源

### 默认：会话转录（只读，零配置）

读取 `~/.claude/projects/<项目>/<会话>.jsonl`（尊重 `CLAUDE_CONFIG_DIR`）。只读、不修改 Claude 的任何文件或设置。启动时回放最近 15 分钟内活跃会话的末尾，恢复“此刻在做什么”。

注意：这是 Claude Code 在本地写的会话记录，**不是公开 API**，格式可能随版本变化；解析失败时只会少事件，不会崩溃，并按失联规则回空闲。子代理（sidechain）的活动不驱动主角色。

### 可选：Claude Code 官方 hooks

更正式的接口，但需要修改 `~/.claude/settings.json`，因此默认没有启用。启用方法：

1. `mkdir -p ~/Library/Application\ Support/YukioPlayer && cp integrations/claude-hooks/yukio-hook.sh ~/Library/Application\ Support/YukioPlayer/`
2. 把 `integrations/claude-hooks/settings-snippet.json` 中的 `hooks` 合并进 `~/.claude/settings.json`（已有 hooks 时逐项合并，不要覆盖）。

脚本只把 hook 输入追加到收件箱文件、不输出、始终退出 0，不会阻塞 Claude。两个来源可以同时开启：同一工具调用 ID 会去重。hooks 不带会话标题，只开 hooks 时气泡标题用请求的第一行。

## 已知限制

- 素材为 192×208 的 1 倍图，在 Retina 屏上是放大显示，会略软；更清晰需要从 `sources/` 高分辨率源图重新提取 2 倍图。
- 动作是底图上的小幅变形，只适合 2 像素以内的移动；翻页、换姿势这类大动作需要重新画图。
- 思考块在消息完成后才写入转录，所以“思考”是推断的（任务进行中且无工具在跑）；最终回答也在写完后才出现，流式输出期间显示思考。
- 气泡的任务清单是从转录重建的：启动时每个会话只回放最后 1 MB，很长的会话里较早建立的任务可能漏掉，进度会少算，直到 Claude 再次更新清单。
- 会话标题由 Claude 生成，一个会话里换了新请求时标题不一定跟着变。
- 主循环 30 Hz（动作一帧 33–67 ms），本机实测 CPU 约 1%；图条要显示时才解码，最近用过的 4 段留在内存里，内存约 45 MB。
- 应用为本机临时签名；分发给他人需要正式签名与公证。
