# 自动活动记录：Stage 1.2b

2026-10-20（America/Los_Angeles）。本地开发增量，未发布、未替换桌面 App。

## Implemented

两端新增独立运行的 `--activity-collect`。自动查找指定 Codex 会话目录中最近 24 小时修改过的 `.jsonl`，从可读取开头导入，并持续发现新会话、跟进新增记录。复用 Stage 1.2a 的事务、来源身份、读取位置和结果关联，保持原数据库格式。它不是开机服务，也没有接入桌宠动画循环。

- 每次检查最多扫描 50,000 个目录项，下降最多 5 层，最多跟进 512 个文件。遇到深度、数量或读取限制明确报告 `scan_complete=false`，不宣称全覆盖。不跟随子目录／文件符号链接；明确选定的根目录在启动时解析一次。
- 每轮最多处理 8 个文件，每个文件最多 500 个完整行；轮流安排，空闲文件不重复导入。每轮完成后间隔约 2 秒。文件量和行数有上限，不是严格的处理耗时上限；大文件的完整前缀校验仍可能较慢。
- 新文件和重新活跃的旧文件进入队列；进程内尚未完成的工作不会仅因超过 24 小时被丢下。重新启动时仍按最近 24 小时发现，超过该范围且没有新修改的积压文件需再次活动，或使用已有单文件导入命令。不是全历史补齐器。
- 单个来源读取失败时保留书签，按 2、4、8 秒递增至最多 60 秒重试；发现文件变化时可提前重试。其他来源继续处理。目录暂时不存在时等待；文件消失不会删除已保存历史，也不据此断言 AI 任务结束。
- 默认数据库文件增长上限 256 MiB，可设为 1–4096 MiB。空间不足或数据库达到上限时暂停保存，保留所有已提交历史；处理空间或调整限额后重新启动。没有自动删除、轮换或压缩。事务临时文件、状态、程序文件不在数据库限额内；外部手动导入器也不受这个连接的限额约束。
- 数据库及状态输出分别使用独占进程锁，避免重复启动的记录器抢同一目标；锁随进程退出释放，保留空的锁文件，不通过删锁文件抢占。Python 提供 Windows 锁分支，但尚未 Windows 原生验收。
- 状态文件仅含汇总数量、时间、状态和固定错误类别，原子替换写入；Mac 上新建文件权限为 0600。拒绝将状态写到会话目录、数据库、数据库伴随文件和无关既有文件。控制台不打印原始聊天或来源错误正文。
- Ctrl-C、SIGTERM 和有限时运行正常结束时写入 `stopped`。强杀／断电不能承诺写出最终状态，网站在 15 秒没有新心跳后明确显示无法确认。不可用的数据库为整体错误，不冒充单一坏来源。

## 重要选择

