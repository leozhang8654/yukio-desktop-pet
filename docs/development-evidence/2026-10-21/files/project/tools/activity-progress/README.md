# Yukio 开发进度网站

[GitHub 公开版](https://leozhang8654.github.io/yukio-desktop-pet/) · [网站发布分支](https://github.com/leozhang8654/yukio-desktop-pet/tree/codex/activity-progress-pages)

公开版显示最近一次发布的开发成果和详细计划，每分钟检查新版。本机版仍每 3 秒读取实际记录器状态。公开版不连接本机服务，不上传活动数据库、运行汇总、聊天正文或密钥。两者不能视为同一条实时数据流。

只展示经过核查的开发进度、完整路线和可展开的日常语言说明。每 3 秒重新读取状态；已展开的内容在自动刷新和分类切换后保留。每个阶段分别说明具体工作、选择原因、验证方式和当前限制，计划中的能力不冒充已实现能力。

这不是最终 AI 活动工作台。`progress.json` 是开发过程中人工维护的成果记录，不是自动推断的代码完成比例。记录器数字从单独的汇总状态文件读取，尚未接入时显示“尚未连接”，不显示演示数据。停止开发后页面仍可浏览，但不会自行产生新进展。

## 启动

在仓库根目录运行：

```sh
python3 tools/activity-progress/server.py --port 8766
```

浏览 `http://127.0.0.1:8766/`。如已有记录器状态文件，可额外指定 `--runtime /absolute/path/collector-status.json`。服务只监听本机，不发布到公网。退出启动进程即可停止；没有设置开机自启。

本次持续运行服务的进程与访问地址记录在 `~/Library/Application Support/YukioPlayer/activity-observation/progress-server.json`，服务日志也在同一目录。这里记录的是进程信息，不代表已经启动活动记录器。

## 维护

- `progress.json`：真实阶段状态、详细说明和进展记录。新增事实应先完成对应核查。
- `update.py`：本地原子写入当前说明与进展记录；网站本身不提供写入入口。
- `dist/`：无需安装依赖的页面；内容自动刷新，修改样式或脚本后需重新载入页面。
- `server.py`：只提供固定页面文件与 `/api/status`，不浏览仓库、不读取聊天正文、不向外传输数据。

示例：

```sh
python3 tools/activity-progress/update.py --note '填写本次实际完成的进展' --work-state '本轮工作已完成'
```

`--checks` 和 `--complete-auto` 只用于自动记录阶段，必须在对应检查实际通过后使用。

## 本轮验证与限制

已在实际浏览器检查详情展开／收起、键盘操作、分类切换保留展开内容、当前阶段直达入口，以及真实状态文件变更后的自动刷新。9 个阶段各有 4 组说明。当前浏览器宽度下无横向溢出。

临时隔离服务通过 10 项 HTTP 检查，覆盖页面可读、禁止缓存、只暴露运行汇总、拒绝仓库文件访问、拒绝外来 Host/Origin、没有网页写入入口及状态损坏时明确报错。没有调用付费 API，没有发布或替换桌面 App。未进行所有设备尺寸的兼容检查。

后续已完成：自动记录器现已接入本机运行汇总，见 [Stage 1.2b](../../docs/ACTIVITY-COLLECTOR.md)。已停止状态不会因时间过去变成“失联”；运行中的心跳超过 15 秒未更新会明确提示。开发阶段进度仍由实际工作人工维护，不由记录数量推算。

## 导出和发布公开版

维护 `progress.json` 时同时维护 `public_current_note` 和 `public_work_state`，使用适合公开的进度说明，不声称当前电脑仍在运行。阶段说明共享，涉及实际运行数字时明确写“本机网站”。

```sh
python3 tools/activity-progress/export_public.py --out /tmp/yukio-public-preview-new
```

输出目录必须为空或不存在。导出器只生成六个文件（页面、脚本、样式、公开进度、README 和 `.nojekyll`），按已知字段重建进度数据；不会打开记录器状态或数据库。文字内容仍需逐项检查，不能把简单关键词检查当成完整隐私审查。

GitHub Pages 从 `codex/activity-progress-pages` 分支根目录发布。首次发布为独立历史，只有这六个文件，未混入桌面 App 代码或其他未提交改动。以后发布应基于该分支最新提交，仅更新审核过的网页文件，正常向前提交；不要强推或用主工作区的全部文件覆盖。Pages 完成后核对正式网址的资源与本次文件内容一致。

这是网站专项交付，没有发布桌面 App 或验证 Windows 新安装包。页面不是千问配置入口，千问仍未接入。
