# 抛掷、碰撞与落地晕眩：实现与验证记录

本轮执行 2026-10-09 的[实施计划](../../plans/throw-and-dizzy-ai-prompt.zh-CN.md)。
实现已接入本地源码和资源；本轮为开发／预览交付，未推送 GitHub、发布安装包或替换用户原有桌面 App。
**Windows 原生验收尚未完成**。用户已确认有测试机，连接信息待提供。

## 已实现

- 两端从输入事件采集最近 100 ms 的加权速度；停手衰减、最后反向、短样本和重复／非有限时间均有明确处理。松手合并一次钟摆切向惯性，合向量限幅。
- 共享 `interaction/physics.json`：120 Hz 固定步长、连续凸包碰撞、四面完整屏幕围墙、支持约束、摩擦、低速停止反弹、停稳后晕眩、恢复最新活动。平台输入和坐标转换独立。
- 松手后锁定当前显示器；macOS 用 point 和 `NSScreen.frame`，Windows 用相对 `rcMonitor` 的局部逻辑单位。包含角度扫掠、角落双法线、迭代预算及极小房间降级。
- 单次释放分配新的会话编号；飞行／晕眩／恢复时按下立即抓稳，未拖动的释放作低速下落，不触发聊天。取消、关闭设置、隐藏、缩放、屏幕变化和休眠清理交互。
- 飞行使用独立约 60 Hz 绘制定时器；任务路由仍按原节奏更新。气泡暂时收起，已打开的回答卡固定位置，恢复时使用最新任务并保存稳定落点。
- 两端设置增加「抛掷互动」，默认开启；关闭后使用旧的拖动摆放。右键、Control-click 和正常纯点击不抛掷。
- 六段动画及四个轻／中撞击变体。三档局部缓冲幅度、撞击时长和晕眩时长不同；停稳并播放完整落地反应后才进入晕眩。最终摇摆按整周期接入恢复，避免中途归正跳变。
- 独立六级眼皮、角色本体命中蒙版、星星前后遮挡；星星不挡鼠标、不参与物理。两端索引、分页、资源哈希检查和诊断命令已接入。

## 输入、素材和本轮隔离

工作树起始已有大量改动。本轮先记录状态与哈希，并备份日常 motion、held、base 和既有代码；未 reset／clean／全仓库提交。
本机完整工作记录：`YukioPlayer/build/throw-dizzy-20261009-194744/`。
该目录含基准、五轮候选、失败证据、原生截图、独立预览 App 和 Windows 测试包。

最终输入在 [sources/interaction-rig](../../../sources/interaction-rig/README.md)。真正执行了 SAM 2.1 初选，并保留原始候选、最终蒙版、精修坐标、模型哈希及补底说明。
四个部件均为 1 连通块、0 不透明孔洞、0 透明背景误选。
已在四种背景查看最终抠图，并检查 200% 蒙版叠加。发现的衣摆内衬漏选和脱离边缘像素已分别修正；失败轮次未覆盖。

当前方案用同源连续逆向变形：脸和头颈保持整体，脚踝固定，膝盖与衣摆小幅运动；没有重生成整张人物，没有把未知身体区域补画出来。
十二套原有 motion 的 25 个文件与本轮基准哈希一致。它们在 Git 中已有的修改不属于本轮。

## 验证结论

| 项目 | 状态与证据 |
| --- | --- |
| Swift 回归 | 188 项通过；含跨语言共享轨迹、解析自由落体和速度采样 |
| Python 回归 | 257 项，1 项跳过，其余通过；Win32 使用替身，不能视为 Windows 原生结果 |
| 共享轨迹 | 10 种场景；Swift / Python 位置误差检查 < 0.00001 逻辑单位，事件时差 < 1/120 s；无求解耗尽；四种绘制刷新率一致 |
| 编码回读 | 10 个片段／变体的尺寸、索引、时长、循环接缝、眼皮 alpha、角色命中区域及允许覆盖范围通过；原 25 文件不变 |
| 透明边缘 | 无 alpha > 24 的实体像素触及输出画布边缘；dizzy-loop 某帧有 1 个 alpha=1 的重采样边缘像素，报告保留该值 |
| 分页 | 十二日常动作及所有新动作／眼皮逐像素无损检查；manifest 同时绑定 motion 和 interaction 哈希 |
| macOS 离屏原生 | 实际 ImageIO / CoreGraphics 解码绘制、三档轨迹；581 帧，无超过 2 point 的显著像素越界，无求解耗尽。p95 3.01 ms，最大 19.37 ms，峰值常驻内存 312.6 MiB；视口裁切检查 0 帧越界。见 [原生报告](native-report.json)、[内存记录](native-memory.txt) |
| macOS 实际窗口 | 隔离 App 使用真实 PetPanel、显示器矩形及定时器完成三次落地／晕眩／恢复；记录副屏负 x 坐标、两屏均 2×。最终视图 192×208、图像 384×416，脚底与屏幕底部对齐。三档 p95 更新成本约 7.4 / 9.7 / 3.6 ms，最大约 41.8 ms，仍有偶发慢帧，不能宣称每一帧稳定 60 fps。见 [实际窗口记录](native-window.json) |
| 实际输入／遮挡 | 自动化工具能启动、截图该非激活面板，但尝试坐标命中返回不支持的辅助功能操作；完整手动抛接、Dock／菜单栏遮挡、拔屏／混合 DPI 尚待人工实测 |
| Windows 原生 | 待测试机；已准备真实分层窗口三档回放、PowerShell 入口及测试包，不把 macOS 上 Python 成功写作 Windows 通过 |

