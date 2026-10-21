# R02 虹膜独立复审

**结论：退回（仅限22个虹膜可见层）。22/22件已逐件检查，12件通过、10件需局部返工，无未检查项。**

审查者：独立 Codex 子 Agent `/root/cutout_independent_review`，与R01为同一审查者，未参与候选制作。只读取本次限定的虹膜素材、scope、冻结哈希、对应逐件PNG，以及目视完成后读取的 machine-report.json；没有查看/评价R02手或道具素材，也没有读取制作脚本、reference参数、制作方自检理由或评分。

## 已确认的修复

- **R01 F01：** 22个虹膜普遍硬台阶已改善，选区现在有软覆盖率；原先明显突刺与硬台阶消除。但10件角点仍有眼白/肤色误选，见新问题清单。
- **R01 F02：** `read_file/iris-left` 高光左缘凹缺已修复，当前白色高光连续；该件本轮通过。
- **R01 F03：** `write_file/iris-right` 左上暗色凸块及高光上方凹口已修复；该件本轮通过。

## 审查方法与哈希

逐件从真实source、mask、part PNG解码，按完整候选包围框显示100%原图、原始mask和候选；逐件检查100%棋盘格/黑/白/洋红背景。逐件显示原图、选区叠加与轮廓200%，并单独打开对应200%四背景。22件全部完成后才读取机器报告与核验数据；随后逐件补看600%下缘，并看7张局部600%对照。没有以缩小总览替代逐件检查。

实际显示73张图像，原始文件、叠加/轮廓文件及显示图的完整清单在 findings.json 的 opened_files。该清单区分原始文件经裁片显示和实际展示图像。

11张源图、22张mask、22张part共**55个SHA-256全部匹配**。本报告绑定 frozen-hashes.json 的字节；findings.json 另内嵌完整清单及每件三类哈希。独立重新计算22件均1连通块、选入源图alpha=0像素为0、所选RGB与源图相同，软mask像素数215–257。拓扑与RGB来源正确不能证明角点选区语义正确。

## 本轮必须修正的问题

以下坐标均为原始1205×1306图像的0-based坐标；x向右、y向下，区域为 `[x0,y0,x1,y1)`。left/right沿用文件名。所有问题严重度为medium，局部误选需要修正；不能因像素面积小直接放行。

### E01 · `default_work/iris-left`

区域：`[[437, 559, 462, 579]]`。

左下角选入眼白楔片；从原图的白色眼白沿深色虹膜线外侧延入选区，黑底呈白色角点，底部还形成小突出。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[default-left-bottom.png](evidence/default-left-bottom.png)。
证据：[default_work-iris-left-bottom600.png](evidence/default_work-iris-left-bottom600.png)。

### E02 · `default_work/iris-right`

区域：`[[623, 566, 642, 584]]`。

左下角保留一条白色眼白及淡肤色边片；它位于虹膜深色外线的外侧，黑底呈较亮短竖边。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[default_work-iris-right-bottom600.png](evidence/default_work-iris-right-bottom600.png)。

### E03 · `failed/iris-left`

区域：`[[438, 545, 460, 562]]`。

左下角带入下眼角红/肤色像素，黑底出现红灰小边片；原图相应颜色连接固定下眼角，不属于虹膜本体。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[failed-left-bottom.png](evidence/failed-left-bottom.png)。
证据：[failed-iris-left-bottom600.png](evidence/failed-iris-left-bottom600.png)。

### E04 · `idle/iris-right`

区域：`[[625, 563, 644, 581]]`。

左下拐角有白色眼白细条伸在虹膜深色描边外侧，黑底呈亮色竖片。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[idle-iris-right-bottom600.png](evidence/idle-iris-right-bottom600.png)。

### E05 · `read_web/iris-left`

区域：`[[428, 493, 450, 513], [434, 552, 456, 566]]`。

左上原图虹膜轮廓是圆弧转角，选区以方角跨入眼白，候选留下白色三角。左下角也带入眼白与下眼角红色小片。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[web-left-top.png](evidence/web-left-top.png)。
证据：[read_web-iris-left-bottom600.png](evidence/read_web-iris-left-bottom600.png)。

### E06 · `read_web/iris-right`

区域：`[[672, 503, 693, 525]]`。

右上原图圆弧转角之外的眼白被方角选区带入；候选黑/洋红底均出现白色角点。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[web-right-top.png](evidence/web-right-top.png)。

### E07 · `respond/iris-left`

区域：`[[489, 544, 511, 563]]`。

右下角选入肤色区域，形成棕粉色小片和偏方的下角；源图该色在虹膜深色轮廓外、与脸部连接。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[respond-left-bottom.png](evidence/respond-left-bottom.png)。
证据：[respond-iris-left-bottom600.png](evidence/respond-iris-left-bottom600.png)。

### E08 · `respond/iris-right`

区域：`[[625, 551, 644, 569]]`。

左下角同时带入一段白色眼白边及其下方肤色，黑底呈白粉色短边条。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[respond-iris-right-bottom600.png](evidence/respond-iris-right-bottom600.png)。

### E09 · `view_image/iris-left`

