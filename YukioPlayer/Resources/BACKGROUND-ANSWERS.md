# 在雪绪里回答问题、处理批准申请

开发中的 0.4.4：现有 GPT、Claude、DeepSeek 三个选择同时用于对应的本机连接和可识别的网页／插件申请。正式下载版仍以 GitHub Release 为准。

有申请时，雪绪显示问号牌。点卡片选项后，先打开完整申请，用户看完再选择。回车、关闭和“稍后处理”不会批准。发送前再次核对申请，过期或内容改变就停止；不会把“允许一次”变成“以后都允许”。看不清、接不上或无法确认收到时，保留提示并请用户到原聊天核对。

## 接入范围

| 入口 | 当前实现 | 验证边界 |
|---|---|---|
| GPT / Codex 本机活动聊天 | 原有问题回答；命令、文件修改和权限申请 | 已有后台连接的聊天才能收到。插件与 App 不是必然共用一条连接 |
| Claude Code | AskUserQuestion 和 PermissionRequest | 需安装雪绪连接后重启 Claude Code；不是普通 Claude 聊天的通用接口 |
| DeepSeek / Deep Code 0.4.1 | 问题回答、当前工具申请允许／拒绝 | 需通过随包单独入口启动，并保留自己的模型配置 |
| Chrome 的 GPT / Claude 官方插件，以及 ChatGPT、Claude、DeepSeek 网页 | 读取页面上真实存在的批准卡片和按钮，用户选择后回传 | 仅可识别的结构与按钮；不能保证每种网页版本或其他第三方 App 通用。没有按钮、只有“我将申请”的文字不会举批准牌 |
| GPT 插件的普通问题回答 | macOS 在后台连接不可用时，尝试匹配当前聊天名称、完整问题和专门的提交按钮 | 不向普通聊天输入框盲发；匹配不唯一、题目已结束、已有其他草稿则停止。真实插件往返尚待验证 |

macOS 网页／插件方式需要辅助功能权限；Windows 使用 UI Automation，可读性由目标软件决定。两个系统都不移动鼠标、不向当前任意输入框敲字。跨屏读取不依赖当前正在使用哪个屏幕。网页／插件识别目前属于实验功能，不能把底层检查通过写成所有真实服务已经测试通过。

## Claude 连接

雪绪设置中的连接按钮会合并 `PreToolUse / AskUserQuestion` 与 `PermissionRequest`，保留其他钩子和权限规则，修改前备份配置。然后重启 Claude Code。

macOS 默认配置在 `~/.claude/settings.json`，也遵从 `CLAUDE_CONFIG_DIR`。Windows 同样遵从该配置位置，连接通过打包的雪绪程序处理，不需要额外安装 Python。Windows 备份在 `%LOCALAPPDATA%/Yukio`，macOS 在 `~/Library/Application Support/YukioPlayer`。

保持雪绪运行、跟随对应助手并开启问题卡。未连接或雪绪退出时，退回 Claude 原有流程，不会自动允许。每次最多等待约 9.5 分钟。回执说明本地程序收到选择，不代表后续任务一定成功。Claude 未发出 PermissionRequest 的申请不属于此通道，例如某些独立的网络权限提示。

依据：[Claude Code hooks](https://code.claude.com/docs/en/hooks)。

## DeepSeek 连接

需要 Node.js 22+、Git，以及原有 Deep Code 模型配置。使用雪绪中的 DeepSeek 连接／安装按钮，会从[官方仓库](https://github.com/lessweb/deepcode-cli)固定版本 `d370f3afe0391e22e22667479c5425efb3a14b5f` 构建单独入口，不覆盖原来的 Deep Code。今后从该入口启动需要连接的聊天：

- macOS：`~/Library/Application Support/YukioPlayer/deepseek-runtime/yukio-deepseek`
- Windows：`%LOCALAPPDATA%/Yukio/deepseek-runtime/yukio-deepseek.cmd`

拒绝时保留 Deep Code 的拒绝状态；允许时只允许当前卡片列出的申请，不授予长期权限。已在其他终端启动的聊天不能自动接管。

## 回答框与断线

macOS 小回答框直接支持 Command-V、Command-C、Command-X、Command-A、撤销，无需先打开助手窗口。发送失败保留原文。如果回复可能已经发出但回执丢失，会提示到原聊天核对，避免自动重复发送。
