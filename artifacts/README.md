# 本地产物

`releases/<版本>/` 集中保存 macOS 压缩包、Windows 安装程序、发布说明和 SHA-256 校验清单。这些二进制不提交 Git。

后续构建脚本仍按原约定输出到各平台的 `build/`、`dist/`。发布完成后可按版本收拢到 `releases/`。

当前 SAM 方案动画对比在 `YukioPlayer/build/neck-stability-sam/`；正确修改前基准保留在 `YukioPlayer/build/neck-stability/before/`。旧流程被否决的结果在 `YukioPlayer/build/neck-stability-rejected/`。动画工具的模型权重保留在 `YukioPlayer/tools/motion/models/`。