区域：`[[443, 555, 464, 574]]`。

左下角深色轮廓外有窄白色眼白楔片，黑底局部亮边与原图眼白对应。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[view_image-iris-left-bottom600.png](evidence/view_image-iris-left-bottom600.png)。

### E10 · `write_file/iris-left`

区域：`[[438, 555, 463, 575]]`。

左下角保留白色眼白楔片，深色轮廓外出现亮片及较直的角点；与原图虹膜侧缘的弯曲过渡不一致。

建议：仅在所列角点沿真实虹膜深色轮廓外侧精修局部蒙版与亚像素覆盖率，排除眼白/肤色残片；保留虹膜描边厚度及已修好的高光，不用全局腐蚀或整体缩小清理。圆弧处不要用方角跨过真实边界。

证据：[write-left-bottom.png](evidence/write-left-bottom.png)。
证据：[write_file-iris-left-bottom600.png](evidence/write_file-iris-left-bottom600.png)。

## 逐件结论

| 部件 | 结论 | 证据 |
|---|---|---|
| `default_work/iris-left` | 退回：E01 | [100/200%原图、mask、四背景](evidence/default_work-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/default_work/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/default_work-iris-left-bottom600.png) |
| `default_work/iris-right` | 退回：E02 | [100/200%原图、mask、四背景](evidence/default_work-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/default_work/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/default_work-iris-right-bottom600.png) |
| `failed/iris-left` | 退回：E03 | [100/200%原图、mask、四背景](evidence/failed-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/failed/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/failed-iris-left-bottom600.png) |
| `failed/iris-right` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/failed-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/failed/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/failed-iris-right-bottom600.png) |
| `idle/iris-left` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/idle-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/idle/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/idle-iris-left-bottom600.png) |
| `idle/iris-right` | 退回：E04 | [100/200%原图、mask、四背景](evidence/idle-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/idle/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/idle-iris-right-bottom600.png) |
| `question_for_user/iris-left` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/question_for_user-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/question_for_user/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/question_for_user-iris-left-bottom600.png) |
| `question_for_user/iris-right` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/question_for_user-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/question_for_user/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/question_for_user-iris-right-bottom600.png) |
| `read_file/iris-left` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 R01 F02高光凹缺已修复。 | [100/200%原图、mask、四背景](evidence/read_file-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/read_file/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/read_file-iris-left-bottom600.png) |
| `read_file/iris-right` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/read_file-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/read_file/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/read_file-iris-right-bottom600.png) |
| `read_web/iris-left` | 退回：E05 | [100/200%原图、mask、四背景](evidence/read_web-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/read_web/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/read_web-iris-left-bottom600.png) |
| `read_web/iris-right` | 退回：E06 | [100/200%原图、mask、四背景](evidence/read_web-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/read_web/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/read_web-iris-right-bottom600.png) |
| `respond/iris-left` | 退回：E07 | [100/200%原图、mask、四背景](evidence/respond-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/respond/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/respond-iris-left-bottom600.png) |
| `respond/iris-right` | 退回：E08 | [100/200%原图、mask、四背景](evidence/respond-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/respond/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/respond-iris-right-bottom600.png) |
| `thinking/iris-left` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/thinking-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/thinking/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/thinking-iris-left-bottom600.png) |
| `thinking/iris-right` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/thinking-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/thinking/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/thinking-iris-right-bottom600.png) |
| `verify/iris-left` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/verify-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/verify/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/verify-iris-left-bottom600.png) |
| `verify/iris-right` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/verify-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/verify/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/verify-iris-right-bottom600.png) |
| `view_image/iris-left` | 退回：E09 | [100/200%原图、mask、四背景](evidence/view_image-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/view_image/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/view_image-iris-left-bottom600.png) |
| `view_image/iris-right` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 | [100/200%原图、mask、四背景](evidence/view_image-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/view_image/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/view_image-iris-right-bottom600.png) |
| `write_file/iris-left` | 退回：E10 | [100/200%原图、mask、四背景](evidence/write_file-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/write_file/iris-left/four-backgrounds-200.png)；[600%下缘](evidence/write_file-iris-left-bottom600.png) |
| `write_file/iris-right` | 通过：可见虹膜/瞳孔/高光轮廓与原图对应，100/200%四背景未见必须退回的误选、漏选、突刺或颜色污染。 R01 F03左上暗色凸块和凹口已修复。 | [100/200%原图、mask、四背景](evidence/write_file-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R02/review/write_file/iris-right/four-backgrounds-200.png)；[600%下缘](evidence/write_file-iris-right-bottom600.png) |

## 复审边界

仅通过表中12件静态可见虹膜；不包含其他10件、不包含任何手/道具，也不包含补底、眼皮或动画。原图真实遮挡保持，不要求补画不可见虹膜。

建议按10件问题的局部ROI精修后另存新轮次，保留已经确认的高光与抗锯齿修复，再冻结文件复审修改位置及关联轮廓。不要通过整体侵蚀或批量缩小去掉角点邻接色，因为这会削薄真实虹膜描边。

完整数据：[findings.json](findings.json)。独立机器复核：[independent-machine-checks.json](independent-machine-checks.json)。
