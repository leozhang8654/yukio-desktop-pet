# 雪绪 · 桌面宠物（DeepSeek / Windows 版）

白发蓝眼的管家少女“雪绪”待在 Windows 桌面右下角，跟着 **DeepSeek 的 Deep Code CLI** 当前在做的事切换动作：思考、读文件、看图片、写文件、跑测试、查网页、递交回答；其余工作坐在电脑前敲键盘，出错时沮丧，要你拿主意时立起问号卡，答完举起勾选卡，没有任务时空闲。每个动作都在小幅、连续地动（写字、敲键盘、转头、眨眼），头顶的小气泡显示当前任务和进度。

素材、活动映射、防抖与保持时间都和 macOS 版（`../YukioPlayer`，Swift）一模一样，换掉的是两头：**读谁的会话记录**（Deep Code 而不是只有 Claude Code）和**用什么画窗口**（Windows 分层窗口而不是 AppKit）。

只依赖 Pillow 一个库。窗口、托盘、菜单都用 ctypes 直接调 Windows API，没有别的界面框架。

## 跑起来

需要 Windows 10 或更新、Python 3.9 或更新（安装时勾上「Add python.exe to PATH」）。

```bat
git clone https://github.com/leozhang8654/yukio-desktop-pet
cd yukio-desktop-pet\YukioWin
pip install pillow
python run.py
```

雪绪出现在屏幕右下角，任务栏托盘里多一个她的小头像。想要一个能直接双击、别人不用装 Python 的 `Yukio.exe`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-exe.ps1
```

打出来的是 `dist\Yukio.exe`（约 25 MB，素材已经打包进去）。没有 Windows 开发环境时，也可以在 GitHub 的 Actions 里跑「打包 Windows 版雪绪」，下载它产出的 exe。

## 操作

| 想干什么 | 怎么做 |
| --- | --- |
| 挪位置 | 按住她拖。拖动时会换成原版的左右跑动，松手回到当前动作，位置会记住 |
| 出菜单 | 在她身上右键（或双击），也可以左键点托盘里的小头像 |
| 换大小 | 菜单 › 大小（100% / 125% / 150% / 200%）。高分屏会自动再乘一次屏幕缩放，不糊 |
| 暂停跟随 | 菜单 › 跟随 AI 活动。关掉后她保持空闲，但事件照收，重新打开立刻跟上 |
| 收起气泡 | 菜单 › 头顶显示任务 |
| 换跟随对象 | 菜单 › 跟随对象（自动 / 只跟 Deep Code / 只跟 Claude Code） |
| 看看效果 | 菜单 › 播放模拟演示：60 秒走一遍所有状态，不是真实活动 |
| 退出 | 菜单 › 退出雪绪 |

再次双击 `Yukio.exe` 不会开出第二只，而是让已经在跑的那只弹出菜单。

设置存在 `%LOCALAPPDATA%\Yukio\settings.json`（位置、大小、跟随开关）。

## 她从哪里知道 DeepSeek 在做什么

### 默认：Deep Code 的本地会话记录（只读，零配置）

[Deep Code](https://api-docs.deepseek.com/quick_start/agent_integrations/deepcode/) 是 DeepSeek 文档里给出的终端版编码助手（`npm i -g @vegamo/deepcode-cli`，命令 `deepcode`）。它把每个项目的会话存在：

```
%USERPROFILE%\.deepcode\projects\<项目码>\
    sessions-index.json     会话列表：标题、状态（processing / ask_permission / failed …）
    <会话 ID>.jsonl         消息记录，一行一条
