# 千夏 motion-R04 独立诊断评审

**整体结论：退回（发现问题＋验证未完成）。** 这是完整送审流程中，对可完成部分的真实诊断记录，不是动态通过。

评审者：独立 Agent `/root/cutout_independent_review`，未参与制作。按《千夏动画独立检查要求.md》执行，先看原图和实际编码帧，后核对机器报告。未看制作方目视评分，未运行生成脚本、未实例化 Rig、未改冻结候选。

候选：`/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-motion-R04`。397 个冻结文件 SHA-256 全匹配；冻结清单哈希 `91a01e8d8e8e342319658a09e2196c59d16f98110404f234f887f5a978fcc7ef`。逐文件绑定见 [candidate-sha256.json](candidate-sha256.json)。

## 已发现的必须修复问题

**R04-F01：打字的左右手指纵向拉长（失败，中等严重度）。** 最大按下时指端下移显著多于指根/掌背，原圆短手指变成长直条，动作由局部伸长产生。不能用幅度变大抵消指形破坏。

- 左手唯一帧 3，首次出现在 manifest 231 ms。资源坐标 ROI `[107,231,156,263]`，重点 `[115,237,141,263]`。[原图/补底/编码帧 500% 对照](evidence/write_file-targeted500.png)。
- 右手唯一帧 9、10，首次时间 462、495 ms，ROI `[230,232,270,264]`。[右手 500% 对照](evidence/write_file-right-targeted500.png)。

坐标均为 384×416 编码物理像素，非 192×208 逻辑点。修复应保留指长及轮廓，用腕/掌受约束抬落或关节转动完成短敲；保持错拍，复查袖口、指端与键帽的接触及相邻帧。代码中随 y 增大的位移权重与本轮 2.5 倍位移放大支持该诊断，判断首先来自原图与真实编码帧。

失败状态曾发现腕旁暗分叉疑点，经 500% 原图/cleanplate/编码对照可见它与固定袖口内沿连接；目前证据不足以认定为悬空残片，不把疑点算已确认失败。保留 [failed-targeted500.png](evidence/failed-targeted500.png)，连续观感仍未测。

## 十二状态结果

| 状态 | 本状态结果 | 本轮已看静态内容 |
|---|---|---|
| idle | 未测 | 手拨球、球的另一极值和固定底座已看；响应先后及是否扰人未测。 |
| thinking | 未测 | 托腮手固定，放大目光的两侧极值与六级眼皮已看。 |
| read_file | 未测 | 卡与手保持固定，三段目光极值及眼皮已看。 |
| view_image | 未测 | 手笔握持、袖口、笔尖与图板接触范围已看，极值无明确脱握/残笔。 |
| write_file | 失败 | 左右指端向下拉长，R04-F01 失败。 |
| verify | 未测 | 手探针共同接近/抬起，尖端、接头、袖口和固定底座已看；未见明确断握或旧针残片。 |
| read_web | 未测 | 手指、袖口和屏前接缝已看；指向/点按实际节奏未测。 |
| default_work | 未测 | 手贴轨迹球的两个极值、固定底座已看；未见明确分离。 |
| respond | 未测 | 实际编码全部 25 唯一帧的手卡/袖口局部已看，R01 M02 暗片未复现。 |
| task_complete | 未测 | 单张静止帧及对号保持，未增加眼睛；进出状态未测。 |
| question_for_user | 未测 | 按手、顶帽压缩、回位与固定底座已看；未见底座一起下沉。 |
| failed | 未测 | 卡手上提和袖口已看。先前暗分叉疑点与固定袖口内沿相连，证据不足以定性为悬空残片，未列确认缺陷。 |

其余状态写“未测”是因为必查动态项目没有完成；不表示每个静态画面失败。已看静态子项通过/失败、眼皮与不适用项逐一列在 [findings.json](findings.json)。

## 实际看过什么

重新读取全部 12 身体 WebP、11 眼皮 WebP 与 12 原始输入。完整源图/首帧/最大差异/末帧以 384×416 100% 对照，并附 192×208 显示大小参考；每状态查看至少 200% 的动作/眼区极值及白、黑、洋红、棋盘格。11 状态分别看首个目光和最大眼区变化帧的全部六级眼皮，300% 原图对照与 200% 四背景；没有目视穷举所有目光组合。

respond 的手卡/袖口 ROI 实看全部 25 个唯一帧；其他状态实看索引在 findings.json。五处疑点分别看原图、真实 cleanplate 与选定编码帧的 500% 对照，另补右手指形 500% 对照。实际打开 65 张独立证据。生成/读取图像不自动算实播。

