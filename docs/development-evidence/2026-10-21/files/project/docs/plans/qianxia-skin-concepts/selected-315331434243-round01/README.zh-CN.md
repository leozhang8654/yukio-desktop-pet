# 千夏科幻桌宠 · 首轮静态图

用户选择：`315331434243`。12 个数字按现有工作状态顺序对应下表。

用浏览器打开 [preview.html](preview.html)，可切换浅灰、白、深色和棋盘格底色，按 192×208 或放大尺寸查看。图片本身保持透明 PNG，未通过代码裁切、重绘或改色。

| 顺序 | 状态 | 选项 | 原图 |
|---|---|---|---|
| 01 | 空闲·磁吸小玩具 | 3 | [01-idle.png](01-idle.png) |
| 02 | 思考·节点图推演 | 1 | [02-thinking.png](02-thinking.png) |
| 03 | 读文件·层叠文件标签 | 5 | [03-read_file.png](03-read_file.png) |
| 04 | 看图·透光检查台 | 3 | [04-view_image.png](04-view_image.png) |
| 05 | 写文件·分体键盘控制台 | 3 | [05-write_file.png](05-write_file.png) |
| 06 | 验证·诊断探针 | 1 | [06-verify.png](06-verify.png) |
| 07 | 浏览网页·扇形链接面板 | 4 | [07-read_web.png](07-read_web.png) |
| 08 | 其他工作·轨迹球操作 | 3 | [08-default_work.png](08-default_work.png) |
| 09 | 回答·电子明信片 | 4 | [09-respond.png](09-respond.png) |
| 10 | 完成·勾选控制台 | 2 | [10-task_complete.png](10-task_complete.png) |
| 11 | 提问·呼叫按钮 | 4 | [11-question_for_user.png](11-question_for_user.png) |
| 12 | 失败·故障数据卡 | 3 | [12-failed.png](12-failed.png) |

## 本轮范围

使用内置 imagegen，以用户角色参考图为身份依据，先生成空闲图作为科幻桌面构图参考，再逐状态生成。精确提示词见 [selection-and-prompts.json](selection-and-prompts.json)。其余十一张同时引用角色参考图与首张空闲图。

12 张图均已在生成结果中实际查看：服装、控制台及配色总体一致；工作道具、完成勾号、问号和故障警告具有各自含义。仅为首轮设计目视检查，不是蒙版或动画验收。图像尺寸与透明通道由 provenance.json 记录。

当前仍是待用户确认的静态候选。各图固定区域存在生成差异，不能直接作为同一套逐帧动画；部分外轮廓贴近画布边界，制作正式源图时还需统一构图与透明留白。下一步需复用同一固定底图、整理源图和手部／道具蒙版、补底与遮挡层，并制作独立眼皮。尚未制作分层、动画、正式 384×416 源图或安装包，也未替换现有 App。
