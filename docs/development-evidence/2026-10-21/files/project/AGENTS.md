# Yukio：抠图、部件动画与自检

## 用户对“更新”的长期约定

在本项目中，用户说“更新”“同步”“上传提交”等，默认要求完整交付，而不只是提交当前代码或开 PR。检查并同步所有相关入口：GitHub 目标分支及提交、GitHub README 和其他文档、macOS 与 Windows 版本、桌面上实际运行的 App、面向下载的安装包与文件。以同一已验证的源码和资源构建，核对包内哈希、下载地址和运行版本；更新后让用户能实际获得改变。Windows 原生测试和实机结论必须来自 Windows 环境。若某项需要外部环境或缺少必要信息，先完成可独立完成的部分，再明确报告未完成项，不能把 PR 已创建或源码已推送说成全部更新完成。保留无关本地改动，不盲目上传生成物或私密数据。用户明确缩小范围时以该次要求为准。

本节适用于角色抠图、部件蒙版、透明边缘、眼睛和动画素材的制作与修复；普通功能开发不必执行整套素材流程。遵循用户本次要求，保留已确认的画风、姿势、道具与动作含义。

## 工具、素材与正式入口

- 历史部件抠图工具为 **SAM 2.1**：先提供初始选择，再修正蒙版和验收，不能把自动分割结果直接当成成品。
- 当前生产输入为 `sources/approved-animation-rig/`：12 套源图、最终 `*-mask.png`、`allowed-mask.png`、`composition.npz`、`rig.json`、`parameters.json`；来源哈希在 `provenance.json`。用户修正并验收的最终蒙版优先于新的自动分割。
- 正式入口为 `YukioPlayer/tools/motion/make_motion.py` → `approved_motion.py`。直接使用 384×416 的 2 倍源图，按 192×208 点显示；当前头颈固定，六级眼皮独立播放。不沿用历史转头、点头建议。
- 旧 1 倍生成、超分和重新描边流程仅用于明确要求的历史复现（`--legacy`），不得默认用于修复。已透明且验收的素材无需重新抠背景。
- 可复用本地 skill：`~/.codex/skills/cutout-animation-qa/SKILL.md`，调用名 `$cutout-animation-qa`。附带的 `scripts/check_masks.py` 输出蒙版报告与多背景检查图。skill 未安装时仍遵循本文件。

## 完整流程

### 1. 固定输入与对照

先查看原图、最终蒙版和最新验收说明，确认是复用、局部修复还是新分割。记录源文件哈希、尺寸、蒙版坐标系、状态、允许变化区域和目标。完整复制当前实际使用的 `motion` 目录作为 `before`；候选、参数、报告和预览逐轮另存，不覆盖已通过的轮次。

保留主图原始比例、透明度、人物身份及手持关系。不要用重生整张图修补局部蒙版错误。需要抠背景时，区分背景去除与内部部件分割，沿用素材已确认的工具与真实底色，不把白衣、白发或画出来的棋盘格误当透明。

### 2. SAM 初选与精修

仅在新部件或已证实的选区缺陷需要时使用 SAM 2.1，先核实环境、模型和调用入口。记录模型/配置、前景点、背景排除点、框选坐标和候选结果；坐标对应实际工作图。历史 SAM 启动脚本所在工作树已不在本机，不把历史路径写成可运行命令。

对照原图修选手套、手指、头、笔、放大镜、纸张。手与握持道具按接触关系联动；保留黑色描边、细笔杆和镜框，排除蓝色袖口、家具及孤立碎点。原始选择与最终蒙版分别保存，不覆盖用户修正结果，不靠全局腐蚀、膨胀或模糊掩盖错误。

### 3. 蒙版静态自检

产出并实际打开：原图、彩色蒙版叠加、轮廓、棋盘格抠图、黑/白/洋红背景合成。用 100% 和至少 200% 查看完整部件及细节。

检查连通块数/面积、漏选不透明孔洞像素、误选全透明背景像素。当前 Yukio 已验收部件期望 **1 个连通块、0 个不透明漏洞、0 个透明背景像素**。`allowed-mask.png` 是允许变化区域，不按实体部件检查。新任务中真实开孔、多部件可能合理，应按原图记录预期，不能自动删小块或填所有洞。数字通过仍需检查选区语义、描边完整和颜色污染。

### 4. 补底、连接与遮挡

保留被移动部件遮住区域的修补底图，用固定袖口、桌沿和前景道具遮接缝。固定手腕/连接端，让手与道具一起运动；在最大位移时检查重复轮廓、残手、孔洞和错误颜色。复用 `composition.npz` 的预乘 RGBA `base`、`foreground`，包括放大镜移开后的衣服修补。

