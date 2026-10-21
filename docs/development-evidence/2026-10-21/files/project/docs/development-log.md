# 开发过程与证据索引

整理日期：**2026-10-18**。这是根据 Git、GitHub PR / Release / Actions 和已有报告补充整理的历史说明，不是当时逐日撰写的日志。本次只核对记录与文档，没有重新运行应用测试、构建安装包或检查当前桌面进程。下文测试数字均归属于引用的历史版本。

## 项目解决什么问题

Yukio 把编码助手的本地活动变成桌面上可见的角色动作、任务气泡和完成／提问提醒，帮助用户知道助手正在做什么、何时需要自己处理。macOS 与 Windows 共用动作素材，分别实现原生窗口；已接入 Claude Code、Codex 和 Deep Code 的活动来源。回答和批准通过对应连接处理，未知或无法确认的聊天不猜测发送目标。

## 当前进度

| 工作项 | 实现状态 | 验证与交付状态 | 下一步 |
| --- | --- | --- | --- |
| 三类助手活动、十二种状态、问题卡与完成提醒 | 已实现 | 已发布；见 0.1–0.4 系列记录 | 随上游格式变化补回归 |
| 后台回答、应用内更新 | 已实现 | 已发布；有协议、原生升级和公开下载验证记录 | 继续区分协议测试与真实服务往返 |
| 千夏皮肤、待机隐身、批准卡、插件聊天定位 | 已实现 | 随 0.4.6 已发布；部分人工场景待验证 | 补真实新任务放牌与点牌返回原标签页 |
| 抛掷、屏幕反弹、落地晕眩 | 已实现（本地） | 未发布；本地 macOS 有验证记录，Windows 原生待验证 | 完成人工抛接与 Windows 验收，再决定接入发布线 |
| 独立助手页面与本地提醒 | 已实现（历史） | 0.3.0 曾发布；0.3.3 起正式入口暂停 | 如恢复入口，重新核对提醒生命周期 |
| AI 个性化、屏幕观察、自动活动记录、简报 | 计划中 | 未找到完整实现和发布记录 | 按设计拆分可验证的小范围任务 |
| 当前桌面实际运行版本 | 待核实 | 0.4.6 报告记录了当时与公开 Mac 包一致；本次未检查运行进程 | 需要时单独核对进程、版本和包内哈希 |

**状态口径：**“计划中”仅有设计；“进行中”已开展但目标未实现；“已实现”有源码或资源；“已验证”必须附环境、对象、结果和范围；“已发布”表示存在公开 Release 与附件；“受阻”需要写明无法继续的具体条件。“待验证／待核实”是证据缺口，不自动等于受阻。一个功能可以同时是“已发布”和“某些场景待验证”。

## 本次核对的基准与边界

