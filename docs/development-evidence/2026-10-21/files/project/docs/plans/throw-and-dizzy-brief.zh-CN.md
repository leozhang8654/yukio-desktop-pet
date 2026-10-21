**雪绪「抛出去、撞墙、落地晕眩」白话计划**

这是研究后的制作计划，目前尚未修改 App。详细的执行要求在 [AI 执行 prompt](throw-and-dizzy-ai-prompt.zh-CN.md)。

1. **甩手就飞。** 保留现在拎起、晃动的效果，松手时往哪甩就往哪飞，甩得越快飞得越远；停住再松手就往下掉。
2. **屏幕四边都能碰。** 撞墙后反弹、减速，最终落到底边，不穿墙、不一直弹。
3. **落地晕一下。** 先缓冲，可能小弹一下，再轻晃身体、眼神发懵、头顶转小星星，约两秒恢复。轻放反应小，重摔明显；随时能再次拎起。
4. **沿用旧抠图流程。** 保留雪绪的画风和比例。新部件用 SAM 2.1 初选、精修、补底，再检查边缘和实际动画；合格旧蒙版直接复用。
5. **先做好手感，再做好表演。** 先测抛出和碰撞，再制作晕眩，最后在 Mac、Windows 分别检查缩放、连续抛接和流畅度。

借鉴依据：用 [Box2D](https://box2d.org/documentation/md_simulation.html) 的碰撞与停稳原则；参考 [Google 官方甩动手势](https://developer.android.com/develop/ui/views/animations/fling-animation) 如何从手势速度接续运动；参考 [Animation Mentor](https://www.animationmentor.com/blog/squash-and-stretch-the-12-basic-principles-of-animation/) 的落地缓冲和重量感。具体力度和时长是为雪绪设计的试调值，并非照搬某款游戏的数据。

默认：以松手所在屏幕为一个房间，地面在最底边；Dock／任务栏遮挡会实际检查。提供「抛掷互动」开关，关闭后照旧拖动摆放。
