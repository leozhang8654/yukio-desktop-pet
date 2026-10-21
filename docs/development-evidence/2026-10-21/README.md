# Yukio 开发过程资料归档 · 2026-10-21

[下载全部资料分包](https://github.com/leozhang8654/yukio-desktop-pet/releases/tag/development-evidence-2026-10-21) · [逐文件清单](manifest.json) · [包校验值](SHA256SUMS.txt) · [排除清单](excluded.json)

本页保存千夏设计与蒙版迭代、动画候选和评审、雪绪抛掷实验、回答功能排错、活动检测实现与需求调研。资料由项目开发过程中使用的本地工作目录整理而来，保留用户反馈、AI 辅助制作、既有 Agent 评审和自动化测试的实际角色。

这是历史开发资料归档。源码快照来自带本地改动的旧工作树，抛掷和活动检测材料中的“本地实现”不等于已进入正式应用。当前正式应用仍为 0.4.6；本次不改变 macOS/Windows 运行资源、安装包或自动更新源。

本轮从前次盘点的 9,640 个文件中归档 9,192 个文件，分成 6 包；其中 1,662 份文本、重点图和研究文件也可直接在本目录的 `files/` 中浏览。43 项重点材料全部包含。文件数含多轮副本，不能换算为独立创作数或工时。

## 完整下载

每包保留 `project/`（原项目相对路径）或 `planning/`（桌面需求与研究文件）目录。将六包解压到同一目录可合并浏览；原文的相对引用以完整归档目录为准。在线 `files/` 只包含可直接浏览的副本，部分图片、补底和动画需要下载。ZIP 内原有压缩包仍保留，经必要脱敏后另记公开哈希。

| 分包 | 内容 | 文件数 | 下载大小 |
|---|---|---:|---:|
| [01-qianxia-design-and-cutouts.zip](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/development-evidence-2026-10-21/01-qianxia-design-and-cutouts.zip) | 千夏概念、选稿、抠图、精修与准备阶段 | 2,680 | 1083.5 MiB |
| [02-qianxia-motion-candidates.zip](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/development-evidence-2026-10-21/02-qianxia-motion-candidates.zip) | 千夏多轮动画候选、参数、工具及编码检查 | 2,799 | 1250.4 MiB |
| [03-qianxia-reviews-and-interactions.zip](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/development-evidence-2026-10-21/03-qianxia-reviews-and-interactions.zip) | 既有独立 Agent 评审、退回证据与提起姿态迭代 | 711 | 88.1 MiB |
| [04-yukio-animation-experiments.zip](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/development-evidence-2026-10-21/04-yukio-animation-experiments.zip) | 雪绪头颈、目光、抛掷和手感实验 | 2,295 | 720.7 MiB |
| [05-local-source-docs-and-validation.zip](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/development-evidence-2026-10-21/05-local-source-docs-and-validation.zip) | 本地源码快照、文档、素材、测试与回执 | 701 | 63.5 MiB |
| [06-research-and-requirements.zip](https://github.com/leozhang8654/yukio-desktop-pet/releases/download/development-evidence-2026-10-21/06-research-and-requirements.zip) | 原始需求、搜索大纲与四份 PDF 调研／教学资料 | 6 | 2.6 MiB |

## 43 项重点材料

优先连同相邻源码、前后图、失败记录和复测结果阅读。下表为可直接浏览的公开副本；改动过的副本与原件哈希分别记录在 manifest 中。

| 类别 | 文件 | 说明 |
|---|---|---|
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/image-prompt.txt](files/project/docs/plans/qianxia-skin-concepts/image-prompt.txt) | 角色方案的制作提示文本，与概念图及后续轮次连用 |
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/provenance.json](files/project/docs/plans/qianxia-skin-concepts/provenance.json) | 记录来源和制作依据 |
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/README.md](files/project/docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/README.md) | 记录用户指出的探针缺块、129 像素修补及两文件变化 |
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/review/change-report.json](files/project/docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/review/change-report.json) | 局部修改的像素数、坐标范围和其他蒙版是否改变 |
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/review/probe-tip-before-after.png](files/project/docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/review/probe-tip-before-after.png) | 原图、修前、修后三栏图；本次已实际打开 |
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/qianxia-motion-R07/reference/R07-revision.json](files/project/docs/plans/qianxia-skin-concepts/qianxia-motion-R07/reference/R07-revision.json) | 保留用户反馈、6→12 级眼皮、取消手变形、5 秒循环的具体修改 |
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/qianxia-motion-R07/tools/build_motion.py](files/project/docs/plans/qianxia-skin-concepts/qianxia-motion-R07/tools/build_motion.py) | 对应动画生成实现 |
| 千夏设计与迭代 | [docs/plans/qianxia-skin-concepts/qianxia-motion-R07/review/encoded-validation.json](files/project/docs/plans/qianxia-skin-concepts/qianxia-motion-R07/review/encoded-validation.json) | 对应编码产物的机器检查记录 |
| 千夏评审与失败 | [docs/plans/qianxia-skin-concepts/qianxia-independent-review/motion-R04/independent-review.md](files/project/docs/plans/qianxia-skin-concepts/qianxia-independent-review/motion-R04/independent-review.md) | 既有 Agent 独立评审原件，明确退回及手指拉长问题；本次没有重新进行独立评审 |
| 千夏评审与失败 | [docs/plans/qianxia-skin-concepts/qianxia-independent-review/motion-R04/candidate-sha256.json](files/project/docs/plans/qianxia-skin-concepts/qianxia-independent-review/motion-R04/candidate-sha256.json) | 冻结候选清单；本次重新核对 397/397 文件一致 |
| 千夏评审与失败 | [docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/independent-review.md](files/project/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/independent-review.md) | 后续复查记录，可与 R08 修正和对照图交叉阅读 |
| 抛掷功能开发 | [docs/plans/throw-and-dizzy-ai-prompt.zh-CN.md](files/project/docs/plans/throw-and-dizzy-ai-prompt.zh-CN.md) | 功能实施要求及验收规划 |
| 抛掷功能开发 | [docs/animation-review/throw-and-dizzy/README.md](files/project/docs/animation-review/throw-and-dizzy/README.md) | 实现、五轮候选、验证范围和仍待测试项目 |
| 抛掷功能开发 | [docs/animation-review/throw-and-dizzy/task-changes.patch](files/project/docs/animation-review/throw-and-dizzy/task-changes.patch) | 保留本轮代码补丁，说明实际修改而非只有成品截图 |
| 抛掷功能开发 | [docs/animation-review/throw-and-dizzy/source-state.json](files/project/docs/animation-review/throw-and-dizzy/source-state.json) | 记录当时工作区与源码依据 |
| 抛掷功能开发 | [docs/animation-review/throw-and-dizzy/handfeel-fixes.md](files/project/docs/animation-review/throw-and-dizzy/handfeel-fixes.md) | 用户反馈后的轻放、再次提起和任务报告恢复修复 |
| 抛掷功能开发 | [docs/animation-review/throw-and-dizzy/handfeel-tests.json](files/project/docs/animation-review/throw-and-dizzy/handfeel-tests.json) | 191 项 Swift、260 项 Python 等既有测试摘要；Windows 原生未完成 |
| 抛掷功能开发 | [YukioPlayer/Sources/YukioCore/ThrowPhysics.swift](files/project/YukioPlayer/Sources/YukioCore/ThrowPhysics.swift) | Mac 侧物理实现 |
| 抛掷功能开发 | [YukioWin/yukio/throw_physics.py](files/project/YukioWin/yukio/throw_physics.py) | Python 侧物理实现 |
| 抛掷素材制作 | [sources/interaction-rig/provenance.json](files/project/sources/interaction-rig/provenance.json) | 来源、SAM 初选、最终蒙版、合成底图哈希；13/13 输入已重新核对 |
| 抛掷素材制作 | [sources/interaction-rig/refinement.json](files/project/sources/interaction-rig/refinement.json) | 蒙版人工精修参数 |
| 抛掷素材制作 | [sources/interaction-rig/sam-round-01/prompts.json](files/project/sources/interaction-rig/sam-round-01/prompts.json) | SAM 初选提示与参数 |
| 抛掷素材制作 | [sources/interaction-rig/mask-review-04/report.json](files/project/sources/interaction-rig/mask-review-04/report.json) | 最终轮蒙版检查记录 |
| 早期动画调试 | [YukioPlayer/build/gaze-fix/blink-detail.png](files/project/YukioPlayer/build/gaze-fix/blink-detail.png) | 不同闭眼级数细节对照；本次已实际打开 |
| 早期动画调试 | [YukioPlayer/build/gaze-fix/before-eye-contact.png](files/project/YukioPlayer/build/gaze-fix/before-eye-contact.png) | 目光修复前对照 |
| 早期动画调试 | [YukioPlayer/build/gaze-fix/candidate-eye-contact.png](files/project/YukioPlayer/build/gaze-fix/candidate-eye-contact.png) | 候选目光对照 |
| 早期动画调试 | [YukioPlayer/build/neck-stability/checks.json](files/project/YukioPlayer/build/neck-stability/checks.json) | 头颈修复过程检查记录 |
| 早期动画调试 | [YukioPlayer/build/neck-stability-rejected/README.md](files/project/YukioPlayer/build/neck-stability-rejected/README.md) | 被保留的旧候选说明，与该目录资源结合阅读 |
| 回答功能排错 | [docs/answer-validation/2026-10-04/README.md](files/project/docs/answer-validation/2026-10-04/README.md) | 权限问题、初次验证盲点、canonical history 修正和真实诊断往返 |
| 回答功能排错 | [docs/answer-validation/2026-10-04/live-question-roundtrip.json](files/project/docs/answer-validation/2026-10-04/live-question-roundtrip.json) | 真实问答诊断回执；属于诊断结果，不等于用户体验评价 |
| 回答功能排错 | [docs/answer-validation/2026-10-04/canonical-yukio-codex-fixture-server-receipt.json](files/project/docs/answer-validation/2026-10-04/canonical-yukio-codex-fixture-server-receipt.json) | 模拟协议端接收回执，可与真实诊断区分 |
| 回答功能排错 | [docs/answer-validation/2026-09-26/README.md](files/project/docs/answer-validation/2026-09-26/README.md) | 较早的后台回答修复及未验证范围 |
| 活动检测开发 | [docs/ACTIVITY-OBSERVATION.md](files/project/docs/ACTIVITY-OBSERVATION.md) | 升级路线与阶段界限 |
| 活动检测开发 | [docs/ACTIVITY-HISTORY.md](files/project/docs/ACTIVITY-HISTORY.md) | 活动历史设计和实现说明 |
| 活动检测开发 | [docs/ACTIVITY-COLLECTOR.md](files/project/docs/ACTIVITY-COLLECTOR.md) | 采集器设计和实现说明 |
| 活动检测开发 | [YukioPlayer/Sources/YukioCore/ActivityCollector.swift](files/project/YukioPlayer/Sources/YukioCore/ActivityCollector.swift) | 本地采集器实际源码 |
| 活动检测开发 | [YukioWin/yukio/activity_collector.py](files/project/YukioWin/yukio/activity_collector.py) | 另一端采集器实际源码 |
| 活动检测开发 | [docs/validation/activity-observation-stage1-2b/verification.json](files/project/docs/validation/activity-observation-stage1-2b/verification.json) | 已有测试、真实本地采集汇总、修复记录；标注本地运行未发布 |
| 活动检测开发 | [tools/activity-progress/progress.json](files/project/tools/activity-progress/progress.json) | 按阶段维护的进度记录 |
| 活动检测开发 | [artifacts/activity-progress/live-collector.png](files/project/artifacts/activity-progress/live-collector.png) | 本地进度网站显示采集运行状态的截图 |
| 开发过程总览 | [docs/development-log.md](files/project/docs/development-log.md) | 串联公开提交与本地实验，作为导航使用；事后整理不能替代原始产物 |
| 原始需求与调研 | [规划/我计划对现有桌面助手的 AI 活动检测能力进行升级.docx](files/planning/%E6%88%91%E8%AE%A1%E5%88%92%E5%AF%B9%E7%8E%B0%E6%9C%89%E6%A1%8C%E9%9D%A2%E5%8A%A9%E6%89%8B%E7%9A%84%20AI%20%E6%B4%BB%E5%8A%A8%E6%A3%80%E6%B5%8B%E8%83%BD%E5%8A%9B%E8%BF%9B%E8%A1%8C%E5%8D%87%E7%BA%A7.docx) | 升级目标、范围和用户参与方式的原始需求文本 |
| 原始需求与调研 | [规划/搜索大纲.docx](files/planning/%E6%90%9C%E7%B4%A2%E5%A4%A7%E7%BA%B2.docx) | 调研方向及问题纲要 |

