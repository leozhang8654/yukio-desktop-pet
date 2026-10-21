# R05 手/道具独立复审

**结论：退回。12件中11件通过、1件退回：write_file/left-hand。** 33个冻结文件SHA256全部一致。

本轮完整目视3件修改项，并抽看 respond/hand-and-card、verify/hand-and-probe。9件沿用项与R04已通过源图/蒙版/透明层字节一致，其中7件本轮没有重复目视。结论仅限静态可见手/道具，不包含虹膜、隐藏结构、补底、眼皮及动画。

## 剩余问题 R05-H01（high）

部件：write_file/left-hand。原图坐标范围 `[425,775,458,808)`，重点 `[438,789,455,802)`；坐标为1205×1306原图，0-based。

最右侧长指朝向指缝的左下弧仍裁到了皮肤/粉色边，原图可见黑色描边没有保留完整。200%白/洋红底可见该段直接从皮肤过渡到透明，与其余手指的连续黑线不一致。小指旧内切台阶、中部短刺及相邻手指侧边已修复，此项只剩长指的这段弧线。

像素佐证：原图(443,794)的RGB为145/83/104、(447,798)为224/153/151，蒙版均为0；紧邻选入像素已是皮肤色，说明边界落在色边内部。此数据用于定位，缺陷判断来自原图与100/200%及局部多背景对照。

修正建议：仅沿该长指左下真实弧线恢复贴近皮肤的原黑色描边与抗锯齿，让上下未缺失的黑线连续连接；同时继续排除指缝中央键盘粉点和大块固定键盘黑区。不要扩大整片指缝，也不要重画RGB。

证据：[800%对照](evidence/remaining-long-finger.png)、[旧ROI 600%复查](evidence/R04-H03-3-roi600.png)、[完整源图/选区/描边](evidence/write_file-left-hand-reference.png)。

## 旧问题关闭情况

- **R04-H01**：关闭：卡片下沿小矩形突片及紫粉邻色清除；斜线连续，上沿与手腕修复未回退。
- **R04-H02**：关闭：握笔凹口袖口粉紫片清除，末端手指黑线和笔杆轮廓保留。
- **R04-H03**：部分关闭：小指台阶、中部底部短刺及相邻指侧描边改善；最右长指左下弧仍漏选，转R05-H01。

## 逐部件结论

|状态|部件|结论|本轮依据|
|---|---|---|---|
|default_work|trackball-hand|通过|字节沿用，本轮未重复目视|
|failed|hand-and-card|通过|修改项完整目视+旧ROI|
|idle|orb|通过|字节沿用，本轮未重复目视|
|idle|touching-hand|通过|字节沿用，本轮未重复目视|
|question_for_user|button-cap|通过|字节沿用，本轮未重复目视|
|question_for_user|pressing-hand|通过|字节沿用，本轮未重复目视|
|read_web|pointing-hand|通过|字节沿用，本轮未重复目视|
|respond|hand-and-card|通过|字节沿用+目视抽查|
|verify|hand-and-probe|通过|字节沿用+目视抽查|
|view_image|hand-and-stylus|通过|修改项完整目视+旧ROI|
|write_file|left-hand|退回R05-H01|修改项完整目视+旧ROI|
|write_file|right-hand|通过|字节沿用，本轮未重复目视|

## 检查与绑定

实际打开21张图片：原图/选区叠加/轮廓、100%四背景、200%四背景、五个旧问题ROI的600%对照及剩余弧线800%对照。先目视后机器。12件独立重算均为1连通块、0不透明内部孔洞、0所选透明源像素、0所选RGB改写；这些数字不证明描边语义完整。

33文件冻结绑定与逐件SHA256见 [findings.json](findings.json)；逐件机器数据见 [independent-machine-checks.json](independent-machine-checks.json)。

## 实际显示文件

- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/failed-hand-and-card-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/failed-hand-and-card-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R05/review/failed/hand-and-card/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/respond-hand-and-card-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/respond-hand-and-card-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R05/review/respond/hand-and-card/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/verify-hand-and-probe-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/verify-hand-and-probe-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R05/review/verify/hand-and-probe/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/view_image-hand-and-stylus-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/view_image-hand-and-stylus-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R05/review/view_image/hand-and-stylus/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/write_file-left-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/write_file-left-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R05/review/write_file/left-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/R04-H01-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/R04-H02-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/R04-H03-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/R04-H03-2-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/R04-H03-3-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R05-hands/evidence/remaining-long-finger.png`
