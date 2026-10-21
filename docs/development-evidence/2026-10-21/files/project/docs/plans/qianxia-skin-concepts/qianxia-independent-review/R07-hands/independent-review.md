# R07 手/道具独立复审

**结论：通过，仅限12件手/道具静态可见层。** 33个冻结文件SHA256全部匹配；本轮两件修改均通过，10件沿用项与R06已通过项字节一致。

本轮实际完整目视 write_file/left-hand、respond/hand-and-card，以及沿用抽查 view_image/hand-and-stylus。其余9件没有重复目视，明确凭原独立通过记录与原图/蒙版/部件相同哈希沿用。未评价虹膜、隐藏结构、补底、眼皮和动画。

## 修正点与回归

坐标为1205×1306原图，0-based，[x0,y0,x1,y1)。

- **R06-H01 · write_file/left-hand**，重点 `[430, 770, 437, 783]`：内部旧软alpha细槽和孤立漏底点已消除；真实指缝保留，最右长指左下弧黑描边及外缘抗锯齿连续；小指台阶、中央指尖键盘短刺未复发。 [600%证据](evidence/R06-H01-1-roi600.png)。
- **respond-internal-alpha · respond/hand-and-card**，重点 `[355, 719, 378, 724]`：内部可见手指阴影与原图一致，四背景不再额外透底；轮廓及卡片下沿未见回退。 [600%证据](evidence/respond-internal-1-roi600.png)。

握笔手抽查确认：末端手指描边与凹口形状保持，袖口粉紫残片未复发。未发现新增误选、漏选、内部漏底、颜色污染或边缘断裂。

## 逐部件结论

|状态|部件|结论|本轮依据|
|---|---|---|---|
|default_work|trackball-hand|通过|相同字节，沿用R06通过；未重复目视|
|failed|hand-and-card|通过|相同字节，沿用R06通过；未重复目视|
|idle|orb|通过|相同字节，沿用R06通过；未重复目视|
|idle|touching-hand|通过|相同字节，沿用R06通过；未重复目视|
|question_for_user|button-cap|通过|相同字节，沿用R06通过；未重复目视|
|question_for_user|pressing-hand|通过|相同字节，沿用R06通过；未重复目视|
|read_web|pointing-hand|通过|相同字节，沿用R06通过；未重复目视|
|respond|hand-and-card|通过|修改项完整目视+ROI+相邻回归|
|verify|hand-and-probe|通过|相同字节，沿用R06通过；未重复目视|
|view_image|hand-and-stylus|通过|相同字节+目视抽查|
|write_file|left-hand|通过|修改项完整目视+ROI+相邻回归|
|write_file|right-hand|通过|相同字节，沿用R06通过；未重复目视|

## 方法与冻结绑定

先逐件对照真实原图、蒙版、彩色叠加、轮廓和透明层；以100%及200%查看棋盘、黑、白、洋红背景，再以600%复看两处内部修正ROI。实际显示11张图片。之后读取机器报告并独立重算。

12件均为1连通块、0不透明内部孔洞、0所选全透明源像素、0所选RGB改写；以mask<255的连通性另算封闭内部区域，12件均为0个/0像素。真实外缘仍有软alpha，未用全部硬边替代抗锯齿。这些数字辅助目视，不替代语义判断。

完整33文件SHA256、逐件源图/蒙版/部件绑定及沿用核对见 [findings.json](findings.json)，独立机器复算见 [independent-machine-checks.json](independent-machine-checks.json)。

## 实际显示文件

以下11张图实际显示；原PNG解码清单另列于findings.json，未将机器解码计作目视。

- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/respond-hand-and-card-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/respond-hand-and-card-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R07/review/respond/hand-and-card/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/view_image-hand-and-stylus-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/view_image-hand-and-stylus-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R07/review/view_image/hand-and-stylus/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/write_file-left-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/write_file-left-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R07/review/write_file/left-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/R06-H01-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R07-hands/evidence/respond-internal-1-roi600.png`
