# 早期交接资料归档

这里保存项目最初的 Cloud 接续资料，仅供追溯。当时的“尚未实现播放器”等描述已过时；当前用法与构建步骤请看 [项目说明](../../README.zh-CN.md)，设计记录在 [HANDOFF.md](../HANDOFF.md)。

- `START_HERE.md`、`PLAYER_REQUIREMENTS.md`、`CONTINUE_PROMPT.txt`：保留原文，其中路径按归档前的仓库结构书写。
- `preview.html`：早期手动演示，图片内嵌，可直接打开。
- `native-current/`：早期原生宠物快照，目录名不代表现在运行的版本。
- `SHA256SUMS.json`：素材交接文件校验清单；路径相对于仓库根目录，已同步本次整理的移动。

在仓库根目录运行 `python3 scripts/verify_package.py`，检查这些文件和仍在使用的源素材。校验不覆盖整个播放器，也不是发布安装包的签名。
