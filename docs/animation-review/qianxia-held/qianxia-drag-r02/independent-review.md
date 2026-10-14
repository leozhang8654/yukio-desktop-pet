# 千夏拖动姿态 r02：原生最大角快照增量独立评审

结论：**通过本次原生合成器静态快照补审**。r01 的原图、候选 PNG、manifest 及其素材/HTML 评审结论继续有效。本补审没有执行安装后的鼠标拖动，也没有执行 Windows 实机测试，不宣布完整桌面交互或发布验收完成。

审查者：独立 Agent `/root/held_pose_review`。日期：2026-10-13（America/Los_Angeles）。本审查未参与制作或代码修复；先实际打开 r02 `native-hang.png`，再读 `changes.md`、冻结清单、`native-hang.log` 与 `swift-tests.log`，并只读核对相关代码与测试入口。

## 输入与变更边界

- r02 `native-hang.png` SHA-256：`191b2ac0338fe3575ec5c7931188c2be0b114fe8372c0148c4acf7e1d8370213`。
- r02 `incremental-sha256.json` 列出的 5 项（图片、两份日志、main.swift、SkinTests.swift）由审查者独立重算，全部匹配。
- r01 `frozen-sha256.json` 的全部 148 项再度独立重算，全部匹配，PNG 与 manifest 未变。
- 沿用的 held PNG SHA-256：`74e35643af95cf5dd424e206ff90087bd7e5cd07d07b48e7981304254bf343af`。
- 沿用的 held manifest SHA-256：`9e31327b01aaf9d5a4161e4bc9aff00b88efa34f046496fae4fa76fc92ac7e36`。

r02 将旋转及 sag 扩展后的包围盒取 `integral`，使 frame 偏移和原生窗口取整一致。静态快照标注的窗口从 r01 334×316 变为 r02 334×317，抓点距上边从 60 变为 61；这属于窗口包围盒变化，未改变角色 PNG。

## 实看覆盖与判断

实际以原始分辨率打开 [native-hang.png](native-hang.png)，逐列检查 −20°、−10°、0°、10°、20°。蝴蝶结尖、左右头发、双手袖口、兔形包及细挂带、腿间开口和双鞋均完整。两个最大角的头发与鞋仍位于外层窗口内，未出现新裁切、拉伸、重复轮廓、残手或接触断裂。橙色悬挂点维持头顶附近的语义。没有必须返工的静态问题。

`native-hang.log` 给出 −20°脚偏左、+20°脚偏右的方向检查。`swift-tests.log` 记录 arm64e-apple-macos14.0 上 214 项测试通过；相关参数化测试 `switchPreservesActivityAndSettings(scale:)` 包含 0.5、1、1.25、2 四档。只读核对调用的 `skinSwitchForCheck()` 确实执行三次拿起/松手/恢复，并精确比较恢复后的窗口 origin。这支持主任务报告的回归测试结果，**不是本审查者亲自操作桌面后的结论**。

r01 的 `native-hang.png` 保留为旧窗口边界证据。最终代码的静态最大角证据应引用本轮 r02 图；最终安装包和桌面操作仍需由主任务独立核验。

完整素材和 HTML 覆盖见 [r01 独立报告](../qianxia-drag-r01/independent-review/review.md)。本次没有修改 r01 候选或冻结文件。
