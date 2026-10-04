# 在雪绪卡片里后台回答 / Background answers

点选项或输入答案后，雪绪在后台提交，保持当前页面和前台应用不变。发送期间禁止重复点击；连接失败保留答案，可以重试。辅助功能权限不是这些后台通道的前提。只有主动点「打开聊天」才跳转。

## 支持范围与连接方式

| 入口 | 后台回答方式 | 设置 |
|---|---|---|
| GPT：Codex macOS 桌面版、本机活动任务 | 同一 macOS 用户的 Codex IPC；发送前核对会话、问题和状态 | 保持 Codex 运行，无需辅助功能 |
| Claude Code 的 AskUserQuestion | 官方 PreToolUse 钩子把答案填入 updatedInput.answers | 雪绪菜单 →「连接 Claude 后台回答」，然后重启 Claude Code |
| DeepSeek：Deep Code CLI 0.4.1 | 随包适配器接入 SessionManager，保留正常终端界面和工具授权 | 按下方说明安装，通过 yukio-deepseek 启动 |

这些不是通用网站自动点击器。ChatGPT 网页、Claude 普通聊天网页/桌面聊天、DeepSeek 网页和未接入适配器的第三方客户端目前没有后台发送通道；不能把识别到问题等同于已经连接回答。无法发送时会明确显示未连接，不会复制后假装成功或强制切换页面。Claude Code 的钩子不代表 Claude 普通桌面聊天已支持。

Codex 使用桌面应用的内部 IPC，升级后可能需要更新适配。当前卡片展示提问数组中的第一题；多题的阻塞式 request_user_input 请在原聊天完成，卡片不会错发一条普通消息来代替整组答案。

## Claude Code

安装按钮只合并 `AskUserQuestion` 的钩子，保留其他 hooks、模型和权限配置。配置位置遵从 `CLAUDE_CONFIG_DIR`，默认 `~/.claude/settings.json`；修改前自动备份到 `~/Library/Application Support/YukioPlayer/claude-settings-before-answers-*.json`。

保持雪绪运行、跟随 Claude（或全部）、开启问题卡。未开启时，新提问直接退回 Claude 原有流程；雪绪中途退出或停止跟随后，钩子也会退回。每组最多等待约 9.5 分钟，多题按顺序在卡片回答。回执表示钩子已接收答案；模型继续运行还取决于 Claude 登录和服务状态。不会替用户同意 Bash、文件修改等工具权限。

官方接口：[Claude Code hooks](https://code.claude.com/docs/en/hooks)。

## DeepSeek / Deep Code

需要 macOS、Node.js 22+、Git 和原有 Deep Code 模型配置。先用雪绪菜单的「安装 DeepSeek 回答适配器」安装；GUI 自动识别 Homebrew 或官方安装器的 Node，也可以使用下面的手动命令。应用 Resources 中的 `deepseek-answers`（源码中 `YukioPlayer/integrations/deepseek`）包含安装器与适配器：

```sh
cd "/path/to/Yukio.app/Contents/Resources/deepseek-answers"
node setup.mjs
```

安装器从 [Deep Code 官方源码仓库](https://github.com/lessweb/deepcode-cli)固定提交 `d370f3afe0391e22e22667479c5425efb3a14b5f` 构建单独的 CLI，添加本地回答接收器；不覆盖原有 `deepcode` 命令、不改模型账号、不自动授权工具。默认安装位置：

```sh
"$HOME/Library/Application Support/YukioPlayer/deepseek-runtime/yukio-deepseek"
```

在要工作的项目目录运行上述命令。新会话的提问可在雪绪回答；已经通过其他终端或 VS Code 启动的会话不能被这个适配器接管。没有 DeepSeek 账号或模型配置时，雪绪不会代建账号或假装模型已经接收。

## English

Option clicks and typed replies use background transports; they do not activate the target app, paste into a window, or press Return globally. Failed sends remain retryable. Supported clients are local Codex desktop tasks, Claude Code AskUserQuestion hooks, and the supplied isolated Deep Code CLI adapter. Ordinary provider websites and unconnected clients are not supported. Claude hook receipts confirm local hook delivery, not subsequent model execution. The Deep Code adapter preserves tool permissions and plan mode. The menu provides Claude hook installation and this setup guide.
