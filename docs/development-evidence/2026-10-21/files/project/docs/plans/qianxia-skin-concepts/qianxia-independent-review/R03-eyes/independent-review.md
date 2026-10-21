# R03 虹膜独立复审

**结论：退回（仅虹膜范围）。19件通过，3件仍需局部轮廓修正。**

审查者：独立 Codex 子 Agent `/root/cutout_independent_review`，沿用R01/R02独立标准，未参与制作。没有读取制作脚本、reference参数或制作方自检结论，没有查看R03手/道具。

## 本轮覆盖

- 10件改动候选：全部重新核对真实原图、原mask、透明部件、叠加与轮廓，100%/200%棋盘格、黑、白、洋红背景；10件全部原问题ROI另看600%及相邻轮廓。
- 12件未改候选：独立核对source、mask、part SHA-256，均与R02已通过字节一致。抽看 `read_file/iris-left` 与 `write_file/iris-right` 的100%/200%多背景，确认R01高光凹缺与异常侧边没有回退。其余10件沿用已核验字节对应的R02独立通过结论，**没有声称在本轮重新目视**。
- 先完成上述目视，再读取机器报告与核验数据；后为残留3处补充1000%坐标定位。1000%图只帮助定位，问题同时在200%四背景可辨，不把正常像素网格本身判为缺陷。

55个冻结文件哈希全部匹配；12件未改文件的逐件对比在 [unchanged-verification.json](unchanged-verification.json)。源图/mask/part完整哈希、38张实际显示图像清单及逐件评审方式见 [findings.json](findings.json)。自动生成但未实际打开的10张参考图另行列出，没有算入实际目视清单。

## 修复进展

R02 E02、E03、E04、E05、E07、E08、E09已闭环通过。E01、E06、E10的亮色误选已移除，但其角点尚未形成正确连续轮廓，因此仍退回。R01 F02/F03保持修复。

## 必须修正的3处

坐标使用原始1205×1306图像，0-based，x向右/y向下，ROI为 `[x0,y0,x1,y1)`。

### R03-C01 · `default_work/iris-left` · medium

关联R02 E01。整体证据区：`[443, 566, 454, 576]`；重点：`[449, 569, 454, 574]`。

原白色眼白楔片已移除，但左下转角仍有向左伸出的暗色短尖尾。侧缘下降到转角后先内缩，再在底边突然向左伸回，形成钩状外轮廓；底部固定眼角线的一小段随虹膜被截出。

建议：沿虹膜侧缘到下缘的真实转折局部重修覆盖率，去掉向眼白方向伸出的尖尾与固定眼角线残段，保留主体深色描边厚度；不要扩大为整圈侵蚀。

证据：[E01-roi1-600.png](evidence/E01-roi1-600.png)。
证据：[E01-tip.png](evidence/E01-tip.png)。

### R03-C02 · `write_file/iris-left` · medium

关联R02 E10。整体证据区：`[443, 562, 455, 572]`；重点：`[450, 564, 455, 569]`。

白色眼白残片已移除，但左下角留下同类暗色小尖尾，侧缘与底缘交接存在一次向外反折，白/洋红背景上可见短横突起。

建议：只修正这一角点，使侧边与底边按原虹膜轮廓衔接，去掉伸入固定眼角区域的短尾，维持邻近抗锯齿与主体描边。

证据：[E10-roi1-600.png](evidence/E10-roi1-600.png)。
证据：[E10-tip.png](evidence/E10-tip.png)。

### R03-C03 · `read_web/iris-right` · medium

关联R02 E06。整体证据区：`[679, 505, 690, 520]`；重点：`[684, 508, 689, 514]`。

白色三角已移除，但右上角留下上沿伸出的暗色短片，紧接其下出现透明内凹口，然后轮廓再向外回到右侧弧线。该形状没有连续跟随原图虹膜的圆弧转角。

建议：重新连接右上圆弧与上方遮挡边，排除上沿固定暗线残段，并平顺处理凹口两侧的亚像素覆盖率；不能通过把凹口重新填白解决。

