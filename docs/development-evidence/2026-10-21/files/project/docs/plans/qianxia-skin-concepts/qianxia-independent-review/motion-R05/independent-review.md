# 千夏 motion-R05 独立复审

**整体结论：退回（验证未完成）。** R04-F01 打字指形拉长在本轮已看静态姿态中关闭；未发现新的明确静态返工缺陷。此记录属于完整送审流程中的局部诊断复审，不能当作完整动态验收。

评审者：独立 Agent `/root/cutout_independent_review`，未参与制作。先看原图与编码帧，再读三个状态的机器报告；未执行制作脚本、未改候选。遵循最新《千夏动画独立检查要求.md》。

候选：`/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-motion-R05`。375 个冻结文件全部匹配，清单 SHA-256 `f1e6a4855107f037e7d355bb76f6ce8fc01fe53ef80b7bdbe592b69897be01a6`；[逐文件绑定](candidate-sha256.json)。输入与 R04 无差异。其他九个状态身体/眼皮编码与 R04 字节相同；只沿用自己的 R04 静态覆盖，不沿用任何动态通过。

## 本轮复审结论

**write_file：已看静态修正通过。** 左右手由抬起姿态转回原接触姿态，指长和轮廓保持，R04 的指端相对指根向下伸长未复现。左手 ROI `[107,231,156,263]`、右手 `[230,232,270,264]`（384×416 资源物理坐标），看源图、帧0、左按下帧3、右按下帧9/10和回位。袖口/键帽周围未见新的明确断缝或残手。

[左手原图和编码500%对照](evidence/write_file-targeted500.png) · [右手500%对照](evidence/write_file-right-targeted500.png)。代码差异也显示 dy 已置零并改为围绕袖口附近旋转；这一点支持目视结果，不代替动态判断。

**verify：已看静态回归通过。** 重新看帧0、14、25、12、24、36；手与探针共同运动，检查握持、尖端、接头、袖口及固定底座，未发现明确断接、露洞、旧针残片。[原图/补底/编码500%对照](evidence/verify-targeted500.png)。

**failed：已看静态回归通过。** 看帧0、20、7、14，卡片和手保持联动，袖口未见明确悬空暗残片。发生字节变化的眼皮也重新看帧0/20的完整六级，未见旧短细睫毛/碎白台阶回归，全闭无可见彩色虹膜。[手腕500%对照](evidence/failed-targeted500.png) · [极值六级眼皮](evidence/failed-max-gaze-and-backgrounds200.png)。

## 十二状态结果

| 状态 | 状态整体结果 | 静态范围 |
|---|---|---|
| idle | 未测 | 按字节沿用 R04 已看静态覆盖 |
| thinking | 未测 | 按字节沿用 R04 已看静态覆盖 |
| read_file | 未测 | 按字节沿用 R04 已看静态覆盖 |
| view_image | 未测 | 按字节沿用 R04 已看静态覆盖 |
| write_file | 未测 | 本轮重新目视通过 |
| verify | 未测 | 本轮重新目视通过 |
| read_web | 未测 | 按字节沿用 R04 已看静态覆盖 |
| default_work | 未测 | 按字节沿用 R04 已看静态覆盖 |
| respond | 未测 | 按字节沿用 R04 已看静态覆盖 |
| task_complete | 未测 | 按字节沿用 R04 已看静态覆盖 |
| question_for_user | 未测 | 按字节沿用 R04 已看静态覆盖 |
| failed | 未测 | 本轮重新目视通过 |

每状态的动态项目均未完成，所以整体状态列写“未测”；静态子项通过不等于状态动画通过。适用/不适用项和实际帧索引详见 [findings.json](findings.json)。

## 实际覆盖与必要核验

本轮实际打开 27 张独立证据：三状态源图/真实编码帧的 384×416 100% 与 192×208 尺寸参考、200% 动作 ROI、黑/白/洋红/棋盘格极值、500% 手腕/指端对照；失败状态六级眼皮在 300% 和200%重新检查。补充逐帧静态核对：write_file 0–30 共31帧、verify 0–36 共37帧、failed 0–20 共21帧，全部唯一身体帧的手/袖口/道具 ROI 均逐张在200%查看，未新增明确必修缺陷。逐帧编号与ROI见 all-frames-index.json；没有把密集静态图算连续播放。

