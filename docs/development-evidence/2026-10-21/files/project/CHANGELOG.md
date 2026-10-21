# 更新记录

2026-10-18 根据真实提交、PR 和 GitHub Release 补充整理。**以下日期统一为公开 Release 的 UTC 发布日期**，不是功能开发起始日；早期文档采用的本地日期和候选日期保留在对应历史记录中。

这里只列用户可感知的变化；原因、失败尝试、测试环境与证据见 [开发过程记录](docs/development-log.md)。已发布不代表所有平台和人工场景都已验证。

## 未发布

- **AI 活动观察 Stage 1.2b（本地已实现）：**自动发现近期 Codex 会话，轮流记录、重启接续、异常重试与容量暂停；新增可展开说明的本机进度网站，接入真实运行状态。Mac 本机记录器已启动；未设置开机运行，未替换桌面 App，Windows 实机待验证。见 [范围与检查](docs/ACTIVITY-COLLECTOR.md)。

- **AI 活动观察 Stage 1.2a（本地已实现）：**新增 Codex 单文件本地记录器，支持保存、重启接续、持续跟随和分页查询；记录与读取位置一起提交，保存失败可重试，改写或替换来源保留旧历史。仅保存必要元数据，未接入默认全会话采集或工作台，未替换现有 App。见 [范围与验证](docs/ACTIVITY-HISTORY.md)。

- **AI 活动观察 Stage 1.1（本地已实现）：**修复 Codex 并发调用的失败结果错配；两端新增成功、失败、取消、未知及未关联回执的结果元数据和只读导出。33 个共享场景验证通过；完整历史库、工作台和千问解释尚未实现，Windows 原生待验证。见 [实现与验证](docs/ACTIVITY-OBSERVATION.md)。未替换现有 App。
- **抛掷互动（本地已实现）：**甩出、屏幕反弹、落地晕眩、再次接住与轻放判定；修复交互后任务气泡不恢复及悬浮时无法提起。本地 Mac 有自动验证记录，Windows 原生和完整人工手感待验证。见 [本地记录](docs/animation-review/throw-and-dizzy/README.md)。尚未找到公开发布依据，不归入 0.4.6。
- **开发文档（本次整理）：**补齐阶段进展、Release 时间依据、验证边界、失败修复和提交／PR 模板。这是文档变更，不对应新的应用版本。

待机隐身已随 0.4.6 公开发布，不再列为未发布功能。AI 个性化等仅有设计的内容见 [规划](docs/PERSONALIZATION.md)，不计作未发布实现。

## 0.4.6 — 2026-10-14（已发布）

- 新增千夏皮肤、专用拖动站姿、默认待机隐身、明确的一次性批准卡；修复回答粘贴、Windows 中文回执与 Claude Hook 依赖。
- 修复 GPT Chrome 插件错跳桌面入口、全屏标签重复及旧聊天标题丢失。完成提醒可按对应聊天可见性收起，问题与批准仍需实际处理。
- 包含 0.4.4／0.4.5 候选工作，这两个编号没有独立公开 Release。[验证记录](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/validation/plugin-signs-0.4.6.md)保留 Windows 失败／重跑及尚未完成的人工场景。

证据：[v0.4.6](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.6)。

## 0.4.3 — 2026-10-12（已发布）

- 修复 macOS 跨屏聊天可见性、静读识别失效、透明 Dock 遮挡与部分 GPT／Claude 窗口识别。
- 两端隔离协助任务身份，避免子任务完成牌挡住父任务；修正 Windows 升级测试固定目标版本。
- Windows 仍采用前台窗口识别；不能当作 Mac 多屏遮挡判断已移植。

证据：[v0.4.3](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.3)。

## 0.4.2 — 2026-10-10（已发布）

- 在两端右键设置加入“退出雪绪”；“完成”按钮仍只关闭设置。

证据：[v0.4.2](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.2)。

## 0.4.1 — 2026-10-10（已发布）

- GPT 确认接收答案或会话记录出现已接收回答后，立即放下问号牌；发送失败保留输入与问题。

证据：[v0.4.1](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.1)。

## 0.4.0 — 2026-10-10（已发布）