```

雪绪只读这两样：从 `.jsonl` 里看角色、时间、工具名与参数、工具有没有报错、`UpdatePlan` 的任务清单；从 `sessions-index.json` 里看标题，以及“正在等你批准 / 已中断 / 本轮失败”这些只写在索引里的状态。**不写入、不修改 Deep Code 的任何文件，也不需要改它的设置。** 对话内容不会被保存或上传——气泡里只出现文件名、命令的前几个词和网址域名。

这是 Deep Code 在本地写的会话记录，不是公开 API，字段可能随版本变化；解析不动时只会少事件、不会崩，按失联规则回空闲。

### 也认 Claude Code 的转录

把 Claude Code 指到 DeepSeek 的 Anthropic 兼容端点时（`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`），跑的是 DeepSeek 模型，写出来的还是 Claude Code 格式的转录（`%USERPROFILE%\.claude\projects`）。这一路照样跟得上，菜单里可以指定只跟其中一个。

### 通用收件箱：别的工具也能驱动她

往 `%LOCALAPPDATA%\Yukio\inbox.jsonl` 里追加 JSON（一行一个），雪绪就会照做：

```json
{"kind": "task_start", "session": "build", "detail": "重构登录页"}
{"kind": "activity_start", "id": "t1", "tool": "edit", "input": {"file_path": "a.py"}}
{"kind": "activity_end", "id": "t1"}
{"kind": "final_answer"}
{"kind": "task_end"}
```

字段说明见 `yukio/bridge.py` 开头。`scripts\yukio-notify.py` 是给 Deep Code 的 `notify` 用的现成脚本（在 `~/.deepcode/settings.json` 里写 `"notify": "C:\\Users\\你\\.deepcode\\yukio-notify.py"`）——平时用不上，它一轮只响一次，远不如直接读会话记录细；留着是为了万一 Deep Code 换了记录格式，至少“任务结束 / 出错”还在。

## 活动映射

| 状态 | 动作 | Deep Code 的来源 | Claude Code 的来源 |
| --- | --- | --- | --- |
| `thinking` | A 托腮思考 | 任务进行中且没有工具在跑；`reasoning_content`；`UpdatePlan` | 同左；TodoWrite、Task*、计划模式 |
| `read_file` | B 桌前读书 | `read`；只读 shell 命令（cat、rg、ls、git status…） | Read、Glob、Grep |
| `view_image` | B 放大镜检查 | `ReadImage`、`UnderstandImage`；截图类 MCP | Read 图片文件 |
| `write_file` | B 纸上书写 | `write`、`edit`；写入类命令（重定向、sed -i、cp、git commit…） | Write、Edit、MultiEdit |
| `verify` | B 对照检查 | 测试／检查命令（pytest、npm test、cargo test…） | 同左 |
| `read_web` | B 平板浏览 | `WebSearch`；curl／wget；浏览器类 MCP | WebFetch、WebSearch |
| `respond` | B 递交报告 | 没有工具调用、只有正文的助手消息 | `end_turn` 文本 |
| `task_complete` | C 展示勾选卡 | 接在递交报告后面 | 同左 |
| `question_for_user` | C 立起问号卡 | `AskUserQuestion`；索引状态 `ask_permission`（等你批准）、`waiting_for_user` | AskUserQuestion |
| `default_work` | 稳定电脑桌 | 其他一切工作（构建、装依赖、`skill`、未知 MCP…） | 同左 |
| `failed` | 沮丧 | 工具结果 `"ok": false`；索引状态 `failed`。中断和拒绝授权不算失败 | 工具报错；API 报错 |
| `idle` | 基础待机 | 没有进行中的任务；失联回退 | 同左 |

分类规则在 `yukio/classify.py`，逐条有测试；拿不准时回电脑桌，不会把任意命令当成测试。

## 自查（在 Windows 之外也能跑）

```sh
python run.py --selftest                     # 72 个测试：路由、防抖、分类、解析、跟随、播放器逻辑
python run.py --check                        # 加载并裁切全部素材，确认帧不越界
python run.py --snapshot out.png             # 把实际使用的动画画在棋盘格上
python run.py --bubble out.png               # 画几种头顶气泡，检查排版、截断与位置
python run.py --replay samples/deepcode-session.jsonl --with-bubble
python run.py --watch 60                     # 实时跟随，打印事件与状态切换（不打印对话内容）
```

`--replay` 会自认会话记录是 Deep Code、Claude Code 还是收件箱格式。仓库里的 `samples/deepcode-session.jsonl` 是一份编出来的样例（不含任何真实对话），可以直接拿来看一轮完整的状态序列。

## 结构

```
yukio/events.py            事件协议（任务开始／结束／失败、活动开始／结束／失败、思考、回答、任务清单）
yukio/router.py            会话隔离、焦点选择、防抖、最短保持、合并窗口、失联回退、气泡内容
yukio/classify.py          工具 → 活动与简短说明（Deep Code 与 Claude Code 两套工具名 + shell 分词）
yukio/parsers_deepcode.py  Deep Code 消息与会话索引 → 事件
yukio/parsers_claude.py    Claude Code 转录 → 事件
yukio/bridge.py            通用收件箱的事件格式
yukio/sources.py           只读跟随会话目录、收件箱
yukio/tailer.py            按字节跟文件、切出完整 JSON（半行会等下一次读）
yukio/catalog.py           动画索引与帧时间线（读 macOS 版同一份 activities.json / motion.json）
yukio/sprites.py           图条 → 逐帧位图，用到才解码，最近 4 段留在内存
yukio/bubble.py            头顶气泡的排版与绘制（Pillow）
yukio/win32.py             分层窗口、托盘、菜单、消息循环（ctypes）
yukio/app.py               主循环、拖动、菜单动作、设置
tests/                     72 个测试；tests/fake_win32.py 把窗口层换成替身，逻辑在任何平台都能测
scripts/                   打包（PyInstaller）、Deep Code 的 notify 脚本
Resources/Yukio.ico        exe 的图标（从 macOS 版的封面图裁的）
```

素材不另存一份：默认用仓库里 `../YukioPlayer/Resources/Assets`（七套活动图条、电脑桌、基础动作、生成的小幅动作）。打包时会被复制进 exe。想换别处的素材可以设环境变量 `YUKIO_ASSETS`。

## 已知限制

- **窗口层没有在真机上跑过。** 我（写这版的 Claude）手边只有 macOS：核心逻辑、解析、路由、气泡排版、播放器主循环都有自动测试（窗口层用替身），素材和气泡是用 `--snapshot`／`--bubble` 出图目测的；但 `yukio/win32.py` 里真正的分层窗口、托盘图标、右键菜单只在 Windows 上才会执行。第一次在 Windows 上跑，请从源码跑（`python run.py`），窗口出不来时终端会打出完整报错。
- Deep Code 把一批工具调用的结果攒到全跑完才写进会话记录，所以同一批里几个很短的调用可能只看到最后一个的结束时间；单个工具的开始是实时的。
- 会话记录不是公开 API，Deep Code 升级后字段可能变。变了的话 `--replay` 一份新记录就能看出来解析还准不准。
- 素材是 192×208 的 1 倍图，放大到 150%／200% 时是插值放大，会略软。
- 应用没有数字签名，Windows SmartScreen 第一次可能拦一下（「更多信息」→「仍要运行」）。
- macOS 版在 `../YukioPlayer`（Swift，跟随 Claude Code），两边互不影响。
