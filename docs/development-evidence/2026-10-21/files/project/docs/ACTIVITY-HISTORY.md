# 本地活动历史：Stage 1.2a

2026-10-20。本地开发增量，未发布，未替换桌面 App。

后续进展：[Stage 1.2b 自动记录器](ACTIVITY-COLLECTOR.md)已经加入近期多会话发现、轮流采集、容量管理及实时汇总。下文保留 Stage 1.2a 的当时范围。

本轮交付可独立运行的 **Codex 单文件记录器**：明确指定一个会话 JSONL 文件，可以一次导入、持续跟随，或关闭后重新运行同一命令继续记录。历史查询不依赖原文件仍然存在。两端均接入真实可执行程序，未接到桌宠动画循环，也尚未默认开启全会话后台采集。

## 用户能得到什么

- 保留已观察到的工具请求、回执、会话和轮次记录，重启后仍可读取。
- 延续上一阶段的成功／失败／取消／未知、未关联和冲突标记；重启不会丢掉尚在等待结果的调用编号。
- 重读同一文件不会重复记账；写了一半的行等写完后再记。
- 原文件被截短、替换或已读部分被改写时，保留旧历史，另开记录段并留下变化说明。
- 保存失败明确报错；该批事件、关联状态和读取位置一起撤回，修复后可以重试。

这不是完整活动工作台，也不代表已覆盖所有客户端、所有内层操作或完整任务历史。记录从所选文件当前可读取的开头开始；无法补回客户端此前已经删除的内容。

## 实现选择

**Technical Reasoning。** SQLite 事务中同时写入 events 和 sources 的完整行游标、前缀哈希、结果关联 checkpoint。使用 `BEGIN IMMEDIATE` 串行化写入者、`synchronous=FULL` 和 SQLite 默认回滚日志，不关闭同步或日志机制。SQL 参数绑定；拒绝未知数据库、未来 schema 版本，不自动重建或覆盖。`application_id=1498762063`，`user_version=1`。Swift 使用 macOS 系统 SQLite3，Python 使用标准库 sqlite3，没有新增云服务或包依赖。