- 新增自动稳定版检查、更新说明、稍后与手动检查，用户确认后安装并重启。
- macOS 使用 Sparkle 签名更新；Windows 改用 Velopack 安装与升级，保留用户设置。旧版需先手动安装一次支持更新的版本。
- 有原生升级、故障拒绝和公开下载复验记录；生产签名的早期阻塞随后解除。见[升级验证](https://github.com/leozhang8654/yukio-desktop-pet/blob/460fb1935966ef2c3472a0bfa661fe90836e5855/docs/update-validation/0.4.0/README.md)。更新签名不等于系统公证／代码签名。

证据：[v0.4.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.4.0)。

## 0.3.9 — 2026-10-08（已发布）

- 任务气泡、通知卡、文字和点击区域随人物大小缩放；Windows 调整尺寸时即时重绘并保留淡入进度。

证据：[v0.3.9](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.9)。

## 0.3.8 — 2026-10-06（已发布）

- 将助手色线从 2 点加粗到 4 点，并向外延伸，不挤占正文与内边距。

证据：[v0.3.8](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.8)。

## 0.3.7 — 2026-10-06（已发布）

- 将彩色气泡改为统一白底，顶部细色线区分 GPT、Claude 和 DeepSeek。

证据：[v0.3.7](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.7)。

## 0.3.6 — 2026-10-06（已发布）

- 按实际聊天助手为气泡与通知卡着色；多助手跟随和切换聊天时保留对应颜色。

证据：[v0.3.6](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.6)。

## 0.3.5 — 2026-10-04（已发布）

- 在气泡、卡片与菜单显示 Codex 保存的真实聊天标题；无标题时显示会话标签，不拿用户输入代替。

证据：[v0.3.5](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.5)。

## 0.3.4 — 2026-10-04（已发布）

- GPT / Codex 回答从模拟键盘转为后台 IPC，兼容 canonical history 和旧 turns。
- 核对线程、问题与回执，拒绝过期／重复答案；失败保留输入供重试，成功只收起对应问题。
- macOS 回答不再依赖辅助功能权限；Windows 增加真实 named-pipe 与打包 EXE 协议检查。协议测试不代表所有服务界面端到端通过。

证据：[v0.3.4](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.4)。

## 0.3.3 — 2026-10-03（已发布）

- 新增大号取消举牌按钮，点击后不打开聊天；设置支持外部点击关闭。
- 正式版暂停独立助手页面及入口，再次打开程序进入紧凑设置。历史提醒实现仍保留，不能当作当前有公开助手入口。

证据：[v0.3.3](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.3)。

## 0.3.2 — 2026-09-26（已发布）

- 新增默认关闭的登录启动与系统状态提示，两端使用浮动小设置。
- 回答／收起状态按聊天和问题隔离，切换聊天后不重复弹旧题；结构化回答只关闭匹配调用。
- 有 Windows 原生 EXE、启动项及公开包检查；真实注销登录和全部多屏场景未覆盖。

证据：[v0.3.2](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.2)。

## 0.3.1 — 2026-09-26（已发布）

- 识别 Codex 桌面当前选中聊天，只抑制对应完成提醒；后台任务继续提醒，过期诊断保守处理。
- Windows 将视图日志读取移出动画线程，修正 64 位窗口／进程句柄声明。

证据：[v0.3.1](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.1)。

## 0.3.0 — 2026-09-26（已发布）

- 两端新增助手主窗口、单次本地提醒、稍后五分钟、编辑／删除、重启与睡眠后恢复。
- Windows 打包 Tk，补充大小、显隐与个性化持久化；问题卡按结构化回答收起并隔离重复提交。
- AI、屏幕观察、自动记录和简报仍为规划；助手正式入口后在 0.3.3 暂停。

证据：[v0.3.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.3.0)。

## 0.2.2 — 2026-09-26（已发布）

- 十二状态固定头颈，保留手部和道具动作；双眼在固定眼框内同步转动，修复闭眼虹膜残留。
- macOS 完整重绘透明画面；同步两端动画和运行时分页，整理动画输入与历史文档。

证据：[v0.2.2](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.2.2)。

## 0.2.1 — 2026-09-25（已发布）

- 允许在桌宠旁问题卡直接作答，发送前检查目标应用前台状态。该方案后由 0.3.4 后台 IPC 替代。

证据：[v0.2.1](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.2.1)。

## 0.2.0 — 2026-09-23（已发布）

- 引入经过 round_13 评审的十二种部件动画、独立眼皮时钟和低内存分页；两端共用资源。
- 支持三类助手自动／指定跟随、任务气泡、聊天卡叠、持续举牌、悬挂拖动和中英文设置。
- 历史评审为 94/100；保留 respond 动作语义的低级问题，分数不代表后续版本重新验收。

证据：[v0.2.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.2.0)。

## 0.1.0 — 2026-09-16（已发布）

- 首个公开桌宠版本：macOS 跟随 Claude Code，以动作、任务气泡和提问／完成牌呈现活动。
- Windows 的 Deep Code / Claude 跟随随后于 09-17 补入，当前 Release 有两端附件；不能把后来补充的附件视为初次发布时间已有。

证据：[v0.1.0](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/v0.1.0)。
