# 千夏 motion-R01 独立评审

**结论：退回。** 11 个状态的眼皮需返工，respond 的袖口露底需返工；锁屏下未做实播，整套动态验收未完成。

评审者：独立 Agent `/root/cutout_independent_review`，未参与制作。只读候选；未运行制作脚本、未实例化 Rig、未改候选或制作方报告。本报告仅覆盖当前冻结 R01，不继承制作方的通过判断。

候选：`/Users/developer/Desktop/yukio-cloud-handoff/docs/plans/qianxia-skin-concepts/qianxia-motion-R01`。264 个冻结文件实际 SHA-256 全部匹配。冻结清单哈希 `b8a6bb862b2a900af13e01d1e42afce5cffc96b450f6cd5d0d695ef8f86635fc`；逐文件候选及证据哈希见 [candidate-sha256.json](candidate-sha256.json)。

## 实际覆盖与方法

先看逐状态原图对照、真实 WebP 解码的帧和眼皮，再读机器报告。12 个原始输入均独立解码；预乘缩放至 384×416 与 source-2x 精确一致，因此对照图没有借用其他源图。完整对照含 384×416 的 100% 画面及 192×208 逻辑显示参考；动作 ROI 至少 200%，眼皮 300%，四处补底 500%。所有 12 状态极值 ROI 均看黑、白、洋红、棋盘格四背景。

独立解码 12 张身体 WebP 和 11 张眼皮 WebP；逐状态看首帧、极值、回位/末帧及若干中间帧；11 状态看首个目光映射的完整六级眼皮。未逐张目视全部身体帧或全部目光×眼皮组合；机器遍历不能被当作这些视觉检查。实际打开证据共 51 张，完整清单见 findings.json；机器读取文件与目视打开文件分开列出。

## 必须返工

### M01：开始闭眼就替换睫毛线形，眼白边界产生碎白台阶（高）

开始闭合时原有粗上睫毛和外侧翼形立即消失，被短细横线替代；并非原睫毛连续下降。眼白/虹膜周边出现碎白台阶和零碎断边，原形被破坏。11 个有眼皮状态均实际看见同类变化；全闭级未见彩色虹膜残留不能解除前级缺陷。

范围：除 task_complete 外全部 11 状态；唯一身体帧 0 的眼皮闭合 1–6 级，尤其 1–2 级。例 question_for_user 的眼部包围框为编码物理坐标 `[119,147,242,188]`，左眼约 `[124,151,164,184]`、右眼约 `[195,154,237,187]`。逐状态眼框见 findings.json。

[实际解码六级证据](evidence/question_for_user-decoded-lids300.png)。保留原上睫毛厚度及外眼角关系，沿连续轨迹形成六级闭合；逐级以完整遮盖边覆盖眼白和虹膜，清除白碎片。重新编码后复查所有 11 状态的张开→1级与相邻级跳变、全闭无虹膜及回睁回归。

代码与视觉一致：eyes.py 在开始闭合即处理 old_ink，再采用短闭眼线位移，不能保证原睫毛连续变化。这里的判断首先来自实际编码资源，不是仅靠代码推测。

### M02：回答时露出悬空暗残片和杂乱接缝（中，必修）

卡片移开后，粉色袖口内部露出悬空深紫/黑色弧片，卡片下沿附近补底接缝杂乱。cleanplate 本身可见这段孤立暗形，原图中对应轮廓与手/袖口连接，移开后变成不合理残片。不是透明背景颜色变化造成。

编码物理坐标 `[124,229,133,240]`，邻接接缝 `[120,223,142,243]`；原始 1205×1306 图约 `[389,719,418,754]`。body 唯一帧 24 从实际 manifest 的 792 ms 起到位，帧 8 可见过渡。[原图、cleanplate 与编码帧 0/8/24 的 500% 对照](evidence/respond-cleanplate-comparison500.png)。

按固定袖口的真实内外轮廓重做这一小块露底与前景遮挡，移除悬空暗残片并接顺卡片下方/手腕旁边的补线；复查整段进入、最大位移和稳定持卡，保持手卡联动。

## 逐状态结论

