# R04 虹膜独立复审

**结论：通过，仅限22个虹膜静态可见层。** 3件修改项全部复查通过，19件与R03已通过项字节一致。55个冻结文件SHA256全部匹配。

本轮实看5件：3件修改项，以及 read_file/iris-left、write_file/iris-right 两件高光回归样本。其余17件没有重复目视，明确凭R03独立通过记录与原图/蒙版/部件相同哈希沿用。未检查手部、补底、隐藏结构、眼皮和动画。

## 实际检查方法

先对照原图、蒙版、透明部件、彩色叠加和轮廓；100%完整部件及棋盘/黑/白/洋红背景，200%完整四背景，三处旧问题再800%局部。之后才读取机器报告、独立核对哈希并重算拓扑。实际显示13张图片，详见末尾文件清单。

## 旧问题关闭

坐标为1205×1306原图，0-based，矩形[x0,y0,x1,y1)。

- **R03-C01 · default_work/iris-left**，坐标 `[443, 566, 454, 576]`：原底角短尾已消除，收尖连续；未见新增白色楔形、断线或漏高光。 [800%证据](evidence/R03-C01-roi800.png)。
- **R03-C02 · write_file/iris-left**，坐标 `[443, 562, 455, 572]`：原底角短尾已消除，底缘与相邻描边连续，未见新增折角或邻色误选。 [800%证据](evidence/R03-C02-roi800.png)。
- **R03-C03 · read_web/iris-right**，坐标 `[679, 505, 690, 520]`：上角突出暗唇及下方凹口消除，轮廓恢复连续凸转角，原白三角未复发。 [800%证据](evidence/R03-C03-roi800.png)。

未发现需要返工的新误选、漏选、颜色污染或边缘断裂。两件高光回归样本保留原高光形状。

## 逐部件结论

|状态|部件|结论|本轮依据|
|---|---|---|---|
|default_work|iris-left|通过|修改项完整目视+ROI|
|default_work|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|failed|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|failed|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|idle|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|idle|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|question_for_user|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|question_for_user|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|read_file|iris-left|通过|相同字节+目视抽查|
|read_file|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|read_web|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|read_web|iris-right|通过|修改项完整目视+ROI|
|respond|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|respond|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|thinking|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|thinking|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|verify|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|verify|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|view_image|iris-left|通过|相同字节，沿用R03通过；本轮未重复目视|
|view_image|iris-right|通过|相同字节，沿用R03通过；本轮未重复目视|
|write_file|iris-left|通过|修改项完整目视+ROI|
|write_file|iris-right|通过|相同字节+目视抽查|

## 机器与冻结绑定

独立重算22件均为1连通块、0不透明内部孔洞、0所选全透明源像素、0所选RGB改写。数字结果仅辅助目视。机器输入中附带的范围外手部行不用于判断。

完整55项SHA256、22件源图/蒙版/部件逐项哈希、沿用核对与机器数据见 [findings.json](findings.json) 和 [independent-machine-checks.json](independent-machine-checks.json)。

## 实际打开文件

以下为实际显示的图片；原图、蒙版、部件与叠加/轮廓的实际解码清单单列于findings.json，避免把机器解码当作目视。

- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/default_work-iris-left-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/default_work/iris-left/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/write_file-iris-left-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/write_file/iris-left/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/read_web-iris-right-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/read_web/iris-right/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/read_file-iris-left-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/read_file/iris-left/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/write_file-iris-right-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/write_file/iris-right/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/R03-C01-roi800.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/R03-C02-roi800.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-eyes/evidence/R03-C03-roi800.png`
