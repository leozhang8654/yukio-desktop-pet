# R05 独立运行补测 · 2026-10-12

**整体仍退回（验证未完成）。** 本次关闭窗口运行与预览事件逻辑的可实证缺口，未新增明确运行缺陷。原静态报告保持有效；没有把截图采样、计数器或等待时间写成连续观看通过。

独立评审者 `/root/cutout_independent_review`，制作方交接后独立按键与取证；未读取制作方本日测试数据。使用原冻结 `qianxia-motion-R05/review/QianxiaMotionPreview.app`，窗口标题“千夏 R05 动画检查预览（尚未通过）”。本次未改候选、未重新生成静态素材、未重跑全量数字报告。候选绑定沿用主报告375文件清单 SHA-256 `f1e6a4855107f037e7d355bb76f6ce8fc01fe53ef80b7bdbe592b69897be01a6`。

## 实际操作与证据

初始交接为总览、深灰、1x、暂停，屏幕153.6秒；此旧计数不作独立证据。按 R 后屏幕归零且仍暂停，再按空格开始本轮。0.5秒截图中 respond/question_for_user/failed 分别为13/8/13帧；11.6秒、62.5秒、72.9秒样本均为保持帧24/16/20，task_complete始终0帧。前八循环状态在不同样本中显示不同帧。该阶段未按 N、未切状态；72.917秒日志 explicit_events 为空。

按 U 的日志时间72.967秒：12个状态的事件ID保持0，restarted=false、offset_before=offset_after=0；随后截图三个一次状态仍为24/16/20。按 N 的日志时间81.017秒：12个状态事件ID从0变1，restarted=true，offset从0改为81.017；81.5秒截图显示一次状态回到13/8/13，90.2秒截图又为24/16/20。全局显示时钟未被 N 清零。

| 本次检查 | 结果 | 范围限制 |
|---|---|---|
| 原R05窗口可用、时钟和画面帧推进 | 通过 | 当前窗口运行样本；旧日期Time Limit记录不改写 |
| 一次进入后超过65秒保持帧 | 通过 | 仅离散采样及日志逻辑，不代表连续65秒观感 |
| U同事件刷新不重启 | 通过 | 12状态预览事件接口，真实任务调度未接入 |
| N新事件重启身体、全局时钟不断 | 通过 | 12状态日志及进入/保持截图；眨眼连续相位未测 |
| 三轮连续目视、循环边界、实际尺寸动作可辨认性、长期舒适度 | 未测 | 无连续视频输入，不能凭计数器关闭 |
| 独立眨眼自然节奏、慢速/放大/多背景及连续切状态 | 未测 | 本次限定补测未完成这些动态视觉项目 |
| 正式App真实任务气泡、真实状态调度 | 未测 | 本窗口是检查预览 |

12个状态均实际出现在总览运行截图中；状态动画整体仍均为“未测”。逐状态程序显示帧覆盖只用于确认运行，见 runtime-findings.json；不表示评审者逐帧连续看过。新事件前独立区间的计数可保留作程序诊断，新事件后的累积计数、静止状态计数均不用于证明观看轮数。

## 实际查看文件

- [00-handoff-paused.png](00-handoff-paused.png)：实际通过 CUA 打开查看的窗口截图。
- [01-reset-paused.png](01-reset-paused.png)：实际通过 CUA 打开查看的窗口截图。
- [02-enter-playing.png](02-enter-playing.png)：实际通过 CUA 打开查看的窗口截图。
- [03-running-sample.png](03-running-sample.png)：实际通过 CUA 打开查看的窗口截图。
- [04-hold-sample.png](04-hold-sample.png)：实际通过 CUA 打开查看的窗口截图。
- [05-over65-before-events.png](05-over65-before-events.png)：实际通过 CUA 打开查看的窗口截图。
- [06-same-event.png](06-same-event.png)：实际通过 CUA 打开查看的窗口截图。
- [07-new-event-enter.png](07-new-event-enter.png)：实际通过 CUA 打开查看的窗口截图。
- [08-new-event-settled.png](08-new-event-settled.png)：实际通过 CUA 打开查看的窗口截图。

日志为原生程序实时报告的只读复制。01至08对应阶段；日志定时刷新，与截图时间略有差异，事件时间以日志为准。所有证据哈希与逐状态记录见 [runtime-findings.json](runtime-findings.json)。

## 交还状态

最后实际查看 [09-final-playing.png](09-final-playing.png)：总览、深灰（background=0）、1x、播放，屏幕178.4秒；同期日志178.000750秒，application_active=true。selected沿用交接值11，本次没有切状态。随后不再操作UI，交由制作方整理测试进程。此间写报告导致运行时间增加，不作为额外连续观看证据。