| 状态 | 实看身体帧（唯一帧索引） | 静态结论 | 检查重点 |
|---|---|---|---|
| idle | 0,16,17,34,50 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 手与球的极值、回位及固定底座已看；未见明确断接。球和手不同轨迹的实际节奏仍待实播。 |
| thinking | 0,8,16,24 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 托腮手和主体保持固定，眼位极值已看；视线停顿是否自然待实播。 |
| read_file | 0,16,8,24 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 三段目光极值与固定卡片已看，身体未见意外变化。 |
| view_image | 0,45,22,44,65 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 手与笔共同换位，笔尖、袖口、图板边缘及补底极值已看；未见明确脱握或露底碎片。 |
| write_file | 0,3,9,10,20,30 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 左右手极值、指缝、腕端和键盘已看；代码为左 .15/.72/1.89 秒、右 .39/1.56/2.16 秒的错拍短击。节奏可辨认性未实播。 |
| verify | 0,14,25,12,24,36 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 握持、探针尖端左缘、接头、落点、抬起及固定底座已看；未见 R07 尖端缺口回归。 |
| read_web | 0,11,26,9,18 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 点按手极值、腕端与固定屏幕已看；未见明显悬浮或断缝。 |
| default_work | 0,21,16,32,47 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 手与轨迹球接触、腕端和底座极值已看；静态接触尚连续，连续运动自然性未验证。 |
| respond | 0,24,8,16 | M01、M02 退回 | 手与卡共同位移，但露出的袖口有暗残片与不顺接缝，M02 退回。 |
| task_complete | 0 | 静态通过；切换/停留待测 | 一张静止帧，无眼皮资源；原图、透明边与固定主体静态通过。切换/长时停留仍未实测。 |
| question_for_user | 0,8,16,5,11 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 按手与顶帽极值、固定环形底座、袖口与接触点已看；未见整底座跟随或明显指端脱离。 |
| failed | 0,20,7,14 | 身体静态无新增明确缺陷；眼皮 M01 退回 | 卡与手共同上提，腕端、卡片边缘和故障符号已看；未见明确分离。 |

## 数值、代码与结论边界

独立核验：23 个 WebP 与对应 decoded PNG 像素一致；全部身体帧允许区外变化为 0；所有眼皮映射有效、眼区外变化为 0、alpha 不变；独立选取上部头发区 y<140 与下方家具区 y≥300 变化均为 0。后者只覆盖这两个保守区域，不冒充完整头颈语义证明。首尾回接帧相同、时长数组有效；三个 enter_then_hold 状态的 loopStart 以后只有稳定尾帧。task_complete 仅一帧、无眼部资源。R08 同路径输入哈希无差异。详见 [resource-audit.json](resource-audit.json)。

这些数值支持资源完整性，不能排除允许区内错误补底，也不能证明眼皮轮廓正确。制作方 encoded-validation 中的数值通过未作为视觉通过依据。

打字参数确为左右错拍；手持卡、笔、探针的分组与姿态在已看极值保持共同运动。按钮顶帽与手有局部变化，固定底座在已看极值保持稳定；原尺寸能否清楚辨认、轨迹球动作是否自然和全程接触需实播判断。

HTML 的尾段循环实现能保留 once 状态末帧。Swift QA 预览则将一次状态整段自动取模，标注为自动新事件演示，不能用它证明同一事件长时间停留或仅新事件才重触发。两个预览都用固定 4.7 秒相位眨眼；这只能是测试时钟，尚未证明设计所述 2.8–7 秒独立调度、少量双眨和状态切换保留时钟。

## 未完成的动态验收

Mac 锁屏，父任务已记录 CUA 要求用户手动解锁。评审没有绕过锁屏，也没有把解码帧、计数器或机器报告当作观看实播。以下均未完成：真实尺寸与真实速度下循环状态至少三轮；放大、慢速、连续眨眼；进入/循环边界的连续观感；一次状态进入、长时稳定与新事件重触发；连续切换和真实 task bubble 配合；无标签动作辨认。Windows 实机亦未测。

先修 M01/M02、重新编码并冻结新轮，再独立复查受影响状态及关联回归；解锁后补齐动态项目，才能决定整套动画是否通过。R01 保持退回。

## 证据文件

