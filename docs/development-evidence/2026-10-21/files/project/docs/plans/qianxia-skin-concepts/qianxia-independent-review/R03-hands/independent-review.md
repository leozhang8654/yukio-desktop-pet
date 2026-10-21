# R03 手/道具独立复审

**结论：退回。12/12件逐件检查，4件静态可见层通过，8件需返工。**

审查者：独立 Codex 子Agent `/root/cutout_independent_review`，未参与制作，沿用R01标准。只读授权素材、scope、哈希与目视后读取的机器报告；没有读取制作脚本、reference或制作自检结论，没有修改候选。

## 覆盖和冻结

所有12件均从真实原图、mask与透明PNG解码，逐件显示100%原图/mask/部件及100%棋盘格/黑/白/洋红背景；逐件检查200%原图、选区叠加、轮廓和四背景。先完成上述目视，再读取机器数据；随后用500/600%局部图定位问题。原始完整选区包围框在逐件图中显示，没有拿总览代替单件。

33个冻结文件SHA-256全部匹配。`idle/orb`、`question_for_user/button-cap`、`default_work/trackball-hand`的source/mask/part与R01通过字节一致，且本轮也完整重看。实际显示44张图像；逐文件清单与逐件哈希在 [findings.json](findings.json)。

## 已确认的修复

- R01 F07：失败状态手腕的可见黑色描边已恢复。
- R01 F09：网页指向手的粉袖与尖刺已去除，该件通过；下缘投影遮挡截面合理。
- R01 F11：针尖不再混入底座横弧，可见末端形状已恢复；装置另有H03所列问题，因此整件仍退回。

## 必须修正的问题

坐标均为原始1205×1306图，0-based，x向右/y向下，区域为 `[x0,y0,x1,y1)`。台阶、残片及漏线在200%图可辨，500/600%仅用于精确定位。

### H01 · `idle/touching-hand` · medium

原图区域：`[[420, 810, 437, 829]]`。关联R01：F04。

下侧指缝的粉色边片虽缩小，黑底仍可见一小条粉/紫袖口色伸在深色手部轮廓之外，旧F04未完全消除。

建议：沿该凹口局部确认手指描边外侧，清掉剩余袖口色与细小外伸片，保留皮肤内部原有粉色阴影。

证据：[F04.png](evidence/F04.png)。

### H02 · `failed/hand-and-card` · medium

原图区域：`[[398, 582, 435, 612]]`。关联R01：F05, F06, F07。

卡片左上绿色污染和手外缘粉色明显改善，原F07手腕可见描边已恢复。但斜上沿在x约415处出现突兀台阶，局部边框厚度突然变化；原图该段是连续斜边。

建议：把修正区与相邻未改黑框平顺衔接，恢复原斜边的连续轮廓及厚度；保留已恢复的手腕描边。

证据：[card-top-step.png](evidence/card-top-step.png)。
证据：[F05.png](evidence/F05.png)。
证据：[F06.png](evidence/F06.png)。
证据：[F07.png](evidence/F07.png)。

### H03 · `verify/hand-and-probe` · medium

原图区域：`[[409, 591, 440, 618], [376, 632, 390, 651]]`。关联R01：F10, F11。

探针上沿在x约423处存在台阶/边框厚度突变；左侧小凸台靠手的下方仍有浅绿色头发残点。针尖的底座横弧误选已去除，圆润针尖与可见发光主体已恢复，此处旧F11可关闭。

建议：修平装置斜上边修补接缝，逐像素去除小凸台下方浅绿残点且保留装置暗边，保持当前针尖与固定底座的分离。

证据：[probe-top-step.png](evidence/probe-top-step.png)。
证据：[probe-green-remnant.png](evidence/probe-green-remnant.png)。
证据：[F10.png](evidence/F10.png)。
证据：[F11.png](evidence/F11.png)。

### H04 · `respond/hand-and-card` · medium

原图区域：`[[296, 710, 323, 746], [382, 713, 425, 738]]`。关联R01：F08。

手左侧在y约723的修补交界出现横向硬台阶；卡片下沿仍留粉紫袖口色及小暗色矩形突片。原图对应卡片边应为连续斜线，残片来自下方固定袖口。

建议：分别修顺手侧边交界与卡片下沿，清理卡框外侧固定袖口残片，不削薄整段手部黑线。

证据：[respond-side-step.png](evidence/respond-side-step.png)。
证据：[respond-card-under-edge.png](evidence/respond-card-under-edge.png)。
证据：[F08.png](evidence/F08.png)。

### H05 · `view_image/hand-and-stylus` · high

原图区域：`[[426, 756, 455, 785], [437, 746, 464, 777]]`。关联R01：F12。

末端手指靠右的可见黑色轮廓被切掉，皮肤直接接透明，形成直截缺口；同时靠笔杆的指缝仍留粉色袖口小片。该手指黑线在原图可见，不是隐藏结构。

建议：先恢复末端手指真实可见黑色描边及圆弧，再单独清除笔杆凹槽粉袖口；不能用矩形边界或整体切除同时处理两者。