**Technical Reasoning。** 保留两个平台现有语言和共同历史格式，以独立串行 worker 复用存储层，避免给动画线程增加文件扫描和 SQLite 工作。使用 SQLite `max_page_count` 限制本连接的数据库增长；该限制不能缩小已有数据库，因此超出预算的现有库暂停而不删减。依据：[SQLite PRAGMA](https://www.sqlite.org/pragma.html#pragma_max_page_count)。

**Beginner-Friendly Explanation。** 上一轮做好了记录簿和书签，这一轮增加一个自动找文件、轮流记账的人。一本文件很长时，先记一部分，再轮到别的文件；写不下时先停下来，不撕掉以前的页。

检查中移除了 Swift 为比较文件身份而额外打开／关闭数据库文件的做法，改为先查文件属性。关闭额外数据库文件句柄可能释放同一进程的 POSIX 锁；这不应绕过 SQLite 的协调。依据：[SQLite 文件锁说明](https://www.sqlite.org/howtocorrupt.html#_posix_advisory_locks_canceled_by_a_separate_thread_doing_close_)。

本机旧测试在给已打开的数据库创建硬链接后出现 `SQLITE_IOERR_VNODE (6922)`。最小独立探针也确认：原生 SQLite 3.54.0 在链接变动后可能使旧连接读取失败；主库将该代码保留给扩展使用。修订测试为精确要求 Yukio 的“数据库不能作为来源”身份错误，然后关闭、仅移除测试创建的别名、重新打开验证历史完整，不关闭原生保护，也不把任意 I/O 错误算成身份检查通过。依据：[错误代码](https://www.sqlite.org/rescode.html#ioerr_vnode)。已打开的数据库被外部改名、删改或硬链接改变时，不能承诺原连接继续工作。

## Verified

- Swift 完整测试 **214 项通过**，包含新增 7 项多场景采集测试。
- Python 完整测试 **336 项运行，335 项通过、1 项跳过**；新增 11 项采集测试。跳过项需要 Windows 命名管道，本轮均在 Mac 上执行。
- 两个实际程序的合成会话检查：动态发现新文件、等待半行、同名调用会话隔离、SIGTERM 正常停止、重启零重复、相互接续数据库、数据库与状态输出互斥、保护无关状态文件。最终 8 条证据逐字段一致（写入顺序另行比较，不假装跨会话全局时间顺序）。
- 原历史回归：33 个共同场景、141 条证据（含 57 条结果）完全一致，6 个元数据边界、跨实现接续、单文件持续跟随和保存失败重试仍通过。
- 本机启动真实 Swift 记录器；初次检查发现 2 份近期会话文件，已保存 1,851 条记录，读取失败 0、待处理 0，SQLite `quick_check=ok`。这是 2026-10-20 23:01 左右的快照，运行数字会继续变化。没有把真实聊天原文复制进验证报告。
- 浏览器已显示真实运行状态与 4/9 阶段完成；9 个阶段仍有可展开说明。状态汇总没有来源路径或聊天编号；已检查新建历史和状态权限均为 0600。

检查入口：

```sh
swift test --package-path YukioPlayer
(cd YukioWin && python3 -m unittest discover -s tests)
python3 tests/verify_activity_collector.py
python3 tests/verify_activity_history.py
```

## 运行与恢复

在仓库根目录使用开发构建，数据库和状态路径应位于本机可靠文件系统：

```sh
swift build --package-path YukioPlayer
YukioPlayer/.build/debug/YukioPlayer --activity-collect /absolute/path/history.sqlite --status-file /absolute/path/collector-status.json
```

Python 入口（在 `YukioWin` 目录）：

```sh
python3 -m yukio --activity-collect /absolute/path/history.sqlite --status-file /absolute/path/collector-status.json
```

两端均支持 `--sessions-dir DIR`、`--seconds N`、`--max-database-mb N`。默认读取 `CODEX_HOME/sessions` 或 `~/.codex/sessions`。`--seconds 0` 持续运行，正数为有限运行。已有单文件导入、跟随和只读查询命令保持可用。

本次实际运行资料在 `~/Library/Application Support/YukioPlayer/activity-observation/`：

- `collector-process.json`：进程号、实际启动命令和二进制 SHA-256。使用按哈希命名的开发程序副本，后续构建不会悄悄替换正在运行的版本。
- `codex-activity-history-v1.sqlite`：本地元数据历史；`collector-status.json`：汇总状态；`collector.log`：启动错误／停止汇总，无逐轮日志增长。
- `progress-server.json`：本机进度网站进程，独立于记录器。访问 `http://127.0.0.1:8766/`。

停止时先核对进程信息，再向对应记录器发 SIGTERM；不要删数据库、事务文件或锁文件。正常停止后可以原命令重新启动。电脑重启后目前需手动重新启动记录器和网站。没有安装开机项，也没有使用云服务。

## Unverified

Windows 原生锁、目录访问权限和实际安装运行；长期大日志负载、真正断电／硬盘故障、所有客户端覆盖；桌面已安装 App 使用新功能。实际采样只说明这些本机文件可以被读取和保存，不能证明所有 AI 工作都正确或日志没有遗漏。

## Issues

最近一天和数量上限是明确的观察范围；不支持自动补齐全部历史。完整前缀校验可能使单个大批次较慢，网站此时会提示心跳未更新。人工维护的开发进度与自动采集状态是两回事。数据库元数据未加密，不应把 0600 文件权限理解为加密保险箱。

## Next Steps

扩展 Claude／Deep Code 的实际可读记录和任务／助手关系，再建立基于持久记录的活动工作台。当前网站是开发进度网站。千问解释需要单独核实接口、配置和数据发送授权；本轮未调用付费 API、未推送、未发布。
