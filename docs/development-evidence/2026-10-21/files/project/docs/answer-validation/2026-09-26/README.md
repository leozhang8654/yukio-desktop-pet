# 后台回答修复验证（2026-09-26）

修复：macOS 问题卡不再打开聊天、粘贴或模拟回车。Codex 用会话 IPC；Claude Code 用 PreToolUse AskUserQuestion 回答钩子；Deep Code 用可安装的本地接收适配器。发送时防重复，失败时保留输入、选项与重试能力。工具权限不会随问题答案被批准。

## 实际点击结果

由 Computer Use 点击同一个 QuestionPanel / QuestionCardView，调用同一发送实现；测试卡位于独立测试进程，避免触碰真实任务的发布选项。

| 检查 | 接收端 | 结果 | 前台与剪贴板 |
|---|---|---|---|
| Codex 已失效问题保护 | 真实正在运行的 Codex IPC | 拒绝发送，显示问题已结束或已回答 | Chrome 保持不变；剪贴板不变 |
| Codex 正常协议发送 | 本地协议测试服务器 | 正确线程、问题编号和答案；返回 turnId | Music 保持不变；剪贴板不变 |
| Claude Code 提问钩子 | 真实独立钩子进程 | 输出 updatedInput.answers，值为 YUKIO_TEST_OK | Chrome 保持不变；剪贴板不变 |
| DeepSeek 接收适配器 | 官方 Deep Code 0.4.1 SessionManager + 本地模拟模型 | 用户答案存入会话，isAnswers=true；模型流程继续 | Chrome 保持不变；剪贴板不变 |

原始测试回执在此目录。未使用任何测试去批准发布、删除或其他真实任务。

## 未验证范围

- **不能据此宣称 Codex 真实待答题的正常提交已端到端通过**：正常提交使用协议测试服务器，真实 Codex 只验证连接与失效题拒绝。
- Claude Code 线上测试返回 `Not logged in · Please run /login`，所以只确认钩子回传，没有确认线上模型继续运行。
- DeepSeek 使用本地模拟模型，没有用用户真实 DeepSeek 账号执行线上请求。
- 普通 ChatGPT / Claude / DeepSeek 网页与 Claude 普通桌面聊天没有接入；支持入口详见随包 BACKGROUND-ANSWERS.md。

## 自动检查与交付

- Swift 回归：171 项通过（移除旧模拟键盘发送器及其 8 个过时测试）；包含会话匹配、重复答题、阻塞请求格式、Claude 多题、配置保留和重试区域。
- DeepSeek 适配器：3 项通过；校验答案入会话才确认、保留计划模式、不代批工具权限，以及缺少连接时退回原流程。
- Deep Code 官方 CLI 的固定版本加适配器构建成功。
- macOS release 构建及应用签名校验通过。

桌面 Yukio.app 更新执行文件和后台回答资源，保留原有动画素材。Claude 设置更新前保留备份。测试窗口已关闭，测试模式仅包含在 DEBUG 构建中，不进入正式包。

实测过程中曾同时留下多张测试窗口，出现叠放；已经关闭，并修正测试窗口的动态尺寸及成功后自动退出。正式问题卡由应用控制器管理位置和尺寸。
