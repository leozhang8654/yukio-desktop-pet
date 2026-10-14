# 千夏拖动姿态 r01：独立只读评审

结论：**通过本轮素材及所提供拖动合成预览评审**。没有发现必须返工的本轮新增描边、造型、色彩、接触或裁切缺陷。本结论不包含安装后的 macOS 原生交互，也不包含 Windows 实机验收；这两项未由本评审执行，不能从本报告推导已通过。

- 审查者：独立 Agent `/root/held_pose_review`，未参与本轮素材制作；遵循 `cutout-animation-qa/SKILL.md` 及 `references/independent-review.md`。
- 日期：2026-10-13（America/Los_Angeles）。
- 轮次：`YukioPlayer/build/qianxia-drag-r01`。
- 范围：用户所供透明 PNG 的等比缩小、透明 padding、头顶悬挂点、既有整图摆动和松手恢复。没有要求内部部件动画、补画隐藏结构或独立眨眼。
- 方法：先实际打开原图、候选、四背景与 200% 细节、轮廓及叠加图，再读取机器报告和制作方自评。制作方意见未代替独立判断。只在本目录生成诊断和报告，未修改原图、候选、参数、冻结清单及制作方报告。

## 输入绑定与独立复核

| 文件 | SHA-256 |
| --- | --- |
| `sources/qianxia-held/original.png` | `dbbe355d88c3313f45d26dd7b0806560c90d0baabe1e27c45962844ada3ea213` |
| `sources/qianxia-held/parameters.json` | `9081beadecbbf2a9697006121ed75113d00229f54ff32267960ad7b92624c435` |
| `after/skins/qianxia/base/held.png` | `74e35643af95cf5dd424e206ff90087bd7e5cd07d07b48e7981304254bf343af` |
| `after/skins/qianxia/base/base-animations.json` | `9e31327b01aaf9d5a4161e4bc9aff00b88efa34f046496fae4fa76fc92ac7e36` |
| `frozen-sha256.json` | `aa50d0b97fa2244f2e598ac3857d2b9492759dd7f1a317064369ffc9e92eacc5` |

完整补充哈希见 [reviewed-sha256.json](reviewed-sha256.json)。独立重新计算冻结清单全部 148 项，全部匹配。

原图为 1024×1536；按预乘 `RGBa` LANCZOS 等比缩至 320×480，再放入 384×496 画布的 (32, 8)，独立重建所得 RGBA 与候选逐像素差异为 **0**。这证明候选严格来自允许的缩放与 padding，没有重绘、改色、改造型或额外 alpha 清理。此数值本身不能替代下述目视判断。

manifest 单帧 192×248 点、pixelScale=2；grip=(98.8125,27.4375) 点，对应源图 (530,150) 的变换位置。该点在头顶发饰附近，整图摆动的受力语义可读。

独立逐文件对比 before/after：仅变更千夏 `base/held.png`、`base/base-animations.json`、`provenance.json`，新增 `held-provenance.json`。其他既有资源逐字节一致。诊断见 [verification.json](verification.json)。

## 实际打开的静态证据与逐部位覆盖

实际打开：原图及候选 PNG；`source-qa/01-source-support-mask/`、`candidate-qa/01-candidate-support-mask/` 下各自的 `cutouts-four-backgrounds.png`、`mask-overlay.png`、`contours.png`；`source-detail-200-0/1/2.png` 与 `candidate-detail-200-0/1/2.png`；`native-hang.png`；`size-comparison.png`。

为避免四背景总览缩小或局部裁图遗漏，另外实际打开本目录的 `source-100-black.png`、`source-100-white.png`、`source-100-magenta.png`、`source-100-checker.png`、`source-bag-200.png`、`source-hair-left-200.png`、`source-hair-right-200.png`，以及 `candidate-200-black.png`、`candidate-200-white.png`、`candidate-200-magenta.png`、`candidate-200-checker.png`。这些仅为诊断合成和最近邻放大，未改动输入。

| 部位 | 覆盖与目视结论 |
| --- | --- |
| 发饰、头发 | 蝴蝶结尖端、黑色外描边、心形与右侧发夹、左右卷发尖与凹弧均与源图对应；未见硬直线切边、缺失发尖或新增邻色污染。 |
| 脸和眼部 | 眼框、瞳孔、高光、脸型和表情完整；没有拆眼或改变表情的迹象。 |
| 手、袖、衣服 | 两手靠拢关系、指缝线、袖口和衣服白色区域保留；无漏透、断腕或重复轮廓。 |
| 包与细带 | 兔形包耳、外轮廓、肩带及两侧细挂带连接完整；没有把白色服装当背景去除。 |
| 腿间开口 | 源图真实透明间隙仍显示对应背景；没有被补实或扩大成缺口。 |
| 鞋 | 鞋带、鞋舌装饰、粉白鞋面和深色鞋底均保留；外缘及两鞋接触附近无新增切角。 |
| 整体透明边缘 | 黑、白、洋红、棋盘格均已检查；未见本轮新增白边、黑色矩形底、残影或整体不等比拉伸。 |

