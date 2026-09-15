# 生成源图

这些源图保留较高分辨率，背景为均匀洋红色，不能直接当作透明桌面素材使用。最终可播放透明图条在 `assets/activities/`。

- `thinking/read_file/view_image/write_file-source.png`：各为一行四格。
- `verify/respond-source.png`：各为一行四格。
- `read_web-corrected-source-2x2.png`：修正平板的两列两行四格，按阅读顺序 0、1、2、3。

文件实际尺寸见 `references/image-inventory.json`。原生图集单格为 192×208，但源图不一定满足这个尺寸，不要按固定 192 像素直接裁源图。

先按等分网格切格，再提取背景、统一等比缩放与锚点。桌椅不应跟随“呼吸”变形。修正平板源图是最终版本，旧的背面触控图没有打包。