- [evidence/default_work-decoded-detail200.png](evidence/default_work-decoded-detail200.png)
- [evidence/default_work-decoded-lids300.png](evidence/default_work-decoded-lids300.png)
- [evidence/default_work-encoded-four-bg200.png](evidence/default_work-encoded-four-bg200.png)
- [evidence/default_work-source-encoded.png](evidence/default_work-source-encoded.png)
- [evidence/failed-decoded-detail200.png](evidence/failed-decoded-detail200.png)
- [evidence/failed-decoded-lids300.png](evidence/failed-decoded-lids300.png)
- [evidence/failed-encoded-four-bg200.png](evidence/failed-encoded-four-bg200.png)
- [evidence/failed-source-encoded.png](evidence/failed-source-encoded.png)
- [evidence/idle-decoded-detail200.png](evidence/idle-decoded-detail200.png)
- [evidence/idle-decoded-lids300.png](evidence/idle-decoded-lids300.png)
- [evidence/idle-encoded-four-bg200.png](evidence/idle-encoded-four-bg200.png)
- [evidence/idle-source-encoded.png](evidence/idle-source-encoded.png)
- [evidence/question_for_user-cleanplate-comparison500.png](evidence/question_for_user-cleanplate-comparison500.png)
- [evidence/question_for_user-decoded-detail200.png](evidence/question_for_user-decoded-detail200.png)
- [evidence/question_for_user-decoded-lids300.png](evidence/question_for_user-decoded-lids300.png)
- [evidence/question_for_user-encoded-four-bg200.png](evidence/question_for_user-encoded-four-bg200.png)
- [evidence/question_for_user-source-encoded.png](evidence/question_for_user-source-encoded.png)
- [evidence/read_file-decoded-detail200.png](evidence/read_file-decoded-detail200.png)
- [evidence/read_file-decoded-lids300.png](evidence/read_file-decoded-lids300.png)
- [evidence/read_file-encoded-four-bg200.png](evidence/read_file-encoded-four-bg200.png)
- [evidence/read_file-source-encoded.png](evidence/read_file-source-encoded.png)
- [evidence/read_web-decoded-detail200.png](evidence/read_web-decoded-detail200.png)
- [evidence/read_web-decoded-lids300.png](evidence/read_web-decoded-lids300.png)
- [evidence/read_web-encoded-four-bg200.png](evidence/read_web-encoded-four-bg200.png)
- [evidence/read_web-source-encoded.png](evidence/read_web-source-encoded.png)
- [evidence/respond-cleanplate-comparison500.png](evidence/respond-cleanplate-comparison500.png)
- [evidence/respond-decoded-detail200.png](evidence/respond-decoded-detail200.png)
- [evidence/respond-decoded-lids300.png](evidence/respond-decoded-lids300.png)
- [evidence/respond-encoded-four-bg200.png](evidence/respond-encoded-four-bg200.png)
- [evidence/respond-source-encoded.png](evidence/respond-source-encoded.png)
- [evidence/task_complete-decoded-detail200.png](evidence/task_complete-decoded-detail200.png)
- [evidence/task_complete-encoded-four-bg200.png](evidence/task_complete-encoded-four-bg200.png)
- [evidence/task_complete-source-encoded.png](evidence/task_complete-source-encoded.png)
- [evidence/thinking-decoded-detail200.png](evidence/thinking-decoded-detail200.png)
- [evidence/thinking-decoded-lids300.png](evidence/thinking-decoded-lids300.png)
- [evidence/thinking-encoded-four-bg200.png](evidence/thinking-encoded-four-bg200.png)
- [evidence/thinking-source-encoded.png](evidence/thinking-source-encoded.png)
- [evidence/verify-cleanplate-comparison500.png](evidence/verify-cleanplate-comparison500.png)
- [evidence/verify-decoded-detail200.png](evidence/verify-decoded-detail200.png)
- [evidence/verify-decoded-lids300.png](evidence/verify-decoded-lids300.png)
- [evidence/verify-encoded-four-bg200.png](evidence/verify-encoded-four-bg200.png)
- [evidence/verify-source-encoded.png](evidence/verify-source-encoded.png)
- [evidence/view_image-cleanplate-comparison500.png](evidence/view_image-cleanplate-comparison500.png)
- [evidence/view_image-decoded-detail200.png](evidence/view_image-decoded-detail200.png)
- [evidence/view_image-decoded-lids300.png](evidence/view_image-decoded-lids300.png)
- [evidence/view_image-encoded-four-bg200.png](evidence/view_image-encoded-four-bg200.png)
- [evidence/view_image-source-encoded.png](evidence/view_image-source-encoded.png)
- [evidence/write_file-decoded-detail200.png](evidence/write_file-decoded-detail200.png)
- [evidence/write_file-decoded-lids300.png](evidence/write_file-decoded-lids300.png)
- [evidence/write_file-encoded-four-bg200.png](evidence/write_file-encoded-four-bg200.png)
- [evidence/write_file-source-encoded.png](evidence/write_file-source-encoded.png)
