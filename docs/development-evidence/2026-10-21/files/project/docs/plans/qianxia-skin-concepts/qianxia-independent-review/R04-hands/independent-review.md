# R04 手/道具独立复审

**结论：退回。12件全部实际目视，9件通过、3件需修正。** 33个冻结文件SHA256全部一致；4件沿用项与R03源图、蒙版、透明层字节一致且本轮重新目视。

本报告只判断静态可见部件，不判断虹膜、隐藏结构、补底或动画。评审者未参与制作，未改候选；没有读取制作脚本、参数或自评。

## 检查与覆盖

逐件对照真实原图、蒙版、彩色叠加、轮廓和透明层，100%及200%查看棋盘、黑、白、洋红背景。旧问题逐区600%复看；新定位以400%、800%、1000%补充证据。先目视后读取机器报告；实际显示57张图片。

## 必须返工

坐标均为1205×1306原图，0-based，矩形[x0,y0,x1,y1)。

### R04-H01 · failed/hand-and-card · medium

区域：`[[434, 697, 449, 709]]`；重点：`[440, 703, 444, 705]`。

上斜边旧台阶已消除；下斜边与固定袖口黑线相交处仍多出小矩形突片。x438–439处边界y703，x440–443反向落到y704，再在x444回到y702，形成不属于连续卡框斜线的短尾，并带邻接紫粉像素。

建议：仅沿卡框真实下斜边移除x440–443的固定袖口连接残片，使相邻斜边连续；勿削薄整条卡框，不改已恢复手腕。

证据：[card-bottom.png](evidence/card-bottom.png)、[card-spur-precise.png](evidence/card-spur-precise.png)。

### R04-H02 · view_image/hand-and-stylus · medium

区域：`[[443, 746, 459, 769]]`；重点：`[448, 747, 458, 764]`。

末端手指原可见黑色轮廓已恢复，旧直截缺口关闭；笔杆与手指凹口内仍留粉紫色袖口片。原图该颜色连接下方固定袖口，候选黑底与洋红底仍可辨认狭长残片，不是手指内部阴影。

建议：沿凹口的真实手指/笔杆暗边局部排除袖口粉紫片，保留本轮已经恢复的末端手指黑线与圆弧。

证据：[H05-1-roi600.png](evidence/H05-1-roi600.png)、[H05-2-roi600.png](evidence/H05-2-roi600.png)、[stylus-groove.png](evidence/stylus-groove.png)、[stylus-remnant-precise.png](evidence/stylus-remnant-precise.png)。

### R04-H03 · write_file/left-hand · high

区域：`[[348, 794, 372, 814], [397, 780, 426, 818], [425, 775, 458, 808]]`；重点：`[412, 811, 418, 817]`。

指尖/指缝仍未形成原图连续轮廓：左侧小指尖下缘有内切台阶；中部指尖底部还留朝下短刺并夹粉色键盘像素；右侧长指靠指缝及下弧的原黑边保留不足，局部皮肤直接接透明。原图可见这些指尖的黑色边线，因此不能以去除键盘为由一并裁掉。

建议：分别沿每个可见指尖重建局部alpha边界，恢复真实黑线与圆弧，排除键盘短刺和粉点；不要沿直线切除整个指缝，也不要全局膨胀或平滑。

证据：[H06-1-roi600.png](evidence/H06-1-roi600.png)、[left-finger-outline.png](evidence/left-finger-outline.png)、[left-outline-precise.png](evidence/left-outline-precise.png)、[left-small-tip.png](evidence/left-small-tip.png)、[left-right-finger.png](evidence/left-right-finger.png)。

## 旧问题关闭情况

- **H01**：关闭：触球手下侧袖口残片清除，黑线连续。
- **H02**：旧上沿台阶关闭；下沿新定位残片见R04-H01。
- **H03**：关闭：探针上斜边平顺，左侧浅绿残点清除；针尖与固定底座分离未回退。
- **H04**：关闭：手侧台阶和卡下袖口残片清除，邻接边连续。
- **H05**：部分关闭：末端手指黑线恢复；凹口袖口残色见R04-H02。
- **H06**：未关闭：指尖边界与键盘残片见R04-H03。
- **H07**：关闭：右手侧边旧突点/台阶清除，连续黑线保留。
- **H08**：关闭：右上尖尾/凹口消除，外侧灰青污染未回退。

## 逐部件结论

|状态|部件|结论|本轮检查|
|---|---|---|---|
|default_work|trackball-hand|通过|100%/200%完整部件和四背景；R03字节沿用已核验|
|failed|hand-and-card|退回：R04-H01|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|
|idle|orb|通过|100%/200%完整部件和四背景；R03字节沿用已核验|
|idle|touching-hand|通过|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|
|question_for_user|button-cap|通过|100%/200%完整部件和四背景；R03字节沿用已核验|
|question_for_user|pressing-hand|通过|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|
|read_web|pointing-hand|通过|100%/200%完整部件和四背景；R03字节沿用已核验|
|respond|hand-and-card|通过|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|
|verify|hand-and-probe|通过|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|
|view_image|hand-and-stylus|退回：R04-H02|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|
|write_file|left-hand|退回：R04-H03|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|
|write_file|right-hand|通过|100%/200%完整部件和四背景；局部修正及相邻轮廓复查|

## 机器检查与哈希

独立重算12件均为1连通块、0不透明内部孔洞、0所选透明源像素、0所选RGB改写。33冻结文件全部匹配；8件有改动、4件保持R03通过字节。上述数字不代表alpha语义或描边已合格。

完整逐部件源图/蒙版/透明层SHA256、冻结绑定、机器数据见 [findings.json](findings.json) 与 [independent-machine-checks.json](independent-machine-checks.json)。

## 实际打开文件

下列57张图已实际显示。原始PNG解码读取清单另见findings.json，不以机器解码代替目视。

- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/default_work-trackball-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/default_work-trackball-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/default_work/trackball-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/failed-hand-and-card-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/failed-hand-and-card-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/failed/hand-and-card/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/idle-orb-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/idle-orb-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/idle/orb/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/idle-touching-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/idle-touching-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/idle/touching-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/question_for_user-button-cap-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/question_for_user-button-cap-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/question_for_user/button-cap/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/question_for_user-pressing-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/question_for_user-pressing-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/question_for_user/pressing-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/read_web-pointing-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/read_web-pointing-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/read_web/pointing-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/respond-hand-and-card-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/respond-hand-and-card-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/respond/hand-and-card/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/verify-hand-and-probe-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/verify-hand-and-probe-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/verify/hand-and-probe/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/view_image-hand-and-stylus-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/view_image-hand-and-stylus-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/view_image/hand-and-stylus/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/write_file-left-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/write_file-left-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/write_file/left-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/write_file-right-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/write_file-right-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R04/review/write_file/right-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H01-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H02-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H03-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H03-2-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H04-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H04-2-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H05-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H05-2-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H06-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H07-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H07-2-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H08-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/H08-2-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/left-finger-outline.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/card-bottom.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/stylus-groove.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/card-spur-precise.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/left-outline-precise.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/stylus-remnant-precise.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/left-small-tip.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R04-hands/evidence/left-right-finger.png`
