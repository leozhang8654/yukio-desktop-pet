# 已验收的动画制作输入

此目录保存 round_13 正式资源对应的 12 套主图、最终 SAM 2.1 蒙版、遮挡层和原动作时间轴。恢复依据是“雪绪打字动画首次实测”聊天的原工作树资料、主项目正式 v4 图集和 `docs/animation-review/round_13`；不是该工作树里残留的旧正式图集。

恢复时逐状态核对：原图和每个最终蒙版与 round_13 逐像素相同；原生产渲染器 `naturalize_animations.rig(state, claude_review_fix)` 在开头、1/4、1/2、结尾和循环起点的输出与正式图集逐像素相同。哈希记录在 `provenance.json`。

- `source.png`：384×416 已确认主图；`original-master.png` 保留原始大图。
- `*-mask.png`：最终修过的蒙版，不要重新跑自动分割来替换。`allowed-mask.png` 为允许变化区域。
- `mask-overlay.png`、`contours.png`、`checker-cutouts.png`：已验收蒙版检查视图。
- `composition.npz`：float32 预乘 RGBA 的原背景修补层 `base` 和固定前景遮挡 `foreground`。保留手套、袖口、桌沿、放大镜后衣服的修补。
- `rig.json`：眼框、闭眼曲线、原枢轴、部件参数、50 fps 每步姿态、时长、loopStart 和独立眨眼种子。`head`/`head_x` 仅供历史对照；当前渲染器明确忽略它们。其他部件变换保持原值；目光沿原时间曲线，双眼共用由较小眼框决定的幅度限制。
- `parameters.json`：原生产轮次参数记录。

正式入口：`YukioPlayer/tools/motion/make_motion.py`，默认调用 `approved_motion.py`，直接使用这些 2 倍素材输出 v4 身体图集及六级眼皮补丁。无需超分、重描边、抠背景或重新生成图片。旧实现只有显式 `--legacy` 才会执行。

头颈固定采用在原位置替换原始头部像素（包含 alpha），并移除旧头部接缝补色。不要把固定头部普通叠加到旧接缝补色上，否则半透明边缘会变厚。眼睛变化仍限制在固定眼框内，手和道具继续覆盖在脸前。

眼球转动由 `gaze_layers.py` 处理：从原图中提取虹膜、瞳孔和高光作为同一层，仅做平移；用原眼白采样补齐其后方，眼角、睫毛和眼睛开口保持固定。不要再对整块眼睛做位移场变形，那会将眼角卷进眼白并拉扁虹膜。双眼共用位移与幅度系数，不能分别限幅，以免一只眼停住、另一只眼继续转。原始主图、眼球大小和独立眨眼曲线不变。

`check_gaze.py --before <旧 motion 目录> --after <新 motion 目录> --out <检查目录>` 检查全部视线、眼角固定、双眼相对位移和逐帧平滑度，并从编码后的资源核对眼框外的像素与原动画相同，输出视线与眨眼检查图。

仅修眼睛时，生成命令加 `--preserve-motion-from <已备份的旧 motion 目录>`，逐时间步保留已发布身体像素，只替换眼区。这样也避开不同 OpenCV 版本重采样手部时产生的微小数值差异。眨眼补丁复用相同身体帧与 alpha，只写入眼皮实际改变的像素；覆盖范围包含整个固定眼睛开口，避免闭眼后残留移动虹膜的蓝色碎片。

核验示例（项目根目录，Python 需 numpy/opencv-python/Pillow）：

```sh
python YukioPlayer/tools/motion/make_motion.py --out YukioPlayer/build/neck-stability-sam/after
python YukioPlayer/tools/motion/check_motion.py --before YukioPlayer/build/neck-stability/before --after YukioPlayer/build/neck-stability-sam/after --out YukioPlayer/build/neck-stability-sam --gif
```

参考经验分类：原制作聊天工作树中的 `经验文档/动画制作`；本次头部完全固定，不沿用历史经验里“头随目光轻动”的建议。
