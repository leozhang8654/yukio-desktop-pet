# 千夏抠图 R08：探针尖端左缘修正，等待用户验收

[验收页](index.html) · [原图／修前／修后对照](review/probe-tip-before-after.png)

修复用户指出的探针尖端左侧缺块：在原图坐标[476,742,495,767)范围补回129个蒙版像素，保留原图RGBA与其余部件。80个素材文件中仅探针蒙版和透明部件两文件变化。

[独立复审报告](../qianxia-independent-review/R08-hands/independent-review.md)确认接头到尖端左缘恢复连续，未带入固定底座或衣服，并承认R07对此处的漏检。12件手/道具通过，未变虹膜22件按R04报告与相同哈希沿用。机器检查、逐文件对照、参数与哈希在review/、reference/probe-left-edge.json、SHA256SUMS.json及qa.json。

当前仍是静态可见部件验收；用户确认后才进入补底与动画。五项后续任务保留在reference/后续任务与验收关口.md。本轮未接入、安装或更换正式资源。