R01 M01 的短细睫毛替换/碎白台阶与 M02 的回答悬空暗片在本轮已看姿态未复现；闭合级未见彩色虹膜漏出。新放大 gaze 的两侧极值及眼皮重新检查，没有用旧静态通过推断新动画通过。

## 资源与代码核验

原始输入预乘缩放与 source-2x 精确一致。23 WebP 与 decoded PNG 像素一致，所有编码身体帧允许区外变化为 0；眼皮允许区外/alpha 变化为 0，映射和帧索引有效；循环首尾帧相同，三种一次状态 loopStart 后仅保持尾帧。保守固定检查区 y<140、y≥300 变化为 0；没有将这两个矩形冒充完整语义固定区域证明。App 内 47 份 motion 文件与候选一致。见 [resource-audit.json](resource-audit.json)、[bundle-check.json](bundle-check.json)。

已读 Preview.swift 全文、HTML 播放代码及 build_motion.py 相关姿态/变形段。原生与 HTML 的 receiveEvent 只有事件 ID 改变才重置身体 offset；N/“新事件”改变 ID，U/“同一事件刷新”保持 ID，不重置身体或眨眼。默认 once 尾段保持，眨眼使用独立时钟；箭头切换重启所选身体，保留眨眼时钟。代码实现此语义通过检查，但实际 UI 操作及正式 App 事件链未测。计数器、编译或代码不能代替观看。

## 未测与限制

1. 系统限制：父任务报告启动出现 “You’ve reached your limit on QianxiaMotionPreview”。本评审未操作 UI、未绕过 Time Limit，也未看到动画播放。
2. 工具限制：当前没有连续视频输入/实时视觉流。静态解码和离散截图不能满足“亲自看到连续播放”。
3. 所有实播必查项未测：八种循环状态实际大小正常速度连续三轮及循环交界；放大慢速/暂停连续观察；三个一次状态首次进入、长时间保持、同事件刷新、新事件；完成持续静止和进出；连续切换、眨眼节奏、每项一分钟及五分钟混合观看。
4. 真实任务气泡未接入，真实界面未验证；Mac 预览不能冒充正式 App，Windows 实机不在本轮已测范围。
5. 用户上一轮“动作幅度过小，完全看不见”尚未闭环。不能把参数放大、静态差异或文件一致当作实际大小正常速度可辨认性通过。

修复 R04-F01 后另存冻结新轮，重看双手和袖口/键帽相邻回归；动态验证仍需具备真实连续观看条件后补齐。当前保持退回。

## 实际打开证据

