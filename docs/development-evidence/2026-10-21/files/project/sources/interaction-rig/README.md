# 抛掷与晕眩输入（candidate-05）

本目录用于新增交互，不替换十二套 `approved-animation-rig` 日常动作。
正式透明 `base/held@2x.png` 按字节复制为 `source.png`（384×480）。
`held-source.png` 是较大的非透明溯源图，与正式输入并不逐像素相同。

- `sam-round-01/prompts.json`：真实 SAM 2.1 Hiera tiny、CPU、checkpoint 哈希、实际源图坐标、点、框、候选编号与分数。原始三个候选及选中结果均保留。
- `*-mask.png`：左右腿和左右衣摆的最终精修蒙版，优先于重新自动分割。
- `refinement.json`：明确的漏选填补、排除像素及右衣摆内衬补选多边形。失败轮次保留在 `mask-review-01` 至 `03`；`mask-review-04` 为最终机器检查。
- `composition.npz`：预乘 RGBA 原图 `base` 与零 `foreground`。本版使用连续逆向坐标变形，未分离出暴露隐藏人体的部件，因此不需要虚构补底。
- `curves.json`：每 20 ms 的屈膝、眼皮、视线、整体脚底摇摆、星星透明度和源图枢轴。
- `allowed-mask.png`：源图允许变形的角色区域；`allowed-output-mask.png`：含透明扩边后所有导出姿态的允许覆盖包络。两者不作为实体蒙版检查。
- `provenance.json`：输入及生成器哈希。机器报告与实际观察分开记录。

输出画布 432×528 / 216×264 逻辑单位；四边各增加 24 源像素，人物不拉伸。
中心 `[108.52944371463218, 116.131783043654]`、脚底 `[124.5,242]` 为输出逻辑坐标（左上原点）。
物理凸包来自源图 alpha > 24，中心坐标转换为 y 向上。腿部只作小幅连接变形；脸和头颈不单独旋转。
强撞、普通、轻撞最大屈膝位移分别为 8、5.5、3 源像素；三档共享原图与锚点。

复现动画（项目根目录；Python 需 numpy、opencv-python、Pillow）：

```sh
python YukioPlayer/tools/interaction/make_interaction.py --out /tmp/yukio-interaction-new
```

重新做 SAM 初选时，安装 [Meta 官方 SAM 2](https://github.com/facebookresearch/sam2) 及其依赖，取得官方 `sam2.1_hiera_tiny.pt`，再运行：

```sh
python YukioPlayer/tools/interaction/segment_held.py \
  --checkpoint /absolute/path/sam2.1_hiera_tiny.pt --out /tmp/yukio-sam-new
```

此命令只产生初选；不能覆盖最终蒙版，也不自动继承精修结论。checkpoint 不放入仓库。
本轮使用本机缓存的 SAM 源码、独立依赖环境与官方模型；完整提示和模型指纹已记录。

检查与限制见 [本轮交付记录](../../docs/animation-review/throw-and-dizzy/README.md)。