证据：[stylus-finger-cut.png](evidence/stylus-finger-cut.png)。
证据：[F12.png](evidence/F12.png)。

### H06 · `write_file/left-hand` · medium

原图区域：`[[367, 792, 415, 819]]`。关联R01：F13。

指缝清理后仍有粉点，并留下朝下/侧边突出的黑色尖片；这些与固定键盘轮廓连接，候选指尖边缘出现锯齿状突刺而非原手指圆弧。

建议：分别沿各指尖真实黑线整理局部边界，排除键盘残片，修复尖刺和凹口；保留各手指可见黑线的厚度。

证据：[F13.png](evidence/F13.png)。

### H07 · `write_file/right-hand` · medium

原图区域：`[[737, 762, 759, 791], [735, 771, 758, 806]]`。关联R01：F14。

左侧外缘在y约771出现修补交界突点/台阶，沿线还可见少量粉色残边。原图该段手指外线是连续斜线。

建议：连接局部修正上下段的外轮廓，去掉突点与邻接粉色残边，保留手指黑线连续。

证据：[right-hand-step.png](evidence/right-hand-step.png)。
证据：[F14.png](evidence/F14.png)。

### H08 · `question_for_user/pressing-hand` · medium

原图区域：`[[781, 725, 810, 766], [788, 733, 808, 776]]`。关联R01：F15。

原灰青外边已去除，但右上角留下向外伸的黑色尖尾，右缘随后出现细小内凹/台阶；局部轮廓未连续跟随原图手指弧线。

建议：沿手指真实圆弧重修尖尾和凹口，使被清理区与上下描边衔接；保留皮肤内部反光。

证据：[pressing-top-spike.png](evidence/pressing-top-spike.png)。
证据：[F15.png](evidence/F15.png)。

## 逐件结论

| 部件 | 结论 | 证据 |
|---|---|---|
| `default_work/trackball-hand` | 通过：R01通过字节一致，本轮100/200%四背景重看无回退。 | [100/200%原图、mask与四背景](evidence/default_work-trackball-hand-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/default_work/trackball-hand/four-backgrounds-200.png) |
| `failed/hand-and-card` | 退回：H02 | [100/200%原图、mask与四背景](evidence/failed-hand-and-card-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/failed/hand-and-card/four-backgrounds-200.png) |
| `idle/orb` | 通过：R01通过字节一致，本轮100/200%四背景重看无回退。 | [100/200%原图、mask与四背景](evidence/idle-orb-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/idle/orb/four-backgrounds-200.png) |
| `idle/touching-hand` | 退回：H01 | [100/200%原图、mask与四背景](evidence/idle-touching-hand-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/idle/touching-hand/four-backgrounds-200.png) |
| `question_for_user/button-cap` | 通过：R01通过字节一致，本轮100/200%四背景重看无回退。 | [100/200%原图、mask与四背景](evidence/question_for_user-button-cap-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/question_for_user/button-cap/four-backgrounds-200.png) |
| `question_for_user/pressing-hand` | 退回：H08 | [100/200%原图、mask与四背景](evidence/question_for_user-pressing-hand-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/question_for_user/pressing-hand/four-backgrounds-200.png) |
| `read_web/pointing-hand` | 通过：旧F09粉袖与暗色尖刺消除，可见手指边界连续；下方真实投影遮挡截面保持。 | [100/200%原图、mask与四背景](evidence/read_web-pointing-hand-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/read_web/pointing-hand/four-backgrounds-200.png) |
| `respond/hand-and-card` | 退回：H04 | [100/200%原图、mask与四背景](evidence/respond-hand-and-card-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/respond/hand-and-card/four-backgrounds-200.png) |
| `verify/hand-and-probe` | 退回：H03 | [100/200%原图、mask与四背景](evidence/verify-hand-and-probe-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/verify/hand-and-probe/four-backgrounds-200.png) |
| `view_image/hand-and-stylus` | 退回：H05 | [100/200%原图、mask与四背景](evidence/view_image-hand-and-stylus-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/view_image/hand-and-stylus/four-backgrounds-200.png) |
| `write_file/left-hand` | 退回：H06 | [100/200%原图、mask与四背景](evidence/write_file-left-hand-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/write_file/left-hand/four-backgrounds-200.png) |
| `write_file/right-hand` | 退回：H07 | [100/200%原图、mask与四背景](evidence/write_file-right-hand-reference.png)；[200%四背景](../../qianxia-cutout-R03/review/write_file/right-hand/four-backgrounds-200.png) |

## 机器与交付边界

独立重算12件均1连通块，选入源图alpha=0像素均0，所选RGB相对源图改动均0。机器报告中的额外虹膜行没有用于本次结论。拓扑正确不能消除轮廓台阶、邻物残片或手指描边漏选。详见 [independent-machine-checks.json](independent-machine-checks.json)。

球、按钮和手与设备的真实遮挡允许保留；本次不要求隐藏结构补画，也没有补底、眼皮、动画或原生播放结论。请依据局部坐标修正并另存新轮次，保留通过字节，再复查受影响轮廓与相邻接缝。
