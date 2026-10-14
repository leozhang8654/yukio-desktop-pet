# 千夏拖动姿态接入

用户提供的透明站姿 PNG 仅做等比适配。拖动时绕头顶摆动，松手晃停后恢复当前活动；雪绪素材和千夏 R07 的 24 个动作/眼皮资源文件未改。

- 原图与参数：`sources/qianxia-held/`，生成入口 `YukioPlayer/tools/skins/build_qianxia_held.py`。
- r01 素材与真实时间合成预览：[独立只读评审](qianxia-drag-r01/independent-review/review.md)。包括 source/candidate SHA-256；图像逐像素可由原图和参数复现。
- r02 修正原生窗口包围盒的取整，避免连续拎起/放下的位置漂移；没有更改已审 PNG 或动作资源。[独立补审](qianxia-drag-r02/independent-review.md)。[最大倾角快照](qianxia-drag-r02/native-hang.png)。
- 自检：macOS 214 项测试通过（皮肤/位置测试覆盖 0.5、1、1.25、2 倍），Windows 移植逻辑 281 项测试完成，1 项平台限定测试跳过。原生 `--check`、`--snapshot`、`--blink-snapshots`、`--hang` 完成；60 个比例/倾角/下坠组合未在窗口外缘检出 alpha。
- [四背景检查](four-backgrounds.png)：原图 alpha 支撑含 89 连通块，适配图 6 块，零不透明孔洞/零选中全透明像素。通用单连通检查仍为 false；独立评审按原图及允许的缩放确认这些低透明度边缘特征，没有放宽阈值或删点。
- 全部本机轮次、原始机器报告、实时 HTML 和 PNG 帧保存在 `YukioPlayer/build/qianxia-drag-r01/`、`qianxia-drag-r02/`。HTML 使用实际 Windows 移植绘制器和测试窗口替身，不是 Windows 实机结论。

Windows 原生窗口测试和公开发布不包含在本次本地接入验证中。桌面安装包的一致性结果记录在本机 r02/install-verification.json。