- GitHub 默认分支 `main`：[460fb19](https://github.com/leozhang8654/yukio-desktop-pet/commit/460fb1935966ef2c3472a0bfa661fe90836e5855)。查询覆盖其 103 条提交、18 个 PR 和 19 个公开 Release；当前可见的普通 Issue 为 0，不代表过去所有问题都没有记录。查询入口：[提交历史](https://github.com/leozhang8654/yukio-desktop-pet/commits/main/)、[所有 PR](https://github.com/leozhang8654/yukio-desktop-pet/pulls?q=is%3Apr)、[所有 Issue](https://github.com/leozhang8654/yukio-desktop-pet/issues?q=is%3Aissue)、[Releases](https://github.com/leozhang8654/yukio-desktop-pet/releases)。
- 最新公开版本：[v0.4.6](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.6)，发布时刻为 **2026-10-14 04:20:54 UTC**。下文阶段范围按 Git 提交／PR 的 UTC 时间归纳，CHANGELOG 的发布日期统一使用 Release `published_at` 的 UTC 日期。旧文档中的本地日期可能早一天；旧 0.4.0 条目的 10-07 是开发阶段日期，公开发布为 10-10，二者不混用。
- 当前本地分支为 `release/v0.2.1`，HEAD 为 `b176e1e38eb65cee94d4045cf7e94ffa045bb9a4`，并有大量既有未提交源码、素材与文档。它不是最新发布源码的干净副本，不能用本地版本号或此 HEAD 代表所有工作文件。公开证据尽量链接到固定提交；本地独有证据明确标识，不杜撰远程链接。
- 0.4.6 应用源码标签指向 [d0de8c1](https://github.com/leozhang8654/yukio-desktop-pet/commit/d0de8c13b0f0e237adbe18c26db4bb0634a48e83)；Windows 构建为 [f1bad3c](https://github.com/leozhang8654/yukio-desktop-pet/commit/f1bad3ced85ad9faf846e782508f549cc460ae37)；下载复验工具所在提交为 [0de15d5](https://github.com/leozhang8654/yukio-desktop-pet/commit/0de15d53c1de6d45bbc5609b872b29636675f9e5)。[PR #17](https://github.com/leozhang8654/yukio-desktop-pet/pull/17) 限制差异只能涉及文档、测试及截图检查器，应用代码、打包配置和素材须一致。不能简写为“所有包都来自同一提交”。
- [发布附件 validation.json](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/v0.4.6/validation.json) 和 [SHA256SUMS.txt](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/v0.4.6/SHA256SUMS.txt) 已读取核对；附件列出 macOS / Windows 包及来源。本次没有重新下载大体积程序并复测，历史公开包复验结果来自下列 Actions。
- PR 正文也可能停留在旧阶段：#10、#14 仍有“草稿／尚未发布”叙述，但之后已合并，相关能力已发布。判断最终状态采用合并元数据、后续记录与 Release，而不只看正文中的一句话。

## AI 活动观察升级：调查与 Stage 1.1（2026-10-18，本地未发布）

**问题。**研究指出的 Codex 共享失败标记在本地两个构造场景中确实错配/丢失失败。本地工作区与正在运行的 0.4.6 App 也不是可直接认定相同的源码基线。

**修改。**Swift/Python 改为按有依据的调用身份关联；保留未关联、未知、取消和冲突结果。新增结果元数据和本地诊断导出，继续复用现有桌宠路由；没有加入持久历史或云端服务。

**验证。**最终 Swift 196 项通过；Python 在 macOS 上运行 306 项，305 项通过、1 项 Windows 命名管道测试跳过。33 个共享场景的 57 条导出记录逐字段一致；3 份真实本机日志的 141 条结果两端一致，不能据此声称覆盖了全部操作。首次回归与集成失败及修复过程见专项记录。

**结果与下一步。**本地已实现并完成上述验证，未提交、推送、打包、发布或替换桌面 App。下一步是事件与完整记录游标的持久化事务，以及文件世代与重启恢复。发布前须先对齐实际发布源码，Windows 原生验证另做。

**证据：**[现状、技术取舍与分阶段记录](ACTIVITY-OBSERVATION.md)、[候选文件哈希与验证结果](validation/activity-observation-stage1-1/verification.json)。

## 阶段一：让一只桌宠跟随真实任务（2026-09-15—09-17）

**问题 → 修改。**最早可核实提交把 macOS 播放器、素材和 Claude Code 跟随接入仓库，随后将动作改成部件分层，并增加提问／完成牌。Windows 移植活动协议、路由和窗口，读取 Deep Code / Claude 本地记录，复用共享素材，避免维护两份动作资源。用户从静态角色获得可区分的工作状态与下载入口。

**验证 → 结果。**[PR #2](https://github.com/leozhang8654/yukio-desktop-pet/pull/2) 保存了 81 项逻辑测试、Windows runner 的窗口与截图检查，以及真实 Deep Code CLI 配合本地假模型的跟随检查。这里的假模型测试不是 DeepSeek 在线服务端到端验证。开发中遇到控制台中文编码、PyInstaller 兼容、窗口构造期间回调及 BOM 设置文件问题，修复提交保留在历史中。

**状态与下一步。**[v0.1.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.1.0) 已发布。Windows 在 09-17 补入；Release 初始发布日期为 09-16，不能据此声称 Windows 所有工作在 09-16 前完成。#2 当前仍 OPEN，但其正文明确说代码已进 main、基线用于补充审阅；不是等待功能合并。关闭该历史 PR 属于后续维护，本次未操作。旧 HANDOFF 提及 09-13 的 36 项测试，本次未找到对应独立原始运行报告，保留为历史叙述。

**证据：**[5b847c5](https://github.com/leozhang8654/yukio-desktop-pet/commit/5b847c55965268fa9bee1539abd371e859a2ddfe)（初始实现）、[9bc8318](https://github.com/leozhang8654/yukio-desktop-pet/commit/9bc8318af74baa93ee9ef6d45dc3d13520c852f9)（分层动作）、[710ca09](https://github.com/leozhang8654/yukio-desktop-pet/commit/710ca092e84e595b4cee0ea143389e95985b7a3c)（Windows）、[2580bb1](https://github.com/leozhang8654/yukio-desktop-pet/commit/2580bb1799c1e6bbd3ad24cdba9df2fd04dca3b9)（CLI 验证）、[PR #1](https://github.com/leozhang8654/yukio-desktop-pet/pull/1)、[PR #2](https://github.com/leozhang8654/yukio-desktop-pet/pull/2)、[早期交接](HANDOFF.md)。

## 阶段二：动作验收、多助手与跨平台播放（2026-09-19—09-23）

**问题 → 修改。**完成牌曾定时消失，多聊天状态不够清楚，动画存在动作语义、轮廓和内存占用问题。加入持续完成提醒、聊天卡叠、拖拽悬挂摆动和 Auto 多助手跟随；逐轮修订十二种部件动作，眼皮使用独立时钟，运行时用分页读取素材。

**选择与失败修复。**保留人物和手持关系，只动局部部件。round_13 原有评审记录指出 `verify` 的核验动作曾不明显，修订后解除强制退回；`respond` 仍略像展示纸张，作为非阻断问题保留。高分屏修图中曾误删提起姿态的蝴蝶结，后续单独补回，不把重做素材写成一次成功。

**验证 → 结果。**引用的历史独立评审为 **94/100**、无强制退回项，包含逐状态三循环与连续切换检查；这是已有评审结论，本次未重新评审。0.2.0 Release 记载 Windows 155 项测试与原生截图验证。缩放测试不能推导出覆盖所有系统 DPI、多屏和设备。

**状态与下一步。**[v0.2.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.2.0) 已发布；后续固定头颈和眼睛修复属于下一阶段，不能用 round_13 分数代表所有后续素材。

**证据：**[8e77bb9](https://github.com/leozhang8654/yukio-desktop-pet/commit/8e77bb948037eea93e1bd5c7efc70d0281f59fe9)（提醒与悬挂）、[99e4d58](https://github.com/leozhang8654/yukio-desktop-pet/commit/99e4d581071436faefbf01667072d7387c92badb)（蝴蝶结修复）、[37e8694](https://github.com/leozhang8654/yukio-desktop-pet/commit/37e86947322eb7a56bd38ca04c21a4b558861df9)（动画与眼皮分页）、[PR #3](https://github.com/leozhang8654/yukio-desktop-pet/pull/3)、[原评审](animation-review/round_13/independent-review.md)、[蒙版拓扑](animation-review/round_13/mask-topology.json)、[0.2.0 Windows 运行记录](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/35831190853)。

## 阶段三：直接回答、固定头颈与眼球修复（2026-09-25—09-26）

**问题 → 修改。**0.2.1 引入问题卡直接回答；其发送方案仍依赖前台检查。动画修复改为复用已验收的 2 倍源图、最终蒙版和补底，固定十二状态的头颈，保留手部／道具时间轴。眼球从整片眼区变形改成虹膜、瞳孔、高光一层平移，双眼共用限幅，避免眼角被拖动及闭眼蓝色残留；macOS 完整重绘透明画面以处理残影。

**失败与验证。**头颈记录保留了误用旧生成流程的废弃候选；新方案不再默认走 1 倍生成和超分。编码后检查记录十二状态固定区域变化为 0；眼睛专项记录眼框外像素变化为 0、161 张原生眼皮组合一致，139 项 Swift 测试通过。固定头颈单独试验当时没有 Windows／Intel 实机结果，不能拿后续发布替早期试验补写测试。

**状态与下一步。**[v0.2.1](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.2.1)、[v0.2.2](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.2.2) 已发布。回答权限和新记录格式问题直到 0.3.4 才进一步处理；未将早期模拟发送等同于真实接收。

**证据：**[f38f2a8](https://github.com/leozhang8654/yukio-desktop-pet/commit/f38f2a8f52fff69db4e53929d11685857a2824ec)、[a69997a](https://github.com/leozhang8654/yukio-desktop-pet/commit/a69997abea7cf6ac5146f7767b3dfbf801498b27)、[固定头颈记录](animation-review/neck-stability-sam/README.md)、[眼球修复](animation-review/gaze-fix/README.md)、[编码检查](animation-review/gaze-fix/gaze-validation.json)、[原生验证](animation-review/gaze-fix/native-verification.json)。

## 阶段四：助手试验、提醒生命周期与设置收敛（2026-09-26—10-03）

**问题 → 修改。**0.3.0 将单次提醒、稍后、完成、重启恢复与个性化带到两端；0.3.1 区分正在查看的 Codex 聊天与后台任务，减少重复完成提醒；0.3.2 增加默认关闭的登录启动、浮动小设置和按聊天／问题编号隔离的回答状态。0.3.3 新增大号取消举牌按钮、外部点击关闭设置，并暂停正式版独立助手页面入口。

**选择。**提醒数据独立于角色显示，问题状态按会话隔离，避免同编号串题；“暂停助手入口”与“从未实现提醒”是不同事实。暂停页面的完整决策过程未找到独立记录，不推测原因。

**验证 → 结果。**0.3.2 的既有报告记录 172 项 Swift、219 项 Windows 回归、29 项实际 EXE 界面流程及公开下载复测；Windows 来自 Windows Server 2025 runner，不是所有 Windows 10/11 用户设备。真实注销／登录、全部多屏组合等未覆盖。0.3.3 Release 另记载 173 项 macOS 与 224 项 Windows 测试。

**状态与下一步。**0.3.0–0.3.3 均已发布；助手主页面仍按暂停入口理解，AI、屏幕观察和简报仍属计划中。

**证据：**[1624d27](https://github.com/leozhang8654/yukio-desktop-pet/commit/1624d2775d7e0d532595074cec616fbc6f2ba688)、[ef094c3](https://github.com/leozhang8654/yukio-desktop-pet/commit/ef094c36030abb4cdd3a3bf9dd71be1e5f6b424d)、[8269b49](https://github.com/leozhang8654/yukio-desktop-pet/commit/8269b490d1623d41c05c4a5ed47aef89a668ed00)、[0.3.2 历史测试范围](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/TESTING.md)、[v0.3.2](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.2)、[v0.3.3](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.3)、[助手历史能力](ASSISTANT.md)、[后续设计](PERSONALIZATION.md)。

## 阶段五：回答可靠性、聊天辨认与可读性（2026-10-04—10-08）

**问题 → 修改。**旧桌面二进制仍使用模拟键盘发送，回答时反复请求权限；更换发送器后，又发现 canonical history 的旧 `turns` 数组为空，活跃问题被误判过期。0.3.4 两端转为后台 IPC，解析新旧记录格式，提交前核对线程、调用与问题，失败保留输入，匹配回执后才收卡。0.3.5 显示真实聊天标题；0.3.6 按助手着色，0.3.7 改白底顶部色线，0.3.8 加粗并向外延伸，0.3.9 让气泡、文字和点击区随角色缩放。

**验证 → 结果。**早期“拒绝失效题”通过并不能证明能发现活跃题。修正后本地报告记录原生问题卡向真实聊天发送诊断文本并收到对应结构化回复；这是自动化诊断，不是用户体验评价。[PR #4](https://github.com/leozhang8654/yukio-desktop-pet/pull/4) 另列 175 项 Swift、234 项本地 Windows/core 测试（含一项原生场景跳过），以及 Windows named-pipe 和打包 EXE 的协议验证；不能将这些全归为真实服务 UI 往返。0.3.9 PR 保留 179 项 Swift 和 Windows 打包截图检查的证据。

**状态与下一步。**0.3.4–0.3.9 已发布。后台回答不再要求 macOS 辅助功能权限，但浏览器聊天可见性识别仍需要该权限；两类用途不能混写。

**证据：**[4b14c41](https://github.com/leozhang8654/yukio-desktop-pet/commit/4b14c4131f9b099c3bbb6bdd5cc42cbe6ecc3330)、[PR #4](https://github.com/leozhang8654/yukio-desktop-pet/pull/4)、[本地修复与真实诊断记录](answer-validation/2026-10-04/README.md)、[PR #5](https://github.com/leozhang8654/yukio-desktop-pet/pull/5)、[PR #6](https://github.com/leozhang8654/yukio-desktop-pet/pull/6)、[PR #7](https://github.com/leozhang8654/yukio-desktop-pet/pull/7)、[PR #8](https://github.com/leozhang8654/yukio-desktop-pet/pull/8)、[PR #9](https://github.com/leozhang8654/yukio-desktop-pet/pull/9)、[cfb3d66](https://github.com/leozhang8654/yukio-desktop-pet/commit/cfb3d66234d952e481cd48891220c63f30f42694)。

## 阶段六：从手动换包到应用内更新（2026-10-08—10-10）

**问题 → 修改。**用户此前每次需要下载并替换程序。0.4.0 提供自动发现稳定版、查看说明、稍后、手动检查和确认后安装重启；macOS 使用 Sparkle 签名更新，Windows 使用 Velopack 安装目录并保留设置。旧版需先安装一次支持更新的版本。

**失败／阻塞 → 验证。**候选阶段曾受生产 Keychain 签名授权阻塞；后续记录明确生产签名成功，不能继续把 #10 正文中的旧阻塞当作现状。隔离升级测试覆盖拒绝无效 feed／损坏包、正常升级、重启和设置保留；最终发布源码的 Windows 248 项检查及公开安装包复验有独立运行记录。报告记录当时 Mac 下载包与桌面程序 254 个文件一致。更新签名不等于 Apple 公证或 Windows Authenticode 签名。

**状态与下一步。**[v0.4.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.0) 已发布；最新桌面版本需独立核实，不能把当时安装 0.4.0 的记录当作今天状态。

**证据：**[PR #10](https://github.com/leozhang8654/yukio-desktop-pet/pull/10)、[PR #11](https://github.com/leozhang8654/yukio-desktop-pet/pull/11)、[5ffc426](https://github.com/leozhang8654/yukio-desktop-pet/commit/5ffc426cfd2b9d00162ceb07d452266b4d58581b)、[候选与最终交付记录](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/update-validation/0.4.0/README.md)、[同源 Windows 构建／升级](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38017080549)、[公开安装包复验](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38017525626)。

## 阶段七：回答收牌、可见聊天与协作任务隔离（2026-10-10—10-12）

**问题 → 修改。**0.4.1 在收到答案回执或会话接收记录后立即放下问号牌，发送失败仍保留问题；0.4.2 在小设置加入退出按钮。0.4.3 修复 Mac 跨屏可见聊天、静读后识别失效、嵌套浏览器控件、透明 Dock 遮挡和 Claude 地址识别；两端分离协助任务身份，避免子任务先完成就遮住父任务动作。

**验证 → 结果。**[PR #13](https://github.com/leozhang8654/yukio-desktop-pet/pull/13) 记录 203 项 Mac 测试、265 项 Windows 测试与 Windows 环境安装升级、回传和显示检查；同时修复升级检查写死 0.4.2 的问题。Windows 仍使用前台窗口识别，不能宣称与 Mac 双屏遮挡判断相同。Intel 仅有通用包架构检查，没有该机器上的原生运行结论。

**状态与下一步。**0.4.1–0.4.3 已发布；插件原标签页、全屏重复节点等剩余问题进入下一阶段。

**证据：**[PR #12](https://github.com/leozhang8654/yukio-desktop-pet/pull/12)、[19c597b](https://github.com/leozhang8654/yukio-desktop-pet/commit/19c597bf4a171cc509a94aa12d61c7250f85bd99)、[PR #13](https://github.com/leozhang8654/yukio-desktop-pet/pull/13)、[02d5e3a](https://github.com/leozhang8654/yukio-desktop-pet/commit/02d5e3a32b6079ef1d9f3945953dfe0f7dff31b3)、[f010b12](https://github.com/leozhang8654/yukio-desktop-pet/commit/f010b128a98aa7993a156221aadc75325827b8b6)、[协作任务修复](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/HELPER-ACTIVITY-FIX.md)、[v0.4.3](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.3)。

## 阶段八：批准卡、千夏与插件聊天合并交付（2026-10-13—10-14）

**问题 → 修改。**批准请求需要完整内容和明确的一次性决定；插件聊天不能错跳桌面 App。加入批准卡、回答框粘贴、Windows UTF-8 回执和 Claude Hook 依赖修复；加入千夏十二种动作、专用提起姿态、连续拖动落点修复、默认待机隐身。随后缓存 GPT Chrome 插件的原标签页，去除全屏重复节点并补回较早聊天名称。可见聊天只确认完成提醒，不自动回答或批准。

**版本归属。**0.4.4、0.4.5 有候选文档，但本次未找到对应公开 Release 或标签；[v0.4.6](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.6) 明确将这些开发改动一起发布。不能仅凭 `docs/releases/0.4.5.md` 标题宣称已单独发布。

**验证与失败。**0.4.6 附件记录 Mac 219 项测试、13 段资源检查、arm64 实际运行与双架构包；外接屏 GPT 侧栏识别、收起／重开和原标签页记录有实际验证。Windows 截图检查曾只取前 12 帧误判静止像素，改为检查完整动画并补第 13 帧变化的回归，保持原 90% 阈值。后续构建第一次又因模拟外部点击失败，第二次原样运行通过；不能写成首次全过或证明偶发问题已根治。

| Windows 证据 | 实际状态 | 范围 |
| --- | --- | --- |
| [原截图检查失败](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38508472446) | 失败记录保留 | 静止像素判定错误；见 #16 修复 |
| [构建 attempt 1](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38509262054/attempts/1) | failure（本次 API 核对） | 模拟设置外部点击失败 |
| [构建 attempt 2](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38509262054) | success（本次 API 核对） | windows-latest；报告列 288 项检查、升级／设置保留、回传、两皮肤 100% / 150% 显示 |
| [公开包下载复验](https://github.com/leozhang8654/yukio-desktop-pet/actions/runs/38510920756) | success（本次 API 核对） | windows-latest；来源、安装、设置、回传及两皮肤 100% / 150% / 200% 显示 |

**状态与下一步。**已发布、已在上述范围验证。真实新一轮完成后“举牌→切回聊天自动放下”、亲手点角色返回原页、所有服务／插件／多屏的批准往返仍待验证。Windows runner 是真实 Windows 自动检查，不能替代全部用户设备人工验收。

**证据：**[PR #14](https://github.com/leozhang8654/yukio-desktop-pet/pull/14)、[PR #15](https://github.com/leozhang8654/yukio-desktop-pet/pull/15)、[PR #16](https://github.com/leozhang8654/yukio-desktop-pet/pull/16)、[PR #17](https://github.com/leozhang8654/yukio-desktop-pet/pull/17)、[PR #18](https://github.com/leozhang8654/yukio-desktop-pet/pull/18)、[b2fceaf](https://github.com/leozhang8654/yukio-desktop-pet/commit/b2fceaf92c735bbdfdaa490cd07289667555e75c)（隐身）、[4b27c97](https://github.com/leozhang8654/yukio-desktop-pet/commit/4b27c974c43c4235869f85cfc614a6dbda954e51)（千夏）、[d0de8c1](https://github.com/leozhang8654/yukio-desktop-pet/commit/d0de8c13b0f0e237adbe18c26db4bb0634a48e83)（发布源码）、[验证范围与失败记录](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/validation/plugin-signs-0.4.6.md)、[批准卡兼容范围](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/validation/approval-cards.md)、发布附件 `validation.json`。

## 本地开发分支：抛掷与晕眩（计划标注 2026-10-09 起）

**问题 → 修改。**在原拖拽之外加入甩出、屏幕边界碰撞、落地晕眩和再次接住；共用物理参数，按输入速度区分轻放与抛掷。后续修复轻放不留在原处、抛掷后任务气泡没恢复、悬浮时无法再次提起。具体手感修复日期未找到明确记录，不从文件修改时间推断。

**验证 → 结果。**本地初轮摘要为 Swift 188 项、Python 257 项（1 项跳过）；后续手感摘要为 Swift 191 项、Python 260 项（1 项跳过）。Mac 记录包含真实 AppKit 窗口回调，Python 窗口层使用 Win32 替身，Windows 原生字段仍为 pending。安装报告记录曾替换本地桌面测试包；不能据此推断今天仍运行该包，也不能将它算作 0.4.6 的功能。

**状态与下一步。**已实现（本地）、未发布。Windows 原生验收按现有记录延后；完整手工抛接仍待补充，不标作全部通过。现有源码基于带未提交改动的旧工作树，进入发布线之前需审核代码、资源哈希与兼容性。

**证据（本地独有，尚非 GitHub 公开证据）：**[实现记录](animation-review/throw-and-dizzy/README.md)、[初轮测试](animation-review/throw-and-dizzy/test-summary.json)、[手感修复](animation-review/throw-and-dizzy/handfeel-fixes.md)、[后续测试](animation-review/throw-and-dizzy/handfeel-tests.json)、[冻结源码依据](animation-review/throw-and-dizzy/source-state.json)。公开前应另存脱敏版报告，移除其中的私人绝对路径；不直接上传整个本地报告目录。

## 尚缺的证据与后续维护

- **公开版本人工场景：**补上 0.4.6 上述放牌、点牌和真实批准往返；记录服务、系统、源码与包哈希，不用截图存在代替行为验证。
- **平台覆盖：**Intel 原生运行、全部 Windows 10/11 设备、系统 DPI 和多屏组合未覆盖；局部通过只能支持局部结论。
- **失败复现：**保留 Windows 外部点击失败及成功重跑，补稳定复现条件后再决定是否需要修复。
- **本地抛掷：**没有公开提交／PR／Release 与 Windows 原生结果；如后续发布，先整理脱敏证据并对齐发布源码。
- **历史缺口：**早期单独运行日志、部分原始视频和已删除工作树中的产物未找到可公开重放的副本。旧评审和测试数仅按原记录引用，不补造时间、工时或意见。
- **桌面状态：**本次未核对当前运行版本。历史安装报告仅证明报告记载时的状态。
- **记录用途：**这些链接用于理解与核查开发过程，不构成作者身份、原创性或工作量的独立证明。

今后新增阶段使用 [提交与阶段记录规范](../CONTRIBUTING.md)；用户可感知的版本变化维护在 [CHANGELOG](../CHANGELOG.md)，不要把全部提交复制到这里。

## 本次文档整理的核验

2026-10-18 已将 CHANGELOG 的 19 个公开版本日期逐一与 GitHub Release 元数据对照；检查文内固定提交、PR、远程文件及附件是否存在，并读取引用的 Actions 运行状态，保留失败与重跑的区别。文档相对链接和空白格式检查通过。本次没有重新运行历史应用测试，也没有构建、发布或替换桌面程序。


## AI 活动观察 Stage 1.2a：持久记录与恢复（2026-10-20，本地未发布）

**问题 → 修改。**上一阶段只有内存中的结果关联和一次性导出。新增 Swift／Python SQLite 历史库，把元数据事件、完整行读取位置、来源世代和有界关联状态放在同一事务里；接入实际程序的导入、持续跟随和只读查询入口。单文件记录器可独立运行，桌宠现有路径不变。

**验证 → 修复。**测试发现 Foundation 与 Python 对 Mac `/var` 路径的规范化不同，导致同一来源身份不同；Swift 改用 POSIX realpath。增加中途改写、数据库锁、存储容量错误、半行、重启、突然退出和跨会话用例；用两种实际程序互读、接续同一个数据库，并验证 33 个既有结果场景。等待无新活动时只检查文件属性，避免反复扫描历史。对特殊文件改用不阻塞的打开方式，防止误选管道后一直等待。

**状态与下一步。**本轮只完成明确选择单个 Codex 文件的可运行存储链，没有自动发现所有会话、工作台或千问。Windows 代码在 Mac 测试，不代表 Windows 实机通过。未发布、未替换桌面 App；后续接入独立后台采集与多会话发现。

**证据：**[实现合同与命令](ACTIVITY-HISTORY.md)、[验证摘要](validation/activity-observation-stage1-2/verification.json)。原始测试日志在本机临时目录，候选源文件哈希随摘要保存。

## AI 活动观察 Stage 1.2b：自动发现与实时状态（2026-10-20，本地未发布）

**问题 → 修改。**单文件记录器需要逐个指定聊天，不适合持续使用。本轮新增两端独立采集命令，按最近一天发现 Codex 记录、轮流处理、保存限额、异常重试及汇总心跳；同一数据库或状态文件禁止两个记录器同时使用。进度网站增加日常语言展开说明，并连接本机实际运行汇总。

**验证 → 修复。**新增测试覆盖新文件、再次活跃的旧文件、长文件与短文件轮流、半行、重启、会话隔离、坏文件、空间不足和目录限制。真实 CLI 检查也确认重启不重复、互读与接续、正常停止和锁保护。整体检查暴露旧硬链接测试的原生 `SQLITE_IOERR_VNODE` 情况；精确要求 Yukio 身份错误，再关闭并移除仅测试创建的别名后检查历史。另去掉直接打开／关闭数据库来比对文件身份的方式，避免破坏 SQLite 文件锁；保留系统安全保护。

**状态与下一步。**Swift 214 项通过；Python 336 项运行、335 项通过、1 项需 Windows 跳过。已启动本机 Swift 记录器并在网站核对实际数据，未替换桌面 App、未安装开机项。下一阶段接入更多客户端与关系证据，再进入活动工作台。

**证据：**[实现、边界与运行说明](ACTIVITY-COLLECTOR.md)、[验证摘要](validation/activity-observation-stage1-2b/verification.json)。真实历史只留在本机应用数据目录；仓库报告不含原始聊天。
