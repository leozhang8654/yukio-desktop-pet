# 千夏 motion-R02 独立复审

**整体结论：退回／待补动态验证。已检查的静态修正通过，R01 M01、M02 关闭；V01 未关闭。** 本轮未发现新的明确静态返工缺陷，不能据此宣布整套动态通过。

评审者：独立 Agent `/root/cutout_independent_review`。未参与制作，只读冻结候选，没有执行制作脚本、实例化 Rig 或修改候选。未重试锁屏 UI，也未绕过锁屏。

候选：`/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-motion-R02`。开始复审先独立计算全部 268 文件 SHA-256，均与冻结清单匹配；包含原生预览二进制。清单哈希 `21a91339f36b4843f617828c06405833ce53bf0c1b40fa813045d3ffbd2876d7`。详见 [candidate-sha256.json](candidate-sha256.json)、[hash-verification.json](hash-verification.json)。

## 静态问题闭环

**M01 已静态关闭。** 逐状态重新读取 11 套编码眼皮，查看原图、张眼与完整六级闭合，在 100%、200%、300% 检查原睫毛、外眼角、肤色过渡和尖端。首目光及最大眼区变化帧分别检查六级；该帧第 3 级看黑、白、洋红、棋盘格。原粗上睫毛不再瞬间替换为短细横线，翼形及外眼角关系保持，R01 碎白台阶未复现；已看全闭级未见彩色虹膜碎片。未见新的明确肤色断层或睫毛尖端破损。实速的连续性仍待播放。

[等待回应六级编码对照](evidence/question_for_user-decoded-lids300.png)；[全部眼部 100% 对照](evidence/eyes-all-states-100.png)。每套眼部包围框及实看索引见 findings.json。

**M02 已静态关闭。** respond 原坐标 `[124,229,133,240]` 的悬空暗片已消失，邻接 `[120,223,142,243]` 的手腕/袖口接缝顺接。查看实际编码全部 25 个唯一身体帧的手、卡和袖口 ROI（200%），并看完整 100% / 192×208 逻辑显示参考和最大位移四背景。未见脱握、残手重边或露底孔洞。卡片和手仍保持联动，袖口固定。

[全部 25 帧](evidence/respond-all-25-frames200.png)；[极值四背景](evidence/respond-encoded-four-bg200.png)。此结论不替代连续进入/停留播放。

## 逐状态覆盖

| 状态 | 身体 | 眼皮六级实看身体索引 | 结论 |
|---|---|---|---|
| idle | R01 字节沿用，继承原静态覆盖 | 0 | 静态范围通过；动态待补 |
| thinking | R01 字节沿用，继承原静态覆盖 | 0,8 | 静态范围通过；动态待补 |
| read_file | R01 字节沿用，继承原静态覆盖 | 0,16 | 静态范围通过；动态待补 |
| view_image | R01 字节沿用，继承原静态覆盖 | 0,39 | 静态范围通过；动态待补 |
| write_file | R01 字节沿用，完整图极值抽查 | 0 | 静态范围通过；动态待补 |
| verify | R01 字节沿用，完整图极值抽查 | 0,25 | 静态范围通过；动态待补 |
| read_web | R01 字节沿用，继承原静态覆盖 | 0,26 | 静态范围通过；动态待补 |
| default_work | R01 字节沿用，继承原静态覆盖 | 0 | 静态范围通过；动态待补 |
| respond | 25 帧全看局部＋完整图与四背景极值 | 0,24 | 静态范围通过；动态待补 |
| task_complete | R01 字节沿用，继承原静态覆盖 | 不适用 | 静态范围通过；动态待补 |
| question_for_user | R01 字节沿用，完整图极值抽查 | 0,16 | 静态范围通过；动态待补 |
| failed | R01 字节沿用，继承原静态覆盖 | 0,20 | 静态范围通过；动态待补 |

除 respond 外的 11 套身体 WebP 与 R01 逐字节相同，因此没有把未改资源冒充本轮重看；对验证、打字、等待回应做了完整原图/极值抽查。眼皮每个列出的身体索引均看完六级，未目视穷举所有其他目光组合。共有 30 张证据实际打开；生成但未打开的辅助图不算覆盖。

## 独立资源核验与代码结论

目视后才读取机器报告。独立脚本确认 12 原图预乘缩放与 source-2x 精确一致；12 身体和 11 眼皮 WebP 与对应 decoded PNG 像素一致；全部身体帧允许区外变化 0，眼皮允许区外及 alpha 变化 0；眨眼映射有效。首尾回接帧相同，时长数组和 loopStart 有效。三个一次状态的 loopStart 后只有稳定尾帧。task_complete 一帧且无眼皮。上部头发 y<140 和下部家具 y≥300 的保守独立固定区变化 0，不将其当作完整语义区域证明。详见 [resource-audit.json](resource-audit.json)。

