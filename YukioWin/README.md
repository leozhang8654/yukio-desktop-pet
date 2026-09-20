# 雪绪 · 桌面宠物（DeepSeek / Windows 版）

白发蓝眼的管家少女“雪绪”待在 Windows 桌面右下角，跟着 **DeepSeek 的 Deep Code CLI** 当前在做的事切换动作：思考、读文件、看图片、写文件、跑测试、查网页、递交回答；其余工作坐在电脑前敲键盘，出错时沮丧，要你拿主意时立起问号卡，答完举起勾选卡等你——举着牌子时点她一下就把牌子放下（跟的是桌面版 Claude 的聊天时还会跳回那条聊天），那条聊天要是已经开在你眼前就不举牌了，没有任务时空闲。同时开着好几个聊天时，谁答完、谁在等你拿主意就先显示谁，其余的挂成一叠小卡压着气泡往上叠、点一张就去那条聊天，也可以在菜单里挑定一条只跟它。每个动作都在小幅、连续地动（写字、敲键盘、转头、眨眼），头顶的小气泡显示当前任务和进度。

素材、活动映射、防抖与保持时间、焦点规则、举牌与那摞卡、被拎起来时的晃动参数，都和 macOS 版（`../YukioPlayer`，Swift）一模一样，换掉的是两头：**读谁的会话记录**（Deep Code 而不是只有 Claude Code）和**用什么画窗口**（Windows 分层窗口而不是 AppKit）。两边仍有差别的只有大小控件（这边是档位、那边是滑条）与点击跳转的实测程度，都写在最后的「已知限制」里。

只依赖 Pillow 一个库。窗口、托盘、菜单都用 ctypes 直接调 Windows API，没有别的界面框架。

## 下载（不用装 Python）