独立核对三个状态身体 WebP 与 decoded PNG，以及对应眼皮 WebP 与 decoded PNG 均像素一致。三个制作机器报告在目视后读取，单独保存在 [focused-resource-check.json](focused-resource-check.json)，未将其数值通过当作视觉通过。

Preview.swift 相对 R04 仅更改轮次标题和临时报告路径；N 新事件/U 同事件刷新与独立眨眼语义沿用 R04 已审代码。未重新执行 UI，不把代码语义当作事件实测。

## 尚未检查及原因

- 系统 Time Limit 未解除；本轮没有启动或操作预览，没有绕过系统限制。
- 工具没有连续视频输入。前八种循环状态真实尺寸正常速度连续三轮及交界、慢放、眨眼节奏、三个一次状态进入/一分钟保持/同事件刷新/真正新事件、完成保持与切换、五分钟混合观看均未测。
- 用户“动作看不见”的反馈仍待实际尺寸正常速度连续观察，不能凭参数或静态修正宣称解决。
- 正式 App 真实任务气泡、真实状态调度未验证；预览不能冒充正式 App 或 Windows 实机。

R04-F01 静态关闭。保留 R05 冻结；必须补齐动态必查项后再决定整套是否通过，当前保持退回（验证未完成）。

## 实际打开证据

- [evidence/write_file-source-encoded.png](evidence/write_file-source-encoded.png)
- [evidence/write_file-decoded-detail200.png](evidence/write_file-decoded-detail200.png)
- [evidence/write_file-targeted500.png](evidence/write_file-targeted500.png)
- [evidence/write_file-encoded-four-bg200.png](evidence/write_file-encoded-four-bg200.png)
- [evidence/verify-source-encoded.png](evidence/verify-source-encoded.png)
- [evidence/verify-decoded-detail200.png](evidence/verify-decoded-detail200.png)
- [evidence/verify-targeted500.png](evidence/verify-targeted500.png)
- [evidence/verify-encoded-four-bg200.png](evidence/verify-encoded-four-bg200.png)
- [evidence/failed-source-encoded.png](evidence/failed-source-encoded.png)
- [evidence/failed-decoded-detail200.png](evidence/failed-decoded-detail200.png)
- [evidence/failed-targeted500.png](evidence/failed-targeted500.png)
- [evidence/failed-encoded-four-bg200.png](evidence/failed-encoded-four-bg200.png)
- [evidence/write_file-right-targeted500.png](evidence/write_file-right-targeted500.png)
- [evidence/failed-decoded-lids300.png](evidence/failed-decoded-lids300.png)
- [evidence/failed-max-gaze-and-backgrounds200.png](evidence/failed-max-gaze-and-backgrounds200.png)

### 逐帧补充证据

- [evidence/write_file-all-frames-00-200.png](evidence/write_file-all-frames-00-200.png)
- [evidence/write_file-all-frames-09-200.png](evidence/write_file-all-frames-09-200.png)
- [evidence/write_file-all-frames-18-200.png](evidence/write_file-all-frames-18-200.png)
- [evidence/write_file-all-frames-27-200.png](evidence/write_file-all-frames-27-200.png)
- [evidence/verify-all-frames-00-200.png](evidence/verify-all-frames-00-200.png)
- [evidence/verify-all-frames-09-200.png](evidence/verify-all-frames-09-200.png)
- [evidence/verify-all-frames-18-200.png](evidence/verify-all-frames-18-200.png)
- [evidence/verify-all-frames-27-200.png](evidence/verify-all-frames-27-200.png)
- [evidence/verify-all-frames-36-200.png](evidence/verify-all-frames-36-200.png)
- [evidence/failed-all-frames-00-200.png](evidence/failed-all-frames-00-200.png)
- [evidence/failed-all-frames-09-200.png](evidence/failed-all-frames-09-200.png)
- [evidence/failed-all-frames-18-200.png](evidence/failed-all-frames-18-200.png)

## 2026-10-12 独立运行补测追加

原日期记录不变。今日系统限制自然解除后，独立操作原 R05 预览，完成正常运行、超过65秒保持采样、U同事件及N新事件逻辑补测；相应子项通过。连续观看、动作可辨认性、长期舒适度与正式任务气泡仍未测，整体仍退回（验证未完成）。详见 [独立运行补测](runtime-2026-10-12-independent/runtime-review.md) 和 [补测结构化结果](runtime-2026-10-12-independent/runtime-findings.json)。
