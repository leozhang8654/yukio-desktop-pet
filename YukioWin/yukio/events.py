"""雪绪播放器的事件协议：与来源无关的小型事件。

适配层（Deep Code 会话记录、Claude Code 转录、通用收件箱、模拟脚本）只负责把原始数据
翻译成这些事件；路由、防抖和保持时间全部在 router.ActivityRouter 中完成。

这是 YukioPlayer/Sources/YukioCore/Events.swift 的 Python 移植，字段含义保持一致。
"""

from __future__ import annotations

import datetime as _dt
import re
from enum import Enum
from typing import List, Optional


class PetState(str, Enum):
    """雪绪可显示的状态。七个活动 + 默认电脑桌 + 失败 + 空闲。

    拖动跑动不是状态：由窗口层临时覆盖，松手后回到当前状态。
    """

    idle = "idle"
    thinking = "thinking"
    read_file = "read_file"
    view_image = "view_image"
    write_file = "write_file"
    verify = "verify"
    read_web = "read_web"
    respond = "respond"
    default_work = "default_work"
    #: 工具报错或本轮因错误中止：沮丧（基础图条 failed）。
    failed = "failed"
    #: AskUserQuestion：把问号卡立在桌上、指着它等你回答。
    question_for_user = "question_for_user"
    #: 一轮任务结束：递交报告之后举起勾选卡，直到回空闲。
    task_complete = "task_complete"

    @property
    def is_work(self) -> bool:
        return self not in (PetState.idle, PetState.question_for_user, PetState.task_complete)


ALL_STATES: List[PetState] = list(PetState)


class TodoStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    #: 更新事件删除条目。
    deleted = "deleted"


class TodoItem:
    """任务清单中的一条（Claude 的 TodoWrite/TaskCreate/TaskUpdate，Deep Code 的 UpdatePlan）。"""

    __slots__ = ("id", "subject", "status")

    def __init__(self, id: str, subject: Optional[str] = None, status: Optional[TodoStatus] = None):
        self.id = id
        #: 条目文字；更新事件里为 None 表示不改。
        self.subject = subject
        #: 更新事件里为 None 表示不改；新条目缺省为 pending。
        self.status = status

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TodoItem):
            return NotImplemented
        return (self.id, self.subject, self.status) == (other.id, other.subject, other.status)

    def __repr__(self) -> str:
        return "TodoItem(%r, %r, %r)" % (self.id, self.subject, self.status)


class Kind(str, Enum):
    #: 用户发出新请求，任务开始。detail 为请求的第一行。
    task_start = "task_start"
    #: 任务正常结束（已给出回答）。
    task_end = "task_end"
    #: 任务被中断／取消／会话关闭。
    task_abort = "task_abort"
    #: 本轮因错误中止（例如 API 报错）：沮丧一会儿再回空闲。
    task_failed = "task_failed"
    #: 工具开始执行。activity 为 None 表示“延续上一个工具的活动”。
    activity_start = "activity_start"
    #: 工具执行结束：成功，或被用户拒绝／中断（这些不算失败）。
    activity_end = "activity_end"
    #: 工具执行失败（报错、非零退出）。同样结束该工具调用。
    activity_failed = "activity_failed"
    #: 模型产生了思考内容或过程说明：只说明任务仍在进行。
    thinking = "thinking"
    #: 最终回答已输出。
    final_answer = "final_answer"
    #: 来源断开（文件消失、适配器出错）；该来源的所有会话回到空闲。
    source_lost = "source_lost"
    #: 会话标题（大任务），标题文字在 detail。
    session_title = "session_title"
    #: 任务清单整体替换，完整清单在 todos。
    todo_list = "todo_list"
    #: 任务清单个别条目新增或更新，要合并的条目在 todos。
    todo_update = "todo_update"


class PetEvent:
    __slots__ = ("ts", "source", "session", "kind", "event_id", "activity", "tool", "detail", "todos")

    def __init__(self, ts: float, source: str, session: str, kind: Kind,
                 event_id: Optional[str] = None, activity: Optional[PetState] = None,
                 tool: Optional[str] = None, detail: Optional[str] = None,
                 todos: Optional[List[TodoItem]] = None):
        #: 事件发生时间，毫秒（Unix 纪元）。
        self.ts = ts
        #: 来源标识，例如 "deepcode"、"claude-transcript"、"bridge"、"sim"。
        self.source = source
        #: 会话 ID。多个会话同时运行时用于隔离状态。
        self.session = session
        self.kind = kind
        #: 工具调用 ID，用于配对开始／结束与去重。
        self.event_id = event_id
        self.activity = activity
        #: 原始工具名，仅用于显示和调试。
        self.tool = tool
        #: 给人看的简短说明。
        self.detail = detail
        self.todos = todos

    def __repr__(self) -> str:
        bits = ["%s" % self.kind.value]
        if self.tool:
            bits.append(self.tool)
        if self.activity:
            bits.append("→ %s" % self.activity.value)
        elif self.kind is Kind.activity_start:
            bits.append("→ (延续上一个)")
        return "PetEvent(%s)" % " ".join(bits)


_ISO = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:?\d{2})?$"
)


def parse_timestamp(text: Optional[str]) -> Optional[float]:
    """解析 ISO-8601 时间戳（带或不带小数秒、带或不带时区），返回毫秒。

    没有时区时按本地时间处理：Deep Code 与 Claude 都写 UTC 的 `Z`，本地时间只在手写事件里出现。
    """
    if not text:
        return None
    m = _ISO.match(text.strip())
    if not m:
        return None
    year, month, day, hour, minute, second = (int(m.group(i)) for i in range(1, 7))
    frac = m.group(7) or "0"
    micro = int((frac + "000000")[:6])
    zone = m.group(8)
    try:
        naive = _dt.datetime(year, month, day, hour, minute, second, micro)
    except ValueError:
        return None
    if zone in (None, ""):
        return naive.timestamp() * 1000.0
    if zone == "Z":
        offset = _dt.timezone.utc
    else:
        sign = 1 if zone[0] == "+" else -1
        body = zone[1:].replace(":", "")
        offset = _dt.timezone(sign * _dt.timedelta(hours=int(body[:2]), minutes=int(body[2:4])))
    return naive.replace(tzinfo=offset).timestamp() * 1000.0
