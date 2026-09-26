# 眼球转动：固定眼角和眼白，双眼同步

原算法在整个眼睛区域施加渐变位移场，会将眼角/睫毛颜色带入眼白，并压扁虹膜。现在以原图提取的虹膜、瞳孔和高光为单独图层，做刚性平移；后方眼白由原眼白采样补齐，眼睛开口和眼角保持固定。双眼共用位移与幅度系数，保留原视线时间曲线，适当收小较大转动，避免一只眼先停住而另一只继续移动。

眨眼曲线与随机时序不变；覆盖范围包含完整眼睛开口，修正思考动作转眼后闭眼残留的蓝色碎片。仅替换眼区像素，已发布的身体动画、手部、道具、头颈、alpha 与帧时长保留。

验证结果：

- 12 个状态、3267 个时间步、269 种视线：眼角固定，无反向水平视线。双眼相对漂移最大 0.489 个源像素（2 倍素材，约 0.245 个默认桌面点）；相邻帧虹膜重心变化最大 0.295 个源像素。
- 实际编码身体图集逐时间步比较：眼框外改变像素为 0；循环接缝为 0；全部六级眼皮 alpha 匹配身体帧；所有完全闭眼补丁没有眼睛开口内的蓝色虹膜残留。
- 原生播放器输出的 161 张身体/眼皮组合，alpha 与生成图集完全相同，不透明像素 RGB 最大误差为 0。139 项 Swift 测试通过。
- 已更新并重启 `/Users/leozhang/Desktop/Yukio.app`，签名验证和分页清单校验通过。旧桌面程序保留在 `YukioPlayer/build/gaze-fix/Yukio-before.app`，其中包含上一次透明窗口修复。

报告见本目录 JSON；可交互对比在 `YukioPlayer/build/gaze-fix/review/comparison.html`，眼部检查图为同目录的 `eyes-and-blinks.png`。

复现（项目根目录，Python 需 numpy/OpenCV/Pillow）：

```sh
python3 YukioPlayer/tools/motion/make_motion.py \
  --preserve-motion-from YukioPlayer/build/gaze-fix/before \
  --out YukioPlayer/build/gaze-fix/final
python3 YukioPlayer/tools/motion/check_gaze.py \
  --before YukioPlayer/build/gaze-fix/before \
  --after YukioPlayer/build/gaze-fix/final \
  --out YukioPlayer/build/gaze-fix/review
python3 YukioPlayer/tools/motion/check_motion.py \
  --before YukioPlayer/build/gaze-fix/before \
  --after YukioPlayer/build/gaze-fix/final \
  --out YukioPlayer/build/gaze-fix/review --gif
```

眼睛专用修复使用备份的已发布身体像素，避免不同 OpenCV 版本重新采样手部时产生无关差异。正式结果在 `final`；早期 `after` 候选不用于发布。
