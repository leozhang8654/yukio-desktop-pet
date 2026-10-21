# R01 独立静态抠图评审

**结论：退回。34/34 件完成逐件检查，31 件需返工；3 件仅在本轮静态可见层范围通过。**

审查者：独立 Codex 子 Agent `/root/cutout_independent_review`，未参与制作。只读取委派范围内的原图、蒙版、透明部件、逐件 PNG、scope、冻结哈希及最后读取的机器报告；没有读取制作脚本、README、制作理由、聊天历史或旧评分，没有改动候选。

按独立评审规程先目视后读机器报告。每件从真实源 PNG 解码并按完整选区包围框裁出原图/原始mask/透明部件，100%显示；原图、选区叠加与轮廓200%逐件显示，棋盘格/黑/白/洋红四背景200%逐件显示。之后独立合成并实际打开全部34件100%四背景，另做400%与600%问题特写。逐件参考图不是缩小总览。完整打开的图像和参与显示的原始文件清单在 findings.json 的 opened_files；记录区分原始文件经裁片显示与直接整图显示。

坐标是原始 **1205×1306** 图像，0-based，x向右/y向下；区域写作 `[x0,y0,x1,y1)`。left/right严格沿用文件名。

## 冻结与机器核验

12张源图、34张mask、34张部件，共80个SHA-256全部与 frozen-hashes.json 一致。逐件的源图、mask及候选SHA-256逐项写入 findings.json，完整清单也内嵌在该文件；本报告只绑定这些字节。

制作方机器报告34件拓扑通过；独立重新计算得到全部1连通块、选入源图全透明像素为0、选中部件RGB相对源图无改动。22个虹膜mask均为0/255二值。导出虹膜alpha非零值253/254沿用了原图近不透明alpha，并不能提供选区边缘抗锯齿。机器报告中的“通过”不能消除下面的可见误选、漏选及颜色污染。详细独立核验见 independent-machine-checks.json。

## 必须修正的问题

### F01 · medium · 抗锯齿/轮廓

部件：全部22个虹膜（逐件见下表）。区域：各虹膜完整外周；每件全图包围框见逐件记录，重点是裸露左右边与底边。。

22件均可见阶梯、短横台阶或突出的深色边缘像素；原图柔和过渡被硬选区截断。200%白/洋红背景最清楚，100%也能见到不规则边缘。后读机器数据确认这22个mask只有0/255，导出非零alpha只有253/254，没有选区边缘覆盖率过渡。源图自身253/254透明度不是本问题，也不要求改为255。

建议：逐件沿真实虹膜/高光轮廓精修选区，保留属于虹膜的描边厚度，为暴露边缘提供局部亚像素覆盖率；修掉突刺，不用全局腐蚀、膨胀或模糊替代轮廓判断。固定睫毛、眼白仍留在固定层。

证据：每件 evidence/{state}-{part}-reference.png。
证据：每件 review/{state}/{part}/four-backgrounds-200.png。
证据：evidence/backgrounds100-1.png 至 backgrounds100-6.png。

### F02 · high · 漏选高光

部件：`read_file/iris-left`。区域：[441, 526, 463, 547]。

白色高光左侧被切出明显向内的黑/透明凹槽。原图该位置为连续的圆润白高光，候选在黑和洋红底上都呈咬缺。

建议：恢复高光可见轮廓和抗锯齿，重新区分高光与旁边眼白；不能让颜色阈值产生凹洞。

证据：[evidence/issue-detail-12.png](evidence/issue-detail-12.png)。

### F03 · medium · 轮廓突起/凹陷

部件：`write_file/iris-right`。区域：[614, 512, 638, 549]。

左上侧边出现凸出的深色块，靠近白色高光上方又向内缩成凹口，无法连续跟随原图虹膜边缘。

建议：对照源图修正这段侧边，清除额外暗色凸块，恢复高光上方连续边线，再进行局部抗锯齿。

证据：[evidence/issue-detail-13.png](evidence/issue-detail-13.png)。

### F04 · medium · 误选袖口/颜色污染

部件：`idle/touching-hand`。区域：[420, 810, 437, 829]。

下侧指缝与袖口接触位置残留粉色点及细边，黑底能看到粉色碎片；它们来自固定袖口。