证据：[E06-roi1-600.png](evidence/E06-roi1-600.png)。
证据：[E06-notch.png](evidence/E06-notch.png)。

## 逐件结论

| 部件 | 本轮方式 | 结论 | 证据 |
|---|---|---|---|
| `default_work/iris-left` | 改动件全量目视/ROI | 退回：R03-C01 | [100/200%对照](evidence/default_work-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/default_work/iris-left/four-backgrounds-200.png) |
| `default_work/iris-right` | 改动件全量目视/ROI | 通过：本轮局部修正与相邻轮廓复查通过。 | [100/200%对照](evidence/default_work-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/default_work/iris-right/four-backgrounds-200.png) |
| `failed/iris-left` | 改动件全量目视/ROI | 通过：本轮局部修正与相邻轮廓复查通过。 | [100/200%对照](evidence/failed-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/failed/iris-left/four-backgrounds-200.png) |
| `failed/iris-right` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `idle/iris-left` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `idle/iris-right` | 改动件全量目视/ROI | 通过：本轮局部修正与相邻轮廓复查通过。 | [100/200%对照](evidence/idle-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/idle/iris-right/four-backgrounds-200.png) |
| `question_for_user/iris-left` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `question_for_user/iris-right` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `read_file/iris-left` | 字节一致＋目视抽查 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 本轮100/200%四背景抽看，无R01高光/突起回退。 | [100/200%对照](evidence/read_file-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/read_file/iris-left/four-backgrounds-200.png) |
| `read_file/iris-right` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `read_web/iris-left` | 改动件全量目视/ROI | 通过：本轮局部修正与相邻轮廓复查通过。 | [100/200%对照](evidence/read_web-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/read_web/iris-left/four-backgrounds-200.png) |
| `read_web/iris-right` | 改动件全量目视/ROI | 退回：R03-C03 | [100/200%对照](evidence/read_web-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/read_web/iris-right/four-backgrounds-200.png) |
| `respond/iris-left` | 改动件全量目视/ROI | 通过：本轮局部修正与相邻轮廓复查通过。 | [100/200%对照](evidence/respond-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/respond/iris-left/four-backgrounds-200.png) |
| `respond/iris-right` | 改动件全量目视/ROI | 通过：本轮局部修正与相邻轮廓复查通过。 | [100/200%对照](evidence/respond-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/respond/iris-right/four-backgrounds-200.png) |
| `thinking/iris-left` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `thinking/iris-right` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `verify/iris-left` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `verify/iris-right` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `view_image/iris-left` | 改动件全量目视/ROI | 通过：本轮局部修正与相邻轮廓复查通过。 | [100/200%对照](evidence/view_image-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/view_image/iris-left/four-backgrounds-200.png) |
| `view_image/iris-right` | 字节一致，沿用R02通过 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 | [哈希核对](unchanged-verification.json) |
| `write_file/iris-left` | 改动件全量目视/ROI | 退回：R03-C02 | [100/200%对照](evidence/write_file-iris-left-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/write_file/iris-left/four-backgrounds-200.png) |
| `write_file/iris-right` | 字节一致＋目视抽查 | 通过：source/mask/part与R02通过字节一致，沿用原结论。 本轮100/200%四背景抽看，无R01高光/突起回退。 | [100/200%对照](evidence/write_file-iris-right-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/write_file/iris-right/four-backgrounds-200.png) |

## 机器核验与边界

独立重算22件均1连通块、选入源图全透明像素0、所选RGB相对源图改动0。原始机器报告拓扑通过；这不排除尖尾或凹口。详见 [independent-machine-checks.json](independent-machine-checks.json)。

本次仅是虹膜静态可见层复审，不包含手/道具、隐藏结构、补底、眼皮、动画或原生播放。请仅修3处角点并另存新轮次，保留19件已通过字节。新轮次继续检查修正点、相邻轮廓、高光和冻结哈希。