- [evidence/default_work-decoded-detail200.png](evidence/default_work-decoded-detail200.png)
- [evidence/default_work-decoded-lids300.png](evidence/default_work-decoded-lids300.png)
- [evidence/default_work-encoded-four-bg200.png](evidence/default_work-encoded-four-bg200.png)
- [evidence/default_work-max-gaze-and-backgrounds200.png](evidence/default_work-max-gaze-and-backgrounds200.png)
- [evidence/default_work-source-encoded.png](evidence/default_work-source-encoded.png)
- [evidence/failed-decoded-detail200.png](evidence/failed-decoded-detail200.png)
- [evidence/failed-decoded-lids300.png](evidence/failed-decoded-lids300.png)
- [evidence/failed-encoded-four-bg200.png](evidence/failed-encoded-four-bg200.png)
- [evidence/failed-max-gaze-and-backgrounds200.png](evidence/failed-max-gaze-and-backgrounds200.png)
- [evidence/failed-source-encoded.png](evidence/failed-source-encoded.png)
- [evidence/failed-targeted500.png](evidence/failed-targeted500.png)
- [evidence/idle-decoded-detail200.png](evidence/idle-decoded-detail200.png)
- [evidence/idle-decoded-lids300.png](evidence/idle-decoded-lids300.png)
- [evidence/idle-encoded-four-bg200.png](evidence/idle-encoded-four-bg200.png)
- [evidence/idle-max-gaze-and-backgrounds200.png](evidence/idle-max-gaze-and-backgrounds200.png)
- [evidence/idle-source-encoded.png](evidence/idle-source-encoded.png)
- [evidence/question_for_user-decoded-detail200.png](evidence/question_for_user-decoded-detail200.png)
- [evidence/question_for_user-decoded-lids300.png](evidence/question_for_user-decoded-lids300.png)
- [evidence/question_for_user-encoded-four-bg200.png](evidence/question_for_user-encoded-four-bg200.png)
- [evidence/question_for_user-max-gaze-and-backgrounds200.png](evidence/question_for_user-max-gaze-and-backgrounds200.png)
- [evidence/question_for_user-source-encoded.png](evidence/question_for_user-source-encoded.png)
- [evidence/read_file-decoded-detail200.png](evidence/read_file-decoded-detail200.png)
- [evidence/read_file-decoded-lids300.png](evidence/read_file-decoded-lids300.png)
- [evidence/read_file-encoded-four-bg200.png](evidence/read_file-encoded-four-bg200.png)
- [evidence/read_file-max-gaze-and-backgrounds200.png](evidence/read_file-max-gaze-and-backgrounds200.png)
- [evidence/read_file-source-encoded.png](evidence/read_file-source-encoded.png)
- [evidence/read_web-decoded-detail200.png](evidence/read_web-decoded-detail200.png)
- [evidence/read_web-decoded-lids300.png](evidence/read_web-decoded-lids300.png)
- [evidence/read_web-encoded-four-bg200.png](evidence/read_web-encoded-four-bg200.png)
- [evidence/read_web-max-gaze-and-backgrounds200.png](evidence/read_web-max-gaze-and-backgrounds200.png)
- [evidence/read_web-source-encoded.png](evidence/read_web-source-encoded.png)
- [evidence/read_web-targeted500.png](evidence/read_web-targeted500.png)
- [evidence/respond-all-25-frames200.png](evidence/respond-all-25-frames200.png)
- [evidence/respond-decoded-detail200.png](evidence/respond-decoded-detail200.png)
- [evidence/respond-decoded-lids300.png](evidence/respond-decoded-lids300.png)
- [evidence/respond-encoded-four-bg200.png](evidence/respond-encoded-four-bg200.png)
- [evidence/respond-max-gaze-and-backgrounds200.png](evidence/respond-max-gaze-and-backgrounds200.png)
- [evidence/respond-source-encoded.png](evidence/respond-source-encoded.png)
- [evidence/respond-targeted500.png](evidence/respond-targeted500.png)
- [evidence/task_complete-decoded-detail200.png](evidence/task_complete-decoded-detail200.png)
- [evidence/task_complete-encoded-four-bg200.png](evidence/task_complete-encoded-four-bg200.png)
- [evidence/task_complete-source-encoded.png](evidence/task_complete-source-encoded.png)
- [evidence/thinking-decoded-detail200.png](evidence/thinking-decoded-detail200.png)
- [evidence/thinking-decoded-lids300.png](evidence/thinking-decoded-lids300.png)
- [evidence/thinking-encoded-four-bg200.png](evidence/thinking-encoded-four-bg200.png)
- [evidence/thinking-max-gaze-and-backgrounds200.png](evidence/thinking-max-gaze-and-backgrounds200.png)
- [evidence/thinking-source-encoded.png](evidence/thinking-source-encoded.png)
- [evidence/verify-decoded-detail200.png](evidence/verify-decoded-detail200.png)
- [evidence/verify-decoded-lids300.png](evidence/verify-decoded-lids300.png)
- [evidence/verify-encoded-four-bg200.png](evidence/verify-encoded-four-bg200.png)
- [evidence/verify-max-gaze-and-backgrounds200.png](evidence/verify-max-gaze-and-backgrounds200.png)
- [evidence/verify-source-encoded.png](evidence/verify-source-encoded.png)
- [evidence/verify-targeted500.png](evidence/verify-targeted500.png)
- [evidence/view_image-decoded-detail200.png](evidence/view_image-decoded-detail200.png)
- [evidence/view_image-decoded-lids300.png](evidence/view_image-decoded-lids300.png)
- [evidence/view_image-encoded-four-bg200.png](evidence/view_image-encoded-four-bg200.png)
- [evidence/view_image-max-gaze-and-backgrounds200.png](evidence/view_image-max-gaze-and-backgrounds200.png)
- [evidence/view_image-source-encoded.png](evidence/view_image-source-encoded.png)
- [evidence/write_file-decoded-detail200.png](evidence/write_file-decoded-detail200.png)
- [evidence/write_file-decoded-lids300.png](evidence/write_file-decoded-lids300.png)
- [evidence/write_file-encoded-four-bg200.png](evidence/write_file-encoded-four-bg200.png)
- [evidence/write_file-max-gaze-and-backgrounds200.png](evidence/write_file-max-gaze-and-backgrounds200.png)
- [evidence/write_file-right-targeted500.png](evidence/write_file-right-targeted500.png)
- [evidence/write_file-source-encoded.png](evidence/write_file-source-encoded.png)
- [evidence/write_file-targeted500.png](evidence/write_file-targeted500.png)