建议：沿手部黑色描边外侧清理粉色袖口残留，保留完整手指线，不扩大缺口。

证据：[evidence/issue-detail-01.png](evidence/issue-detail-01.png)。

### F05 · medium · 误选头发/颜色污染

部件：`failed/hand-and-card`。区域：[346, 591, 415, 643]。

卡片左上圆角和斜上边保留浅绿色外缘，与原图邻接头发颜色一致，黑/洋红底成为浅绿描边。

建议：剔除头发混入的像素，按卡片本身黑边保留抗锯齿；不要把整条黑色卡框向内削薄。

证据：[evidence/issue-detail-02.png](evidence/issue-detail-02.png)。

### F06 · medium · 误选袖口

部件：`failed/hand-and-card`。区域：[326, 680, 376, 760]。

手的左外沿有长条粉色袖口残留，局部还有粉色点，已脱离原图语义成为部件外圈。

建议：沿手部与袖口分界清理残留，保留属于手的黑色轮廓。

证据：[evidence/issue-detail-03.png](evidence/issue-detail-03.png)。

### F07 · high · 漏选可见描边

部件：`failed/hand-and-card`。区域：[387, 727, 414, 760]。

手腕右下侧原图明确可见的一段黑色轮廓，在候选中被切掉；皮肤直接接透明背景，边缘形成斜截口。该线在原图中可见，不是隐藏结构。

建议：恢复该段可见黑色描边及过渡，按原手腕曲线连接上下段，避免切进皮肤。

证据：[evidence/failed-wrist.png](evidence/failed-wrist.png)。

### F08 · medium · 误选袖口

部件：`respond/hand-and-card`。区域：[300, 723, 403, 780]。

手左下外缘带粉色细条；小指上方与卡片下沿之间带粉色袖口三角残片，黑底可明确分辨。

建议：两处分开精修，以真实手部/卡片描边为边界排除固定袖口，不把整个手腕一起侵蚀。

证据：[evidence/issue-detail-04.png](evidence/issue-detail-04.png)。

### F09 · medium · 误选袖口/轮廓尖刺

部件：`read_web/pointing-hand`。区域：[406, 630, 436, 667]。

手右上与袖口/头发交界带粉色片和突出的暗色尖刺，候选右缘不再是单纯手指轮廓。

建议：去除粉袖口及相邻固定线条，保留手指真实外线。手下边被投影遮挡的截面可以保留，不需要补画。

证据：[evidence/issue-detail-05.png](evidence/issue-detail-05.png)。

### F10 · medium · 误选头发/颜色污染

部件：`verify/hand-and-probe`。区域：[381, 602, 423, 647]。

探针装置左上斜边及左侧小凸台外缘带浅绿色头发细条。

建议：排除邻接头发色，保留装置暗色边框的真实厚度与软边。

证据：[evidence/issue-detail-06.png](evidence/issue-detail-06.png)。

### F11 · high · 误选固定底座/针尖轮廓截切

部件：`verify/hand-and-probe`。区域：[457, 713, 514, 784]。

针尖左下带入底座浅青色横弧的一小截；右侧和末端被几何直边截切，形成三角化边缘。源图针尖实际发光边缘与固定底座弧线应分开。

建议：以原图可见探针和其实际发光边缘重新确定局部蒙版，排除固定底座横弧。逐像素核对针尖，不用一个直边多边形同时截取发光探针与底座。

证据：[evidence/issue-detail-07.png](evidence/issue-detail-07.png)。
证据：[evidence/probe-base-junction.png](evidence/probe-base-junction.png)。

### F12 · medium · 误选袖口

部件：`view_image/hand-and-stylus`。区域：[437, 746, 464, 777]。

手指下端靠笔杆的凹槽中带入粉色袖口细片，黑底可见两小条粉色。

建议：沿手指/笔杆外框精修凹槽，去除袖口残片，保持手和笔完整联动组。

证据：[evidence/issue-detail-08.png](evidence/issue-detail-08.png)。

### F13 · medium · 误选键盘

部件：`write_file/left-hand`。区域：[367, 792, 415, 819]。

两处指尖之间及下沿带入粉色键帽/键盘边，黑底形成粉色尖片，属于固定键盘。