## 校验、隐私与范围

- 原始输入未改写；公开文本中的个人主目录、私网地址和诊断会话／调用标识按稳定规则替换。原始 SHA-256 和公开 SHA-256 同时保留。代码快照中需要本机路径的历史脚本应按复现环境调整。
- 247 个顶层文件发生脱敏或容器成员调整。嵌套压缩包的变化见 [nested-archive-changes.json](nested-archive-changes.json)。
- 排除编译缓存、已发布或被取代的安装包、已安装 App 备份及编译二进制；保留对应源码、参数、制作候选和验证记录。每项路径、原哈希和排除原因列在 excluded.json。
- 本次没有把 NAS 中未盘点的资料、私人应用数据或原始聊天数据库加入归档。未发现密钥标记；这一检测不等同于对全部内容语义的独立安全认证。
- 前次远端盘点比较了当时的 23 个分支、19 个标签、18 个 PR head 和 100 个 Release 附件。manifest 的 prior_remote_status 描述该次盘点，不代表永久的未上传状态；上传前已再次拉取远端，其他工作分支可能新增相同资料。
- 前次确认抛掷输入 13/13 与 provenance 一致、千夏 R04 冻结文件 397/397 一致。本次逐包重新读取并核对全部归档成员，结果见 [archive-verification.json](archive-verification.json)。
- 本次仅核验归档完整性，不重跑文档中的历史功能测试、不代写新的独立评审。Windows 原生待测、人工动态验收未完成、曾经失败的记录按原意保留。
- PDF 教材、研究汇编和事后开发日志可辅助理解过程，不能单独证明对应功能已经实现。原文件修改时间也不作为独立的创作时间证明。

## 源码基准

项目远端基准：`460fb1935966ef2c3472a0bfa661fe90836e5855`。原本地工作树基准：`b176e1e38eb65cee94d4045cf7e94ffa045bb9a4`（`release/v0.2.1`，包含未提交修改）。归档提交只添加文档和证据快照，不将历史代码覆盖到运行入口。

与首次盘点相比，13 个归档源文件内容发生变化。旧报告的测试只说明其当时版本，不能证明这些新快照已通过相同测试；详见 [publication-summary.json](publication-summary.json)。

## 校验下载文件

```sh
shasum -a 256 -c SHA256SUMS.txt
```

使用下载页同目录提供的 `SHA256SUMS.txt`。解压后可以按 `manifest.json` 的 `archive_path` 和 `public_sha256` 对照单个文件。原目录中的旧 SHA256SUMS/provenance 是历史原件哈希；发生脱敏的文本应使用本次 manifest 的公开哈希。
