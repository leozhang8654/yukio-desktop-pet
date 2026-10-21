# R06 手/道具独立复审

**结论：退回。11件通过，write_file/left-hand仍需局部修正。** 33冻结文件SHA256全部匹配。旧R05-H01的下弧描边漏选已关闭；修复上端新增内部alpha漏底。

本轮1件修改项完整目视，另抽看 failed/hand-and-card、view_image/hand-and-stylus。11件沿用项的原图/蒙版/部件与R05已通过项字节一致；其中9件本轮未重复目视。只判断手/道具静态可见层。

## R06-H01：内部软alpha残留（medium）

原图区域 `[425,768,452,797)`，重点 `[430,770,437,783)`。坐标为1205×1306原图，0-based。

长指左下弧描边已恢复，旧R05-H01的漏选关闭；但修补上端保留了原外边界的半透明alpha。这些像素如今被新不透明选区包围，变成内部漏底细槽和孤立软透明点，洋红底出现细亮槽/亮点。原图此处是连续深色区域，不存在亮点或孔洞。

定位数据：(435,776) alpha211、(435,777) alpha108，周围为255；x431、y773–779仍残留128–195的一段旧软边。该位置在本轮扩大描边后已不再是真实外边界。

修正建议：按修补后的新边界区分内部和外缘：只恢复内部遗留软边/孤立低alpha像素，消除漏底；真实指缝外缘继续保留抗锯齿，不整体填平指缝或重画RGB。复看上端衔接、下弧及键盘残片。

证据：[上端1000%对照](evidence/long-finger-upper-join.png)、[下弧600%复查](evidence/R05-H01-1-roi600.png)、[整手原图/选区/轮廓](evidence/write_file-left-hand-reference.png)。

## 逐部件结论

|状态|部件|结论|本轮依据|
|---|---|---|---|
|default_work|trackball-hand|通过|相同字节沿用，未重复目视|
|failed|hand-and-card|通过|相同字节+目视抽查|
|idle|orb|通过|相同字节沿用，未重复目视|
|idle|touching-hand|通过|相同字节沿用，未重复目视|
|question_for_user|button-cap|通过|相同字节沿用，未重复目视|
|question_for_user|pressing-hand|通过|相同字节沿用，未重复目视|
|read_web|pointing-hand|通过|相同字节沿用，未重复目视|
|respond|hand-and-card|通过|相同字节沿用，未重复目视|
|verify|hand-and-probe|通过|相同字节沿用，未重复目视|
|view_image|hand-and-stylus|通过|相同字节+目视抽查|
|write_file|left-hand|退回R06-H01|完整目视+旧ROI+邻接回归|
|write_file|right-hand|通过|相同字节沿用，未重复目视|

## 检查与冻结绑定

实际显示11张图，包含100%/200%棋盘、黑、白、洋红四背景，原图、选区叠加、轮廓及600%/1000%细节。先目视后机器。

12件基本拓扑均为1连通块、0不透明内部孔洞、0所选透明源像素、0所选RGB改写。注意：0孔洞是alpha>0二值统计，本次211/108等部分透明漏底不在其检测范围内。

完整33文件哈希、逐部件结论与实际解码清单见 [findings.json](findings.json)；机器复算见 [independent-machine-checks.json](independent-machine-checks.json)。

## 实际显示文件

- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/failed-hand-and-card-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/failed-hand-and-card-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R06/review/failed/hand-and-card/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/view_image-hand-and-stylus-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/view_image-hand-and-stylus-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R06/review/view_image/hand-and-stylus/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/write_file-left-hand-reference.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/write_file-left-hand-background100.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-cutout-R06/review/write_file/left-hand/four-backgrounds-200.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/R05-H01-1-roi600.png`
- `/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-independent-review/R06-hands/evidence/long-finger-upper-join.png`