建议：分别清理指缝和指尖下方键盘选区，保留指尖黑色轮廓与真实接触端。

证据：[evidence/issue-detail-09.png](evidence/issue-detail-09.png)。

### F14 · medium · 误选相邻粉色区域

部件：`write_file/right-hand`。区域：[735, 771, 758, 806]。

最左侧手指外沿有粉色条状污染，与原图相邻粉色袖口/键盘区域连续。

建议：对照原图外侧深色轮廓精修此段，排除粉色邻物，不削去手指描边。

证据：[evidence/issue-detail-10.png](evidence/issue-detail-10.png)。

### F15 · medium · 边缘颜色污染

部件：`question_for_user/pressing-hand`。区域：[788, 733, 808, 776]。

手右侧外边带较亮的灰青色边条，源图该处紧邻青色投影/反光区域；候选在黑底产生灰白边。

建议：局部重新判断手部黑边与邻接投影的分界及覆盖率，清理外缘灰青污染，保留皮肤内部原有光照。

证据：[evidence/issue-detail-11.png](evidence/issue-detail-11.png)。

## 逐件覆盖与结论

每行均已检查原图、mask、候选、叠加、轮廓及100%/200%四背景。以下包围框只是定位选区，不是把框内每个像素都判为有问题。

| 部件 | 原图包围框 | 结论/问题 | 逐件证据 |
|---|---|---|---|
| `default_work/iris-left` | `[439, 507, 500, 574]` | 退回：F01 | [100/200%对照](evidence/default_work-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-1.png)；[200%四背景](../../qianxia-cutout-R01/review/default_work/iris-left/four-backgrounds-200.png) |
| `default_work/iris-right` | `[627, 516, 695, 580]` | 退回：F01 | [100/200%对照](evidence/default_work-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-1.png)；[200%四背景](../../qianxia-cutout-R01/review/default_work/iris-right/four-backgrounds-200.png) |
| `default_work/trackball-hand` | `[345, 737, 453, 818]` | 静态可见层通过：可见手指和接触端保留；左下斜截是原图设备遮挡边，本阶段允许。四背景未见必须退回的固定邻物误选。 | [100/200%对照](evidence/default_work-trackball-hand-reference.png)；[100%四背景](evidence/backgrounds100-1.png)；[200%四背景](../../qianxia-cutout-R01/review/default_work/trackball-hand/four-backgrounds-200.png) |
| `failed/hand-and-card` | `[330, 581, 516, 758]` | 退回：F05, F06, F07 | [100/200%对照](evidence/failed-hand-and-card-reference.png)；[100%四背景](evidence/backgrounds100-1.png)；[200%四背景](../../qianxia-cutout-R01/review/failed/hand-and-card/four-backgrounds-200.png) |
| `failed/iris-left` | `[435, 501, 497, 559]` | 退回：F01 | [100/200%对照](evidence/failed-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-1.png)；[200%四背景](../../qianxia-cutout-R01/review/failed/iris-left/four-backgrounds-200.png) |
| `failed/iris-right` | `[620, 511, 688, 566]` | 退回：F01 | [100/200%对照](evidence/failed-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-1.png)；[200%四背景](../../qianxia-cutout-R01/review/failed/iris-right/four-backgrounds-200.png) |
| `idle/iris-left` | `[441, 507, 506, 573]` | 退回：F01 | [100/200%对照](evidence/idle-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-2.png)；[200%四背景](../../qianxia-cutout-R01/review/idle/iris-left/four-backgrounds-200.png) |
| `idle/iris-right` | `[629, 517, 698, 577]` | 退回：F01 | [100/200%对照](evidence/idle-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-2.png)；[200%四背景](../../qianxia-cutout-R01/review/idle/iris-right/four-backgrounds-200.png) |
| `idle/orb` | `[519, 717, 614, 811]` | 静态可见层通过：球体的可见黑边、内部星形标记和色带保留；左侧手指遮挡缺口与原图对应，不要求补画完整球体。 | [100/200%对照](evidence/idle-orb-reference.png)；[100%四背景](evidence/backgrounds100-2.png)；[200%四背景](../../qianxia-cutout-R01/review/idle/orb/four-backgrounds-200.png) |
| `idle/touching-hand` | `[384, 734, 528, 828]` | 退回：F04 | [100/200%对照](evidence/idle-touching-hand-reference.png)；[100%四背景](evidence/backgrounds100-2.png)；[200%四背景](../../qianxia-cutout-R01/review/idle/touching-hand/four-backgrounds-200.png) |
| `question_for_user/button-cap` | `[759, 784, 843, 834]` | 静态可见层通过：按钮可见上盖与底座分离；上缘手指遮挡缺口对应原图，不按完整椭圆补画。 | [100/200%对照](evidence/question_for_user-button-cap-reference.png)；[100%四背景](evidence/backgrounds100-2.png)；[200%四背景](../../qianxia-cutout-R01/review/question_for_user/button-cap/four-backgrounds-200.png) |
| `question_for_user/iris-left` | `[439, 496, 505, 568]` | 退回：F01 | [100/200%对照](evidence/question_for_user-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-2.png)；[200%四背景](../../qianxia-cutout-R01/review/question_for_user/iris-left/four-backgrounds-200.png) |
| `question_for_user/iris-right` | `[626, 505, 696, 575]` | 退回：F01 | [100/200%对照](evidence/question_for_user-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-3.png)；[200%四背景](../../qianxia-cutout-R01/review/question_for_user/iris-right/four-backgrounds-200.png) |
| `question_for_user/pressing-hand` | `[712, 718, 804, 791]` | 退回：F15 | [100/200%对照](evidence/question_for_user-pressing-hand-reference.png)；[100%四背景](evidence/backgrounds100-3.png)；[200%四背景](../../qianxia-cutout-R01/review/question_for_user/pressing-hand/four-backgrounds-200.png) |
| `read_file/iris-left` | `[447, 506, 509, 573]` | 退回：F01, F02 | [100/200%对照](evidence/read_file-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-3.png)；[200%四背景](../../qianxia-cutout-R01/review/read_file/iris-left/four-backgrounds-200.png) |
| `read_file/iris-right` | `[637, 516, 705, 577]` | 退回：F01 | [100/200%对照](evidence/read_file-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-3.png)；[200%四背景](../../qianxia-cutout-R01/review/read_file/iris-right/four-backgrounds-200.png) |
| `read_web/iris-left` | `[434, 499, 494, 563]` | 退回：F01 | [100/200%对照](evidence/read_web-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-3.png)；[200%四背景](../../qianxia-cutout-R01/review/read_web/iris-left/four-backgrounds-200.png) |
| `read_web/iris-right` | `[621, 509, 687, 572]` | 退回：F01 | [100/200%对照](evidence/read_web-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-3.png)；[200%四背景](../../qianxia-cutout-R01/review/read_web/iris-right/four-backgrounds-200.png) |
| `read_web/pointing-hand` | `[325, 621, 432, 691]` | 退回：F09 | [100/200%对照](evidence/read_web-pointing-hand-reference.png)；[100%四背景](evidence/backgrounds100-4.png)；[200%四背景](../../qianxia-cutout-R01/review/read_web/pointing-hand/four-backgrounds-200.png) |
| `respond/hand-and-card` | `[302, 588, 532, 778]` | 退回：F08 | [100/200%对照](evidence/respond-hand-and-card-reference.png)；[100%四背景](evidence/backgrounds100-4.png)；[200%四背景](../../qianxia-cutout-R01/review/respond/hand-and-card/four-backgrounds-200.png) |
| `respond/iris-left` | `[440, 499, 504, 558]` | 退回：F01 | [100/200%对照](evidence/respond-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-4.png)；[200%四背景](../../qianxia-cutout-R01/review/respond/iris-left/four-backgrounds-200.png) |
| `respond/iris-right` | `[628, 508, 699, 565]` | 退回：F01 | [100/200%对照](evidence/respond-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-4.png)；[200%四背景](../../qianxia-cutout-R01/review/respond/iris-right/four-backgrounds-200.png) |
| `thinking/iris-left` | `[416, 502, 475, 567]` | 退回：F01 | [100/200%对照](evidence/thinking-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-4.png)；[200%四背景](../../qianxia-cutout-R01/review/thinking/iris-left/four-backgrounds-200.png) |
| `thinking/iris-right` | `[594, 523, 660, 583]` | 退回：F01 | [100/200%对照](evidence/thinking-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-4.png)；[200%四背景](../../qianxia-cutout-R01/review/thinking/iris-right/four-backgrounds-200.png) |
| `verify/hand-and-probe` | `[370, 589, 504, 779]` | 退回：F10, F11 | [100/200%对照](evidence/verify-hand-and-probe-reference.png)；[100%四背景](evidence/backgrounds100-5.png)；[200%四背景](../../qianxia-cutout-R01/review/verify/hand-and-probe/four-backgrounds-200.png) |
| `verify/iris-left` | `[437, 511, 501, 574]` | 退回：F01 | [100/200%对照](evidence/verify-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-5.png)；[200%四背景](../../qianxia-cutout-R01/review/verify/iris-left/four-backgrounds-200.png) |
| `verify/iris-right` | `[623, 520, 695, 578]` | 退回：F01 | [100/200%对照](evidence/verify-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-5.png)；[200%四背景](../../qianxia-cutout-R01/review/verify/iris-right/four-backgrounds-200.png) |
| `view_image/hand-and-stylus` | `[372, 657, 520, 811]` | 退回：F12 | [100/200%对照](evidence/view_image-hand-and-stylus-reference.png)；[100%四背景](evidence/backgrounds100-5.png)；[200%四背景](../../qianxia-cutout-R01/review/view_image/hand-and-stylus/four-backgrounds-200.png) |
| `view_image/iris-left` | `[440, 504, 504, 570]` | 退回：F01 | [100/200%对照](evidence/view_image-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-5.png)；[200%四背景](../../qianxia-cutout-R01/review/view_image/iris-left/four-backgrounds-200.png) |
| `view_image/iris-right` | `[630, 514, 698, 576]` | 退回：F01 | [100/200%对照](evidence/view_image-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-5.png)；[200%四背景](../../qianxia-cutout-R01/review/view_image/iris-right/four-backgrounds-200.png) |
| `write_file/iris-left` | `[440, 507, 499, 570]` | 退回：F01 | [100/200%对照](evidence/write_file-iris-left-reference.png)；[100%四背景](evidence/backgrounds100-6.png)；[200%四背景](../../qianxia-cutout-R01/review/write_file/iris-left/four-backgrounds-200.png) |
| `write_file/iris-right` | `[619, 516, 687, 574]` | 退回：F01, F03 | [100/200%对照](evidence/write_file-iris-right-reference.png)；[100%四背景](evidence/backgrounds100-6.png)；[200%四背景](../../qianxia-cutout-R01/review/write_file/iris-right/four-backgrounds-200.png) |
| `write_file/left-hand` | `[354, 739, 469, 813]` | 退回：F13 | [100/200%对照](evidence/write_file-left-hand-reference.png)；[100%四背景](evidence/backgrounds100-6.png)；[200%四背景](../../qianxia-cutout-R01/review/write_file/left-hand/four-backgrounds-200.png) |
| `write_file/right-hand` | `[741, 747, 849, 812]` | 退回：F14 | [100/200%对照](evidence/write_file-right-hand-reference.png)；[100%四背景](evidence/backgrounds100-6.png)；[200%四背景](../../qianxia-cutout-R01/review/write_file/right-hand/four-backgrounds-200.png) |

## 范围与复审条件

`idle/orb`、`question_for_user/button-cap` 和 `default_work/trackball-hand` 的真实遮挡边属于当前可见层范围，不要求补画隐藏结构。`read_web/pointing-hand` 下边被投影遮挡本身不作为缺陷；F09针对的是另外一段可见右侧边界。思考/读文件手固定、完成整图固定的约束未被扩大为额外部件要求。

本轮未进入动画，没有补底、眼皮、动态播放或原生播放器通过结论。请按问题清单另存新轮次，重做对应逐件四背景检查和机器报告，冻结新哈希后复审修改部件并检查关联边缘。3件局部通过不能用于宣布整套完成。

附件：完整逐文件SHA-256、逐件结论和实际打开清单见 [findings.json](findings.json)；独立机器复核见 [independent-machine-checks.json](independent-machine-checks.json)。
