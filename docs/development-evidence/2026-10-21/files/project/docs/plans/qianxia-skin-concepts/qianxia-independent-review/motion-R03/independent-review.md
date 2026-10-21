# 千夏 motion-R03 独立复审（仅只读核验，动态审查终止）

**结论：退回，进入动作幅度返工。独立动态审查未进行。**

独立评审者 `/root/cutout_independent_review`。本阶段只读核验，没有操作 UI，没有读取制作方目视评分。

316 个冻结文件 SHA-256 全部匹配。`inputs/`、`rigs/`、`motion/` 共 226 文件与 R02 逐字节相同；M01/M02 静态关闭可沿用 R02 独立结论。冻结清单哈希：`9760e338b630f2aef930e48bd573b37540eaf7211da7060c2801f4ae185da2dd`。详见 hash-verification.json。

实际预览 app 内打包 motion 资源 47 文件，与候选 motion 同名文件逐字节相同。见 preliminary-audit.json。

已读 Preview.swift 全文：NSApplication 先初始化；manifest/图片从 app bundle Resources/candidate 读取；报告写临时目录；Timer 加到主 common run-loop。时钟门限为窗口 isVisible、未最小化、App active，不再使用先前的 occlusion 位测试。默认一次进入后仅保持尾段；N 新事件及箭头状态切换重置身体 offset，均不重置独立眨眼时钟。

这些是静态代码事实；计数器、日志或哈希不能证明评审者看过连续动画。当前尚未接管 UI，未做独立真实速度三轮、慢速、状态切换、长期保持/新事件验证。V01 保持未完成。后续离散截图必须注明采样覆盖，不作为连续视频的替代。

用户随后实看反馈“动作幅度过小，完全看不见”。该反馈由父任务转达，是用户观察，不是本评审者的实播结论。按最新要求停止动态验收与 UI 操作；本轮未接管 UI。R03 不再作为最终候选，等待新轮冻结后重新检查幅度、接触、袖口及关联回归。上述静态字节核验保留，不解除用户指出的动作可辨认性问题。
