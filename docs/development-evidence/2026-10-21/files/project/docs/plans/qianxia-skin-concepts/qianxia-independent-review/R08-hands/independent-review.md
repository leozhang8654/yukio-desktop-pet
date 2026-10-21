# R08 手/道具独立复审

**结论：通过，仅限12件手/道具静态可见层。** 33个冻结文件SHA256全部匹配。探针修改项已重新完整目视；11件沿用项与R07通过项字节一致。

## 上次漏检与本轮闭环

**上次对探针的通过判断漏掉了尖端左缘缺口。** 用户截图与R07冻结部件的对照证实该问题；旧报告保留，本报告追加更正记录，不把旧通过当作本轮探针验收依据。

问题定位：原图1205×1306，0-based；完整尖端范围 `[445,704,514,785)`，本轮实际mask改动范围 `[476,742,495,767)`，共129像素。R07/R08旧候选对照所用源图/蒙版/部件哈希与原报告一致。

R08恢复了缺口处的可见青色边缘与连续收尖轮廓。复查接头、左缘、下端及整件手部/外壳，未见新直切缺口、突片或漏底。固定底座横向青色环、下方承托区与邻接衣服未被并入移动部件；原高光与颜色未重绘。

证据：[R07/R08同坐标400%对照](evidence/R07-R08-tip-comparison.png)、[完整尖端600%](evidence/probe-tip-1-roi600.png)、[接头与左缘600%](evidence/probe-tip-2-roi600.png)、[下端及固定底座600%](evidence/probe-tip-3-roi600.png)、[原图与选区800%叠加](evidence/tip-source-overlay.png)。

## 本轮覆盖

探针从真实原图重新检查，整件100%/200%棋盘、黑、白、洋红背景，彩色选区与轮廓，接头到尖端分段放大。另实看 write_file/left-hand、respond/hand-and-card，前轮内部alpha与描边修复未回退。其余9件没有重复目视，凭独立通过记录与同字节沿用。共实际显示15张图片。

## 逐部件结论

|状态|部件|结论|本轮依据|
|---|---|---|---|
|default_work|trackball-hand|通过|相同字节，沿用R07通过；未重复目视|
|failed|hand-and-card|通过|相同字节，沿用R07通过；未重复目视|
|idle|orb|通过|相同字节，沿用R07通过；未重复目视|
|idle|touching-hand|通过|相同字节，沿用R07通过；未重复目视|
|question_for_user|button-cap|通过|相同字节，沿用R07通过；未重复目视|
|question_for_user|pressing-hand|通过|相同字节，沿用R07通过；未重复目视|
|read_web|pointing-hand|通过|相同字节，沿用R07通过；未重复目视|
|respond|hand-and-card|通过|相同字节+目视抽查|
|verify|hand-and-probe|通过|修改项重新完整目视+用户问题闭环+整件回归|
|view_image|hand-and-stylus|通过|相同字节，沿用R07通过；未重复目视|
|write_file|left-hand|通过|相同字节+目视抽查|
|write_file|right-hand|通过|相同字节，沿用R07通过；未重复目视|

## 机器与哈希

先目视后机器。12件独立重算均为1连通块、0不透明内部孔洞、0所选全透明源像素、0所选RGB改写、0封闭内部非255区域。基本机器数字也曾未发现旧缺口，不能替代原图轮廓对照。

完整33文件SHA256、逐部件绑定、用户截图SHA256及旧探针对照绑定见 [findings.json](findings.json)；机器复算与129像素改动范围见 [independent-machine-checks.json](independent-machine-checks.json)。

本报告不包含虹膜、隐藏补底或动画验收。

## 实际显示文件

- `/Users/developer/Desktop/截屏2026-10-11 下午3.50.12.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/respond-hand-and-card-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/respond-hand-and-card-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/review/respond/hand-and-card/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/verify-hand-and-probe-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/verify-hand-and-probe-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/review/verify/hand-and-probe/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/write_file-left-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/write_file-left-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R08/review/write_file/left-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/probe-tip-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/probe-tip-2-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/probe-tip-3-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/tip-source-overlay.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R08-hands/evidence/R07-R08-tip-comparison.png`
