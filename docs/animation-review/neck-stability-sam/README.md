# 固定头颈：复用已验收 SAM 方案

本次修复恢复 round_13 正式画风、SAM 2.1 小部件蒙版和 v4 独立眨眼，在同一生产素材上固定 12 个状态的头颈。读书目光、手指，写字手与笔，看图手与放大镜，以及其他状态的原部件动作和时间轴均保留。没有新增点头。

## 制作经验与来源

已向原制作聊天“雪绪打字动画首次实测”（01a0c758-2a65-7600-bf78-bc7d22d548c2）发送方案核对请求；发送后聊天历史接口报 missing source rollout，未取得这次请求的新回复。已实际阅读其保存的 `经验文档/动画制作/01-制作方法.md`、`02-踩坑与改进.md`、HANDOFF，以及原生产代码与 round_13 审查文件。

采用的经验：

- SAM 只提供初始选择，复用用户修正过的最终手套、笔与放大镜蒙版，保留描边并排除蓝色袖口污染和孤点。
- 手与握持道具一起运动，固定连接端，由原袖口、桌沿和道具前景遮住接缝。
- 保留修补后的隐藏背景；放大镜移开时露出的衣服使用原生产修补数据。
- 头部固定后直接恢复原图像素与 alpha，移除旧运动头部下方的接缝补色，避免半透明描边叠厚。
- 虹膜在固定眼框内移动，六级眼皮独立播放。当前要求不沿用旧经验中轻微偏头、点头的建议。
- 正式资源不再经过旧 1 倍生成及超分链。历史工作树中残留的正式图集不是发布基准。

已把可复现的生产输入收录到 [`sources/approved-animation-rig`](../../../sources/approved-animation-rig/README.md)。本次入口是 `make_motion.py` → `approved_motion.py`，默认输出候选目录。旧生成/超分必须显式传 `--legacy`。

## 验证结果

[`validation.json`](validation.json) 为实际编码图集检查：全部 12 状态通过。每步检查头颈固定区域；排除独立眼区和道具扫过的区域，头部与原主图逐像素一致、头颈全时间轴像素变化为 0；原头部影响范围之外与修改前图集逐像素一致；12 个循环的末帧与循环起点像素差均为 0。保留原时长与 loopStart，记录开场到循环的相邻帧差值。所有编码眼皮补丁的 alpha 与对应身体帧一致。

已经目视检查全部状态的起始、动作中段、闭眼和循环末帧联系表，并打开读书、写字、看图的放大对比。原生播放器成功生成全状态快照及 161 张身体/眼皮组合快照。测试 App 打包使用当前图集及匹配的无损分页，签名验证通过，详细哈希见 [`runtime-verification.json`](runtime-verification.json)。未替换桌面正在使用的 App；没有在 Windows/Intel 真机上验证这次素材。

## 预览与测试包

项目根目录下：

- `YukioPlayer/build/neck-stability-sam/comparison.html`：全部状态，真实 20 ms 时间步，可暂停、单步、四分之一速度、查看循环接缝及放大头颈。
- `YukioPlayer/build/neck-stability-sam/comparison.mp4` / `.gif`：读书、写字、看图八秒快速对比（20 fps 预览；正式图集为 50 fps）。
- `YukioPlayer/build/neck-stability-sam/all-states.png`、`native-snapshot.png`、`native-blinks/`：全部状态与原生解码检查。
- `YukioPlayer/build/Yukio.app`：本次已修正测试包，包含分页资源。

先前误用旧生成流程的版本移至 `YukioPlayer/build/neck-stability-rejected/`，不要使用该轮的报告或预览代表本次结果。正确修改前基准保留在 `YukioPlayer/build/neck-stability/before/`。
