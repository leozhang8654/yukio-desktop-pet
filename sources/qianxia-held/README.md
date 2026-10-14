# 千夏拖动姿态

`original.png` 是用户提供的原始透明 PNG，未改像素，SHA-256：

`dbbe355d88c3313f45d26dd7b0806560c90d0baabe1e27c45962844ada3ea213`

原图为 1024×1536。运行图用预乘 RGBA 等比缩为 320×480，在 384×496 的透明画布上放于 (32, 8)，按 192×248 点显示。悬挂点映射原图 (530, 150)，位于头顶；未增加内部部件动画。

重建命令（需要 Pillow）：

```sh
python3 YukioPlayer/tools/skins/build_qianxia_held.py
```

`parameters.json` 保存尺寸、留边、悬挂点及源图哈希。正式资源目录的 `held-provenance.json` 记录输出哈希。已有透明背景不重新抠图，不清除原图的低透明度边缘像素，不改人物、服装、包带或鞋子。