变换与合成保持一致的预乘 alpha 约定，避免黑边和重影。固定头部应原位替换原像素及 alpha、去掉旧接缝补色，不能把半透明头部叠到旧层上而使描边增厚。

### 5. 动画与眼睛

保持原时间曲线、时长、循环入口、状态语义和独立眨眼；未要求修改的区域保持原像素，家具不漂移。幅度在原尺寸可辨认但不拉断接触，状态之间保持节奏差异。

使用 `gaze_layers.py`：虹膜、瞳孔、高光作为一层在固定眼框内平移，原眼白补底，眼角、睫毛、开口固定。双眼共用位移与限幅，不分别截断；全闭眼不能有虹膜碎片。仅修眼睛时使用 `--preserve-motion-from`，保留对照版本其他身体像素，避免重采样库版本差异影响原动作。

### 6. 编码后自检与实际播放

重新读取导出的 WebP、眼皮图集和 `motion.json`，不能只检查内存帧。核对尺寸、帧索引、时长、loopStart、眨眼映射、alpha、允许区域外变化、开场到循环及循环末到起点。固定头颈修复要求固定区域变化为 0；仅修眼睛要求眼框外像素与对照一致，不能将此条件套用于有意改动手部的任务。

逐状态完整播放至少三次，查看关键帧、最大位移、连续眨眼和循环边界；检查真实速度、暂停逐帧、慢速、原尺寸、放大、多背景、连续状态切换。检查接缝、残影、悬浮部件、接触断裂、同步机械感、闪白、跳帧，并无标签辨认动作。GIF 仅辅助，真实时间 HTML/原生播放用于判断时序。

### 7. 修复闭环与交付

失败记录状态、部位、时间/帧号、证据与原因。选区问题修蒙版，露底问题修补底/遮挡，接触问题修枢轴/幅度，跳变修时间轴，编码问题修导出/读取。不得仅放宽阈值或拿旧报告宣布新产物通过。重检受影响部分及相邻状态；同类失败反复出现且无法定位时保留失败包、说明阻塞，不无限重生图。

交付源图、最终蒙版、提示/修正参数、哈希、补底与遮挡、候选资源、机器报告、预览、实际目视结论。独立评审结论必须来自真实评审，不能代写“通过”。整套动作重新验收可沿用 round_13 的 90/100 且无强制退回项标准；局部修复按任务范围验收。

只有任务包含接入/发布时才替换正式资源、重建同源分页、构建并核验包内哈希及原生播放器。使用 `--check`、`--snapshot`、`--blink-snapshots`；涉及性能再跑 `--motion-benchmark`。Windows 实机结论必须来自 Windows 环境，保留回退基准。

## 当前可运行命令

在项目根目录执行，Python 需 numpy、opencv-python、Pillow。本机现有解释器如下，使用前核实。每轮使用新目录。

```sh
PYTHON=/Users/developer/.cache/yukio-sr/bin/python
mkdir -p YukioPlayer/build
RUN="$(mktemp -d "$PWD/YukioPlayer/build/cutout-review.XXXXXX")"
cp -R YukioPlayer/Resources/Assets/motion "$RUN/before"
"$PYTHON" YukioPlayer/tools/motion/make_motion.py --out "$RUN/after"
"$PYTHON" YukioPlayer/tools/motion/check_motion.py --before "$RUN/before" --after "$RUN/after" --out "$RUN/review" --gif
```

仅修眼睛时改用以下生成和视线检查命令；`check_gaze.py` 要求眼睛以外像素不变，不是任意动画改动的通用检查器。

```sh
"$PYTHON" YukioPlayer/tools/motion/make_motion.py --preserve-motion-from "$RUN/before" --out "$RUN/after"
"$PYTHON" YukioPlayer/tools/motion/check_gaze.py --before "$RUN/before" --after "$RUN/after" --out "$RUN/gaze-review"
```

`--only` 生成仅含选定状态的 manifest，不能直接覆盖完整正式 manifest；现有检查器遍历全部 12 个状态，全量检查要使用完整候选目录。

## 依据

[已验收输入](sources/approved-animation-rig/README.md)、[固定头颈方案](docs/animation-review/neck-stability-sam/README.md)、[目光修复](docs/animation-review/gaze-fix/README.md)、[round_13 蒙版拓扑](docs/animation-review/round_13/mask-topology.json)、[历史独立评审](docs/animation-review/round_13/independent-review.md)。历史聊天“雪绪打字动画首次实测”（94660a0f-4677-bf27-0af7-0af7fa271b86）仅作追溯，已不存在的工作树不是运行依赖。当前要求和修复说明优先于历史试验参数。