## 动态检查

独立创建 CUA 浏览器页 `http://127.0.0.1:8937/preview.html`，以 1×大小、1×速度运行；页面完成轮数先显示 3，随后显示 7。实际观察播放中的恢复、拿起、横向移动和回落画面，并用暂停/下一帧逐一核对关键边界。又运行 0.25×速度、2×大小，检查黑底和洋红底；白底与棋盘格在正常大小检查。浏览器截图是离散取样，未将其声称为 Windows 桌面录屏或逐显示帧采集。

逐帧核对的 UI 时间及对应 trace 帧（零基索引）：

| 时间 | 帧 | 观察 |
| --- | --- | --- |
| 0.600 → 0.633 s | 17 → 18 | 日常姿态切到新 held；头部位置衔接，整图出现完整，无双重身体。 |
| 1.133 s | 33 | 横向移动负角极值约 −8.1°；发饰、包带、鞋完整，手袖无分离。 |
| 2.167 → 2.200 s | 64 → 65 | 首次松手后恢复已有日常姿态，无 held 残留。 |
| 3.467 s | 103 | 第二次拿起正常触发，未沿用错误姿态或失去身体。 |
| 3.733 s | 111 | 上提左移正角极值约 +8.7°；2×洋红底下查看完整角色，无裁切或接触破坏。 |
| 4.433 → 4.467 s | 132 → 133 | 第二次恢复正常，无透明闪白或重复图层。 |

辅助索引图 [dynamic-keyframes.png](dynamic-keyframes.png) 使用同一已冻结 PNG 帧生成；它用于定位，并非独立的原生系统录屏。实时页循环重置的是测试拖动路径，不能把该重置解释成角色内部动画循环。

已打开真实 macOS 合成器 `native-hang.png` 的 −20°、−10°、0°、10°、20° 静态极值。角色完整处于外层窗口区域，鞋与头发没有外边界裁切；图中的小蓝框是常规窗口参考，不是 held 外层裁切边界。这张 r01 图是旧窗口边界证据，不能当作最终安装包截图：主任务在本评审完成素材部分后报告发现浮点窗口边界可能引起放下位置累计漂移，正另存取整修复后的 r02 原生快照供增量目视检查。该消息不改变本轮冻结素材结论，也不构成本评审亲自验证原生交互通过。

## 机器报告、观察项与限制

目视之后读取 `geometry-check.json`、`alpha-diagnostics.json`、`resource-diff.json`、source/candidate `report.json`、`preview-machine.json`、`self-review.md`。

- geometry 报告的 60 个缩放/角度/sag 组合外缘 alpha 像素为 0；HTML trace 196 帧、约 6.53 秒，两次释放均恢复。此处是所提供合成器与轨迹检查，不是 Windows 实机结论。
- 原始 `check_masks` **仍为 passed=false**：源图 alpha>0 支撑为 89 个连通块，候选为 6 个；二者不透明漏洞和误选完全透明背景均为 0。本报告没有更改阈值或把该结果写成机器全通过。
- 非阻断观察：候选小岛在 (193,15)、(223,30)、(150..156,44)、(59,205)、(281..283,368..369)，最高 alpha 1–4。原图已经含极浅外缘点，候选与原图允许的确定性缩放逐像素相同。四背景与放大检查未出现独立可读碎物、缺线或污染；本任务明确限制为原图等比适配，因此保留这些源图/采样特征，不擅自清理。若未来要做素材净化，应独立立项并重新评审，不能用本报告授权删点。
- 本轮没有新分割或内部部件运动；不适用 SAM、隐藏补底、六级眼皮或雪绪固定头颈逐像素要求。
- **未完成且在本报告范围外**：安装后的真实 macOS 鼠标拿起/移动/松手交互、桌面运行包一致性、Windows 原生窗口和实机测试。由主任务继续验证；本报告只允许引用为冻结素材与所给合成预览通过。

没有必须返工的问题。以上通过结论仅对本报告绑定哈希有效，候选改变后需要重新审查受影响部分。