到 [Releases](https://github.com/leozhang8654/yukio-desktop-pet/releases/latest) 下载 `Yukio-0.1.0-Windows.exe`（约 21 MB），放哪儿都行，双击就开。Python、Pillow、素材都打包在里面了，需要 Windows 10 或更新的 64 位系统。

第一次打开 Windows 可能弹蓝色的「Windows 已保护你的电脑」——这个程序没买代码签名证书，点「更多信息」→「仍要运行」，以后不再问。

## 从源码跑

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
| 挪位置 | 按住她拖。拖动时像被一只看不见的大手拎着后领，按单摆晃：往右拖脚落在左后方，停下荡过竖直线再收住，猛地往上提会先坠下去再弹回来。松手晃停后回到当前动作，位置会记住 |
| 点她一下 | 举着勾选卡时：放下牌子（那一轮结束了）；立着问号卡时：卡不收，问题还等你答。跟的是桌面版 Claude 的聊天时，两种都会顺手跳回那条聊天（见下面「点一下跳回聊天」） |
| 出菜单 | 在她身上右键（或双击），也可以左键点托盘里的小头像 |
| 换大小 | 菜单 › 大小：50% / 75% / 100% / 125% / 150% / 175% / 200% 七个整档，再加「放大一点 / 缩小一点」各 ±5%，能停在 50%–200% 之间任何一个整 5%。高分屏会自动再乘一次屏幕缩放，不糊 |
| 暂停跟随 | 菜单 › 跟随 AI 活动。关掉后她保持空闲，但事件照收，重新打开立刻跟上 |
| 收起气泡 | 菜单 › 头顶显示任务 |
| 收起别的聊天 | 菜单 › 头顶显示别的聊天。关掉后只剩气泡，不再叠小卡 |
| 换跟随对象 | 菜单 › 跟随对象（自动 / 只跟 Deep Code / 只跟 Claude Code） |
| 挑一条聊天跟 | 菜单 › 跟随的聊天。默认「自动（完成和提问优先）」：谁答完、谁在等你拿主意就先显示谁，都没有时跟最近在干活的那条；点一条聊天就挑定它，别的聊天再忙也抢不走，挑定只在这次运行内有效 |
| 看看效果 | 菜单 › 播放模拟演示：60 秒走一遍所有状态，不是真实活动（第一次打开且两个工具都没装时会自动演一遍） |
| 退出 | 菜单 › 退出雪绪 |

再次双击 `Yukio.exe` 不会开出第二只，而是让已经在跑的那只弹出菜单。

设置存在 `%LOCALAPPDATA%\Yukio\settings.json`（位置、大小、跟随开关、显示气泡与小卡）。

> macOS 版那边「大小」是一条 50%–200% 的滑条，拖着走当场变大变小。Win32 的托盘菜单是系统原生弹出菜单，塞不进滑条，所以这边换成七个整档加 ±5% 的两条，范围和步进一样，只是要多点几下。

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

## 多个聊天同时跑：跟哪一条

一只雪绪同一时刻只**显示**一条聊天（不然动作会互相串），其余有话要说的挂成小卡贴在气泡上面。

默认**自动**，顺序按档位，越靠前越先显示（和 ChatGPT 桌面版那只宠物的排法一致）：

1. **等你回答**的（问号卡）
2. **整轮出错停住**的
3. **答完举着勾选卡**的
4. 都没有时，跟**还在干活**的那条：它没停就不换，停了、被中断或失联，才换到最近有动静的另一条

同一档里先给最近的那条；处理掉一条，下一条自己露出来。头顶气泡显示的是**那条聊天**的标题，一眼能看出是谁答完了。

**答完了就一直举着牌子**：不再是停 8 秒自己放下，而是举到你点她一下为止（或者那条聊天开始新一轮、被中断、记录被删）。举着的牌子被晾满 15 分钟还没人点，就先让位给还在干活的聊天——牌子不放下，等那条也停下来时再举回来，列表里那条写「举着牌子等你（先让位了）」。答完的那一刻她哪怕正跟着别的聊天，这块牌子也会先举起来存着，不会丢掉那一轮的完成提示。

**头顶那摞小卡**：她正显示的那条不出卡（气泡已经在讲它），其余的一条一张，压着气泡往上叠，最要紧的那张挨着气泡。卡上是聊天名 + 此刻在干什么 + 右边一个短标签（等你回答／出错／答完了／在跑），左边一条同色的竖条。最多叠 3 张，其余折进「还有 N 条」，点它展开。点卡正文＝去那条聊天并收起这张，点 ✕＝只收起（那条聊天下一轮有动静时会再来），在卡上右键＝这条聊天本次运行内不再出卡。菜单 › **头顶显示别的聊天** 可以整个关掉。

菜单 › **跟随的聊天** 可以自己挑一条：第一条是「自动（完成和提问优先）」；下面列最近半小时内的聊天，最多 10 条，按同一套档位排（等你回答 → 出错 → 答完 → 在跑 → 按安静时间），每条显示聊天名（记录里的会话标题，没有就用请求第一行）和它此刻在干什么；标题里顺带报数（有几条等你／有几条在跑）。点一条就挑定它：立刻切过去，别的聊天再忙也抢不走；挑定的那条停下来时她就空闲等着。挑定只在这次运行里有效，重开回到自动。命令行 `--chats` 可以先看一眼这份列表。

## 点一下跳回聊天

举着勾选卡或立着问号卡时点她一下（或点头顶那摞里的一张卡），会用**桌面版 Claude 自己注册的深链**打开那条聊天：

```
claude://code/continue?session=local_…
```

转录里的会话 ID（`~/.claude/projects/*/<会话>.jsonl` 的文件名）和桌面版的会话 ID 不是一个，对应关系在桌面版自己的记录里，**只读、不写**：

```
%APPDATA%\Claude\claude-code-sessions\<账号>\<组织>\local_<id>.json   里面的 cliSessionId
```

`python run.py --chat-link <会话ID>` 可以先查一条对不对得上。这是桌面版的内部记录、不是公开接口，可能随版本变化；**对不上时就只把牌子放下，不乱跳到别的聊天**。

在终端里跑的 Claude Code、以及 **Deep Code（DeepSeek）的会话本来就没有这种链接**——那些聊天跑在终端里，点了只是把牌子放下。这套跳转在 macOS 版上实测过；Windows 上的路径与协议是照桌面版同一套写的，没有在 Windows 上实机验证过。

## 自查（在 Windows 之外也能跑）

```sh
python run.py --selftest                     # 129 个测试：路由、防抖、分类、解析、跟随、聊天选择、卡叠、摆动、播放器逻辑
python run.py --check                        # 加载并裁切全部素材，确认帧不越界
python run.py --snapshot out.png             # 把实际使用的动画画在棋盘格上
python run.py --bubble out.png               # 画几种头顶气泡，检查排版、截断与位置
python run.py --cards out.png                # 画“气泡 + 上面那摞别的聊天”，收起与展开各一格
python run.py --hang out.png                 # 被拎着的五个倾角并排，并自查摆动方向（方向反了就非零退出）
python run.py --replay samples/deepcode-session.jsonl --with-bubble
python run.py --watch 60                     # 实时跟随，打印事件与状态切换（不打印对话内容）
python run.py --chats 3                      # 列出最近的聊天，→ 标出此刻会跟哪条
python run.py --chat-link <会话ID>           # 查这条聊天对应桌面版 Claude 的哪一条（点牌子跳哪去）
```

`--replay` 会自认会话记录是 Deep Code、Claude Code 还是收件箱格式。仓库里的 `samples/deepcode-session.jsonl` 是一份编出来的样例（不含任何真实对话），可以直接拿来看一轮完整的状态序列。

## 结构

```
yukio/events.py            事件协议（任务开始／结束／失败、活动开始／结束／失败、思考、回答、任务清单）
yukio/router.py            会话隔离、焦点选择（等你回答／出错／答完举牌优先，可挑定一条）、举着的牌子、
                           防抖、最短保持、合并窗口、失联回退、气泡内容、聊天列表与那摞卡
yukio/cards.py             一张通知卡的内容与档位（等你回答 → 出错 → 答完 → 在跑）
yukio/cardstack.py         那摞卡的排版与绘制（Pillow，和气泡共用一套外观）
yukio/hang.py              被大手拎着时的单摆晃动与那张图的窗口几何（纯逻辑，可用虚拟时钟测）
yukio/chatlinks.py         转录会话 → 桌面版 Claude 的那条聊天（只读它的记录，给出 claude:// 深链）
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
tests/                     129 个测试；tests/fake_win32.py 把窗口层换成替身，逻辑在任何平台都能测
scripts/                   打包（PyInstaller）、Deep Code 的 notify 脚本
Resources/Yukio.ico        exe 的图标（从 macOS 版的封面图裁的）
```

素材不另存一份：默认用仓库里 `../YukioPlayer/Resources/Assets`（七套活动图条、电脑桌、基础动作、生成的小幅动作）。打包时会被复制进 exe。想换别处的素材可以设环境变量 `YUKIO_ASSETS`。

## 已知限制

- **和真的 Deep Code 对过一次**：2026-09-17 在本机装上 `@vegamo/deepcode-cli` 0.4.0，用一个本地假模型（说 OpenAI 流式协议，不连 DeepSeek 的服务器、不需要密钥）驱动它真跑了一轮「读文件 → 回答」，然后拿雪绪去跟它写下的会话记录：`--replay` 解析无误，`--watch` 实时跟随依次走出 思考 → 阅读 hello.txt → 递交报告 → 勾选卡 → 空闲，事件写入延迟 30–80 ms。字段与这里写的完全一致（`messageParams.tool_calls`／`reasoning_content`、`tool_call_id`、结果 JSON 里的 `ok`）。它发给模型的工具名实测是 bash、read、write、edit、WebSearch、UpdatePlan、skill、UnderstandImage／ReadImage，分类规则都认。
- **"聊天已开在眼前就不举牌"这条在 Windows 上没实测过**：判断分两半——读桌面版的会话记录找出此刻选中哪条聊天（这半边在 macOS 上实测过，`--open-chat` 能当场查，两边用的是同一份记录、同一个 `lastFocusedAt` 字段），以及判断桌面版 Claude 是不是真在最前面（`win32.foreground_process_name()`，只有 Windows 上才跑得到，按 `Claude.exe` 比对）。后半边和 `chat_url` 的深链一样，是照桌面版的同一套写的，没在 Windows 上验过。任何一步取不到都退回**照常举牌**，不会因此少提醒。
- **实机验到哪一步**：每次构建都会在 GitHub 的 Windows 机器（Windows Server 2025）上把打好的 exe 真跑一遍——枚举出雪绪、气泡、那摞卡、宿主四个窗口，核对尺寸与 `WS_EX_LAYERED`（只有一条聊天时那摞卡是隐藏的 1×1 窗口），确认她按造出来的 Deep Code 会话显示「纸上书写 · 编辑 login.py」，再截屏、拿屏幕上的像素和图条逐点比（100% 与 150% 两种缩放，最近一次是 98.6% 与 99.9%，门槛 90%）。没覆盖到的是人手才能试的部分：托盘菜单点开长什么样、拖动手感、多显示器、资源管理器重启、非整百的系统缩放。这些出问题时，先从源码跑 `python run.py`，终端里有完整报错（双击 exe 时报错写在 `%LOCALAPPDATA%\Yukio\error.log`）。
- 窗口类名是进程内注册的，所以 `FindWindow("YukioPet")` 在别的进程里找不到她（要用 `EnumWindows` + `GetClassName`，`scripts/smoke-test.ps1` 就是这么做的）。
- Deep Code 把一批工具调用的结果攒到全跑完才写进会话记录，所以同一批里几个很短的调用可能只看到最后一个的结束时间；单个工具的开始是实时的。
- 会话记录不是公开 API，Deep Code 升级后字段可能变。变了的话 `--replay` 一份新记录就能看出来解析还准不准。
- 素材是 192×208 的 1 倍图（被拎起来那张是 192×240），放大到 150%／200% 时是插值放大，会略软。
- **被拎起来时只有一帧、不眨眼**：`held.png` 是单帧图，晃动是绕抓手点的实时旋转，但人物本身不动。
- **点一下跳回聊天只在 macOS 上实测过**：Windows 上桌面版 Claude 的记录位置与 `claude://` 协议注册是照同一套写的，没有在 Windows 上实机验过；对不上时只放下牌子，不乱跳。
- **大小是七个整档 + ±5%，不是滑条**：macOS 版菜单里能塞一条 50%–200% 的滑条，Win32 的原生弹出菜单塞不进去，要完全一致得另开一个设置窗口。范围与 5% 的步进两边一样。
- 应用没有数字签名，Windows SmartScreen 第一次可能拦一下（「更多信息」→「仍要运行」）。
- macOS 版在 `../YukioPlayer`（Swift，跟随 Claude Code），两边互不影响。