HTML 已在原尺寸和 200%、慢速、暂停逐帧、棋盘格／黑／白／洋红背景打开检查，各片段实时预览运行超过三轮。
已查看编码后关键帧和原生闭眼图：手腕、腿、衣摆无可见分离或重复轮廓；全闭眼无残留虹膜，头颈未单独摆动，晕眩有整体失衡和半垂眼。
这些是本轮实际抽样观察，**不是独立评审，也不等同于完整人工连续抛接验收**。恢复至桌前任务的观感仍应在实机手动切换时确认。

## 本地复现

以下在仓库根目录执行；`python` 指装有 Pillow、numpy、opencv-python 的解释器。
每轮使用新目录；不要把 `--only` 的不完整索引覆盖正式资源。

```sh
swift test --package-path YukioPlayer
PYTHONPATH=YukioWin python -m unittest discover -s YukioWin/tests
python YukioPlayer/tools/interaction/replay.py --out /tmp/throw-traces.json
python YukioPlayer/tools/interaction/make_interaction.py --out /tmp/interaction-new
python YukioPlayer/tools/interaction/check_interaction.py \
  --assets YukioPlayer/Resources/Assets \
  --baseline YukioPlayer/build/throw-dizzy-20261009-194744/before \
  --out /tmp/interaction-review-new
python YukioWin/scripts/prepare-windows-assets.py \
  --source YukioPlayer/Resources/Assets --output /tmp/yukio-pages-new
swift build --package-path YukioPlayer -c release
YUKIO_ASSETS=/tmp/yukio-pages-new YukioPlayer/.build/release/YukioPlayer --check
YUKIO_ASSETS=/tmp/yukio-pages-new YukioPlayer/.build/release/YukioPlayer --interaction-check /tmp/native-interaction-new
YUKIO_ASSETS=/tmp/yukio-pages-new YukioPlayer/.build/release/YukioPlayer --snapshot /tmp/actions.png
YUKIO_ASSETS=/tmp/yukio-pages-new YukioPlayer/.build/release/YukioPlayer --blink-snapshots /tmp/blinks-new
YUKIO_ASSETS=/tmp/yukio-pages-new YukioPlayer/.build/release/YukioPlayer --motion-benchmark
```

`--interaction-check` 的截图含边界、姿态、时间、速度与事件计数调试叠加。
`--interaction-demo` 或预览 App 的 `YukioInteractionDemo` plist 标记驱动三次真实窗口回放；专用设置域与独立包标识避免修改日常 App 设置。
`YukioInteractionDemoOutput` 指定实际窗口记录文件。预览包是本机 ad-hoc 签名开发产物。

## Windows 接手与人工验收

解压本轮 `Yukio-Windows-interaction-test.zip`，进入其中 `YukioWin`：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\smoke-interaction.ps1 -Python .\.venv\Scripts\python.exe
```

生成 `build\interaction-check\windows-native.json`。随后用同一解释器 `-m yukio` 启动正常窗口，完成下列检查并记录机器、屏幕、DPI、资源哈希与日期：

1. 左／右／上／下／斜抛、轻放、急停 150 ms 后释放、最后反向甩、普通点击／右键／Control-click。
2. 空中、撞击、晕眩、恢复分别接住并重抛；抓取首帧不跳，旧手势不污染新释放。
3. 四边与角落、地面零高度、用户缩放、负坐标副屏、100%／150%／200% DPI 和跨屏拖动。
4. 改缩放、关闭开关、隐藏／显示、失去捕获、拔屏、休眠唤醒、重启；无卡住定时器或离屏角色。
5. 空中切换任务，确认恢复最新动作；打开的问题／回答卡及未发送输入保留。
6. 三档各至少三次完整播放，检查地面接触和全身→桌前衔接；录下任务栏／菜单栏／Dock 遮挡，不改工作区冒充完整屏幕。
7. 在没有编译、图集生成等竞争工作时测量绘制耗时和峰值内存。目标 60 Hz；报告原生分层窗口实际成本，不能只报纯物理耗时。

本轮没有生成 Windows 可执行文件或声称其通过实机验收。测试源包仅包含代码、所需资源和验证入口，不包含本机会话记录、设置或 SAM 模型。

## 可审查交付文件

- [逐文件起始／结束哈希](source-state.json) 与 [本轮代码 patch](task-changes.patch)：相对本轮开始时的工作文件，避免混入此前未提交改动。
- [编码检查](encoded-validation.json)、[实际观察与待测项](visual-review.json)、[包内一致性](package-verification.json)、[全部状态解码耗时](motion-benchmark.json)。
- [离线动画预览](preview.html)、[关键帧总览](contact-sheet.png)、[原生晕眩帧](native-dizzy.png)、[恢复后的实际视图](native-normal.png)。

本地隔离 App、Windows 源码测试 ZIP 和全部失败／中间记录位于本轮 `YukioPlayer/build/throw-dizzy-20261009-194744/`，未作为发布物上传。
本机没有 Windows，不能构建或验收 Windows 可执行包。macOS 自动化面板的坐标操作分别返回不支持的辅助功能操作、移动窗口位置不存在；没有把这些尝试写成手动抓取通过。