SQLite 的原子提交语义及对文件系统和硬件的依赖见 [Atomic Commit](https://www.sqlite.org/atomiccommit.html)，写入锁、提交失败和回滚处理见 [Transactions](https://www.sqlite.org/lang_transaction.html)。本轮测试不能证明所有硬盘、网络文件系统或断电情况下的数据安全。活动数据库应放在本机可靠文件系统；资料和大型产物的 NAS 存储约定不等于已经验证远程文件系统上的数据库锁。

**Beginner-Friendly Explanation。** 相当于一本工作记录簿和一枚书签：写下事情时，书签一起移动。如果写入失败，两者一起退回原处。下次打开时从书签继续，就不会把没记下来的事情误当成已经保存。

### 数据边界

- 保存必要的身份、工具名、时间是否存在、机器结果标志、原始行位置与 SHA-256；不保存聊天正文、提示词、工具参数、脚本、命令或输出正文。
- 在调用结果解析器之前使用字段白名单；checkpoint 只包含会话、轮次和有界调用关联状态。它用于历史结果恢复，不是完整桌宠 UI 状态快照。
- 会话与调用编号仍属于本地项目元数据；数据库不是加密保险箱。新建 Mac/POSIX 数据库文件权限为 0600，目录为 0700；Windows ACL 沿用账户目录权限，尚未原生核验。没有网络发送、密钥配置或 API 调用。
- 每个非空完整源行形成一条证据，保留 `source_record_sha256`（不含 LF）、`source_line`、`source_offset`、`next_offset`。
- `source_id` 是规范化真实路径的 SHA-256；路径字符串不落库。`event_id = source_id:generation:offset`。同一路径的重复读取去重；不同路径的副本、同一文件内实际出现的重复行仍是不同源证据，不声称已经做跨文件语义去重。
- `sequence` 是写入顺序，不是不同客户端事件的真实全局发生顺序。缺少时间保持 `timestamp_available=false`；结果中的旧接口 `timestamp_ms=0` 不能当作实际时间。
- `tool_requested` 只证明观察到请求；`tool_result` 是客户端回执。`turn_ended` 只表示观察到客户端轮次结束标志，不等于任务正确、测试通过或用户验收。
- `context_turn_id` 是当前解析上下文；源行明确携带的 `turn_id` 单独保留。外来 `thread_id` 标为 `foreign_session_record`，按其报告的会话归组，不修改当前会话关联状态。
- 格式损坏的完整行记为 `invalid_record`，保留哈希和位置，清除跨缺口关联上下文；不保存坏行正文。未知类型记为 `unrecognized_record`。多 Agent 因果关系仍未推断。

### 读取与故障合同

1. 一次最多提交 500 个完整行。每行最多 8 MiB；超限明确失败，保留之前批次，不跳过后面的未知内容。
2. 未带换行符的末尾，即便已经是合法 JSON，也等待下次写完；书签不跨过它。
3. 每次实际导入先验证已读前缀；文件身份变化、长度回退或哈希变化触发新 generation。结束时再次校验本批消费的前缀与文件身份，避免读到一半发生改写却提交。
4. 持续跟随每 2 秒检查文件身份、长度、mtime 与 ctime；无变化时不重读、不写库。变化后仍执行完整前缀验证。原文件消失、权限失败、锁冲突或存储错误会明确停止，原历史仍可查询。
5. 写入失败不推进游标；恢复后重新运行即可。仅支持常规文件，拒绝管道及把数据库自身作为来源；查询入口只读，不创建缺失数据库。
6. 源文件长期持续原地变动、绕过系统时间戳的改写、极大档案的吞吐与长期磁盘增长仍需专项验证。当前每个有效批次重新哈希已读前缀，优先保证可核查性；尚无索引快照优化、自动轮转或保留期限，不自动删除历史。

## 可复现运行

以下从仓库根目录执行，`DB` 与 `SOURCE` 请使用绝对路径。`SOURCE` 为用户明确选定的 Codex JSONL。命令只读来源；数据库是新的 Yukio 文件，不能选现有重要文件充当数据库。

macOS 开发构建：

```sh
swift build --package-path YukioPlayer
YukioPlayer/.build/debug/YukioPlayer --activity-import "$DB" "$SOURCE"
YukioPlayer/.build/debug/YukioPlayer --activity-follow "$DB" "$SOURCE"
YukioPlayer/.build/debug/YukioPlayer --activity-history "$DB" --limit 100
```

Windows/Python 源码入口（在 YukioWin 目录）：

```sh
python -m yukio --activity-import "$DB" "$SOURCE"
python -m yukio --activity-follow "$DB" "$SOURCE"
python -m yukio --activity-history "$DB" --limit 100
```

- `--activity-follow` 默认持续运行；可用 `--seconds 30` 有限运行，或 Ctrl-C 停止。关闭后重新运行同一路径即可接续。Swift 被信号终止时由 SQLite 在下次打开恢复未提交事务。
- 查询支持 `--after 序号`、`--limit 1到10000`、`--session 会话编号`；输出 JSONL，供下一阶段页面使用。默认只取 500 条，不是全部历史。
- 每次导入输出该批 `records_read/events_saved/offset/generation/batch_full`。导入命令自动处理后续批次；某一批失败时此前成功提交的批次保留，不能把整个文件说成已经导入完成。
- 当前桌面安装版不含这些新增命令；请使用本轮开发构建。没有默认采集所有聊天或自动上传行为。

验证入口：

```sh
swift test --package-path YukioPlayer
(cd YukioWin && python3 -m unittest discover -s tests)
python3 tests/verify_activity_history.py
python3 tests/verify_codex_result_parity.py
```

## 阶段记录

**Implemented：**两端本地 SQLite 元数据历史库、事务游标和关联 checkpoint；单文件导入、持续跟随、只读分页／会话查询；格式缺口、重复读取、迟到结果、文件世代及失败回滚处理。

**Verified：**Swift 全套 207 项通过；Python 全套 325 项，324 项通过、1 项 Windows 命名管道测试跳过。33 个共享场景的 141 条历史证据（含 57 条结果）在两个实际 CLI 中完全一致，另验证 6 个元数据边界场景；可互读数据库并从对方保存的状态接续。详见 [verification.json](validation/activity-observation-stage1-2/verification.json)。使用明确标识的构造记录，运行实际 CLI 与真实磁盘数据库。覆盖重启关联、半行、改写／替换／截断、会话隔离、隐私白名单、写入失败重试、数据库锁、SQLite FULL 和 Python 子进程突然退出恢复。没有将模拟内容称为真实 Agent 完成工作。

**Unverified：**Windows 原生运行与 ACL、安装包、真实断电／磁盘损坏、长期高负载、全客户端覆盖、当前桌面 App 使用新代码。未接入工作台和千问，未发布或替换 App。

**Issues：**单文件记录器需要明确指定文件，尚未接入自动发现多个会话；只存元数据，不保留可直接阅读的完整输出。文件被删除后能查看已保存元数据，但无法重新读取被删掉的正文。已有工作树与正式发布源码仍需在发布前对齐。当前开发增量没有改变桌宠采集／动画／问题卡路径。

**Next Steps：**Stage 1.2b 将记录器接到独立后台采集服务，加入多会话发现、采集状态和容量管理；之后扩展其他客户端并接入活动工作台。云端解释继续等待明确数据授权与接口配置。