读取冻结的 Preview.swift 全文与 HTML 播放代码，确认原生预览默认 autoRetest=false，一次状态进入后仅循环保持尾段；N 新事件单独重置身体 offset，T 自动重测是显式模式。HTML 按钮也只重触发对应身体时间。眨眼使用全局独立时钟，结束后 2.8–7 秒安排下一次、单次 0.18–0.26 秒，10% 概率追加相隔 0.12 秒的双眨；新事件及选择状态不重置该时钟。闭眼有全闭停留段。上述是代码审查结论，没有实际执行用户事件；不等于 App 正式调度已经验证。

原生预览读取 decoded PNG，WebP 与它们的一致性由本轮独立检查确认。冻结二进制仅验证哈希，没有声称执行或二进制重建一致性。制作方另报语法检查/编译成功，本评审不将其计入实际播放证据。

## V01：仍未完成

Mac 仍锁屏，用户尚未回复解锁。未做真实尺寸/真实速度下循环状态至少三轮、慢速、暂停逐帧的连续观察、连续眨眼、连续切换、一次动作长时保持与新事件重触发、真实 task bubble 配合或无标签动作辨认；Windows 实机未测。图表中的静态通过仅关闭指定静态缺陷。

保持 R02 冻结，待解锁后完成实际播放并记录发现，再决定整套动态是否通过。当前整体保持退回／待补动态验证。

## 实际打开的证据

- [evidence/eyes-all-states-100.png](evidence/eyes-all-states-100.png)
- [evidence/idle-decoded-lids300.png](evidence/idle-decoded-lids300.png)
- [evidence/idle-max-gaze-and-backgrounds200.png](evidence/idle-max-gaze-and-backgrounds200.png)
- [evidence/thinking-decoded-lids300.png](evidence/thinking-decoded-lids300.png)
- [evidence/thinking-max-gaze-and-backgrounds200.png](evidence/thinking-max-gaze-and-backgrounds200.png)
- [evidence/read_file-decoded-lids300.png](evidence/read_file-decoded-lids300.png)
- [evidence/read_file-max-gaze-and-backgrounds200.png](evidence/read_file-max-gaze-and-backgrounds200.png)
- [evidence/view_image-decoded-lids300.png](evidence/view_image-decoded-lids300.png)
- [evidence/view_image-max-gaze-and-backgrounds200.png](evidence/view_image-max-gaze-and-backgrounds200.png)
- [evidence/write_file-decoded-lids300.png](evidence/write_file-decoded-lids300.png)
- [evidence/write_file-max-gaze-and-backgrounds200.png](evidence/write_file-max-gaze-and-backgrounds200.png)
- [evidence/write_file-source-encoded.png](evidence/write_file-source-encoded.png)
- [evidence/verify-decoded-lids300.png](evidence/verify-decoded-lids300.png)
- [evidence/verify-max-gaze-and-backgrounds200.png](evidence/verify-max-gaze-and-backgrounds200.png)
- [evidence/verify-source-encoded.png](evidence/verify-source-encoded.png)
- [evidence/read_web-decoded-lids300.png](evidence/read_web-decoded-lids300.png)
- [evidence/read_web-max-gaze-and-backgrounds200.png](evidence/read_web-max-gaze-and-backgrounds200.png)
- [evidence/default_work-decoded-lids300.png](evidence/default_work-decoded-lids300.png)
- [evidence/default_work-max-gaze-and-backgrounds200.png](evidence/default_work-max-gaze-and-backgrounds200.png)
- [evidence/respond-decoded-lids300.png](evidence/respond-decoded-lids300.png)
- [evidence/respond-max-gaze-and-backgrounds200.png](evidence/respond-max-gaze-and-backgrounds200.png)
- [evidence/respond-source-encoded.png](evidence/respond-source-encoded.png)
- [evidence/respond-decoded-detail200.png](evidence/respond-decoded-detail200.png)
- [evidence/respond-all-25-frames200.png](evidence/respond-all-25-frames200.png)
- [evidence/respond-encoded-four-bg200.png](evidence/respond-encoded-four-bg200.png)
- [evidence/question_for_user-decoded-lids300.png](evidence/question_for_user-decoded-lids300.png)
- [evidence/question_for_user-max-gaze-and-backgrounds200.png](evidence/question_for_user-max-gaze-and-backgrounds200.png)
- [evidence/question_for_user-source-encoded.png](evidence/question_for_user-source-encoded.png)
- [evidence/failed-decoded-lids300.png](evidence/failed-decoded-lids300.png)
- [evidence/failed-max-gaze-and-backgrounds200.png](evidence/failed-max-gaze-and-backgrounds200.png)
