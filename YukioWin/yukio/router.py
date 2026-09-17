"""把事件流变成“当前该显示什么”，并施加防抖与最短保持。

时间全部由调用方传入（毫秒），因此可以用虚拟时钟完整测试。
实时模式传入墙钟；回放历史记录时传入事件自身的时间戳。

移植自 YukioPlayer/Sources/YukioCore/ActivityRouter.swift，数值与行为保持一致。
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional

from .events import Kind, PetEvent, PetState, TodoItem, TodoStatus

INF = float("inf")


class RouterConfig:
    """路由与调度参数。数值是待调起点，不是用户指定的精确值。"""

    def __init__(self):
        #: 候选状态需稳定这么久才生效（建议 300–600 ms）。
        self.debounce_ms = 400.0
        #: 每个显示状态至少保持这么久（建议 1–2 s）。
        self.min_hold_ms = 1500.0
        #: 工具结束后仍按该工具的活动计算这么久：合并同类连续短调用。
        self.tool_grace_ms = 3500.0
        #: 任务结束后“递交报告 + 勾选卡”这一段的总停留时间。
        self.respond_linger_ms = 8000.0
        #: 其中前这么久显示“递交报告”，之后换成勾选卡。须小于 respond_linger_ms。
        self.respond_hold_ms = 3000.0
        #: 工具失败后沮丧最多显示这么久；期间开始新工具会立即接替，之后回到思考。
        self.failed_hold_ms = 4000.0
        #: 本轮因错误中止后沮丧停留这么久，然后回空闲。
        self.failed_linger_ms = 8000.0
        #: 任务进行中、没有未结束工具、且这么久没有任何事件：视为失联，回空闲。
        self.stale_no_tool_ms = 10 * 60 * 1000.0
        #: 有未结束工具（例如长时间构建）时的失联上限。
        self.stale_open_tool_ms = 30 * 60 * 1000.0
        #: 两个适配器同时报告同一任务开始时，这个窗口内的重复开始被忽略。
        self.duplicate_task_start_ms = 3000.0


class Progress(NamedTuple):
    done: int
    total: int


class StatusLine(NamedTuple):
    """头顶气泡的内容：大任务标题 + 当前任务（没有清单时是正在进行的活动）+ 进度。"""

    title: Optional[str]
    current: str
    progress: Optional[Progress]


class _OpenCall:
    __slots__ = ("id", "state", "at", "detail")

    def __init__(self, id: str, state: PetState, at: float, detail: Optional[str]):
        self.id = id
        self.state = state
        self.at = at
        self.detail = detail


class _Session:
    """单个会话的活动模型。"""

    def __init__(self, source: str, now: float):
        self.source = source
        self.task_active = False
        self.task_started_at = -INF
        self.task_started_ts = -INF
        self.task_ended_at: Optional[float] = None
        self.task_ended_ts = -INF
        self.last_event_at = now
        self.open: List[_OpenCall] = []
        self.last_tool_state: Optional[PetState] = None
        self.last_tool_ended_at: Optional[float] = None
        self.final_answer_at: Optional[float] = None
        #: 最近一次失败（工具报错或本轮因错误中止）的时间。
        self.failed_at: Optional[float] = None
        #: 失败的那次工具调用的说明；API 报错时为 None。
        self.failed_detail: Optional[str] = None
        #: 各动作最近一次工具调用的说明，让气泡文字和显示的动作对得上。
        self.last_detail: Dict[PetState, str] = {}
        self.title: Optional[str] = None
        self.prompt: Optional[str] = None
        #: 任务清单。跨轮保留：用户说“继续”时进度接着算。
        self.todos: List[TodoItem] = []
        self._ended_ids: List[str] = []
        self._ended_set = set()

    def begin_task(self, now: float, ts: float) -> None:
        self.task_active = True
        self.task_started_at = now
        self.task_started_ts = ts
        self.task_ended_at = None
        self.open = []
        self.last_tool_state = None
        self.last_tool_ended_at = None
        self.final_answer_at = None
        self.failed_at = None
        self.failed_detail = None
        self.last_detail = {}

    def end_task(self, now: float, ts: float, keep_answer: bool) -> None:
        self.task_active = False
        self.task_ended_at = now
        self.task_ended_ts = max(self.task_ended_ts, ts)
        self.open = []
        self.last_tool_ended_at = None
        self.failed_at = None
        if not keep_answer:
            self.final_answer_at = None

    def upsert_todo(self, item: TodoItem) -> None:
        for i, existing in enumerate(self.todos):
            if existing.id == item.id:
                if item.status is TodoStatus.deleted:
                    self.todos.pop(i)
                    return
                if item.subject is not None:
                    existing.subject = item.subject
                if item.status is not None:
                    existing.status = item.status
                return
        if item.status is TodoStatus.deleted:
            return
        # 上一批全部完成后又新建任务：视为新的一批，进度从头算。
        if item.status is None and self.todos and all(t.status is TodoStatus.completed for t in self.todos):
            self.todos = []
        self.todos.append(TodoItem(item.id, item.subject, item.status or TodoStatus.pending))

    def mark_ended(self, id: str) -> None:
        if id in self._ended_set:
            return
        self._ended_ids.append(id)
        self._ended_set.add(id)
        if len(self._ended_ids) > 512:
            self._ended_set.discard(self._ended_ids.pop(0))

    def was_ended(self, id: str) -> bool:
        return id in self._ended_set


class Snapshot(NamedTuple):
    focused_session: Optional[str]
    task_active: bool
    open_tools: int
    session_count: int


_FALLBACK_TEXT = {
    PetState.read_file: "阅读文件",
    PetState.view_image: "查看图片",
    PetState.write_file: "修改文件",
    PetState.verify: "运行测试",
    PetState.read_web: "浏览网页",
    PetState.default_work: "处理中",
    PetState.thinking: "思考中",
    PetState.respond: "整理回答",
    PetState.failed: "出错了",
    PetState.question_for_user: "等你回答",
    PetState.task_complete: "已完成",
    PetState.idle: "等你回答",
}


class ActivityRouter:
    def __init__(self, now: float = 0.0, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()
        self.displayed = PetState.idle
        # 启动时的空闲不占用最短保持时间，第一次切换只受防抖约束。
        self.displayed_since = -INF
        self.pending: Optional[PetState] = None
        self.pending_since = 0.0
        #: 当前跟随的会话。多个会话同时工作时只跟随一个，避免交叉串状态。
        self.focused_session: Optional[str] = None
        self._sessions: Dict[str, _Session] = {}
        self._anonymous = 0

    # MARK: 事件输入

    def ingest(self, e: PetEvent, now: float) -> None:
        cfg = self.config
        if e.kind is Kind.source_lost:
            for s in self._sessions.values():
                if s.source == e.source and s.task_active:
                    s.end_task(now, e.ts, keep_answer=False)
            return

        s = self._sessions.get(e.session)
        if s is None:
            s = _Session(e.source, now)
            self._sessions[e.session] = s
        s.last_event_at = max(s.last_event_at, now)

        kind = e.kind
        if kind is Kind.task_start:
            if e.detail:
                s.prompt = e.detail
            if s.task_active and now - s.task_started_at < cfg.duplicate_task_start_ms:
                return
            s.begin_task(now, e.ts)

        elif kind is Kind.task_end:
            if not s.task_active or e.ts < s.task_started_ts:
                return
            s.end_task(now, e.ts, keep_answer=True)

        elif kind is Kind.task_abort:
            if not s.task_active and s.final_answer_at is None:
                return
            s.end_task(now, e.ts, keep_answer=False)
            s.task_ended_at = None

        elif kind is Kind.task_failed:
            if not s.task_active or e.ts < s.task_started_ts:
                return
            s.end_task(now, e.ts, keep_answer=False)
            s.failed_at = now
            s.failed_detail = None

        elif kind is Kind.activity_start:
            # 早于当前任务或已结束任务的迟到事件不能复活旧活动。
            if e.ts < s.task_started_ts or e.ts < s.task_ended_ts:
                return
            if e.event_id and (s.was_ended(e.event_id) or any(c.id == e.event_id for c in s.open)):
                return
            self._ensure_active(s, now, e.ts)
            state = e.activity or s.last_tool_state or PetState.default_work
            call_id = e.event_id or self._next_anonymous_id()
            s.open.append(_OpenCall(call_id, state, now, e.detail))
            if e.detail:
                s.last_detail[state] = e.detail
            s.final_answer_at = None
            s.failed_at = None

        elif kind in (Kind.activity_end, Kind.activity_failed):
            failed = kind is Kind.activity_failed
            call = None
            if e.event_id:
                for i, c in enumerate(s.open):
                    if c.id == e.event_id:
                        call = s.open.pop(i)
                        break
                s.mark_ended(e.event_id)
            elif s.open:
                call = s.open.pop()
            # 重复的结束（两个适配器都报告）找不到未结束调用，不会再次触发沮丧。
            if call is None or not s.task_active:
                pass
            else:
                s.last_tool_state = call.state
                # 失败的工具没有合并窗口：沮丧之后直接回思考，不再显示原来的动作。
                s.last_tool_ended_at = None if failed else now
                if failed:
                    s.failed_at = now
                    s.failed_detail = call.detail

        elif kind is Kind.thinking:
            if e.ts < s.task_ended_ts:
                return
            self._ensure_active(s, now, e.ts)

        elif kind is Kind.final_answer:
            if e.ts < s.task_ended_ts:
                return
            self._ensure_active(s, now, e.ts)
            s.final_answer_at = now

        elif kind is Kind.session_title:
            title = (e.detail or "").strip()
            if title:
                s.title = title

        elif kind is Kind.todo_list:
            items = []
            for t in (e.todos or []):
                if t.status is TodoStatus.deleted:
                    continue
                items.append(TodoItem(t.id, t.subject, t.status or TodoStatus.pending))
            s.todos = items

        elif kind is Kind.todo_update:
            for t in (e.todos or []):
                s.upsert_todo(t)

    def _ensure_active(self, s: _Session, now: float, ts: float) -> None:
        """在任务中途才开始跟随（或开始事件丢失）时，由其他事件隐式开启任务。"""
        if not s.task_active:
            s.begin_task(now, ts)

    def _next_anonymous_id(self) -> str:
        self._anonymous += 1
        return "anon-%d" % self._anonymous

    # MARK: 状态计算

    def _is_live(self, s: _Session, now: float) -> bool:
        if not s.task_active:
            return False
        quiet = now - s.last_event_at
        limit = self.config.stale_no_tool_ms if not s.open else self.config.stale_open_tool_ms
        return quiet <= limit

    def _desired(self, s: _Session, now: float) -> PetState:
        cfg = self.config
        if s.task_active:
            if not self._is_live(s, now):
                return PetState.idle
            if s.open:
                return s.open[-1].state
            if s.final_answer_at is not None:
                return PetState.respond
            if s.failed_at is not None and now - s.failed_at < cfg.failed_hold_ms:
                return PetState.failed
            if (s.last_tool_state is not None and s.last_tool_ended_at is not None
                    and now - s.last_tool_ended_at < cfg.tool_grace_ms):
                return s.last_tool_state
            return PetState.thinking
        if s.final_answer_at is not None and s.task_ended_at is not None \
                and now - s.task_ended_at < cfg.respond_linger_ms:
            # 先递交报告（整理文件那一下），再举勾选卡停住。
            hold = min(cfg.respond_hold_ms, cfg.respond_linger_ms)
            return PetState.respond if now - s.task_ended_at < hold else PetState.task_complete
        if s.failed_at is not None and now - s.failed_at < cfg.failed_linger_ms:
            return PetState.failed
        return PetState.idle

    def _update_focus(self, now: float) -> None:
        f = self.focused_session
        if f is not None:
            s = self._sessions.get(f)
            if s is not None and self._is_live(s, now):
                return
        live = [(k, v) for k, v in self._sessions.items() if self._is_live(v, now)]
        if live:
            self.focused_session = max(live, key=lambda kv: kv[1].last_event_at)[0]
        # 没有进行中的会话时保持原焦点，让“递交报告”能停留完。

    def desired_state(self, now: float) -> PetState:
        """不考虑防抖时，此刻“应该”显示的状态。"""
        self._update_focus(now)
        s = self._sessions.get(self.focused_session) if self.focused_session else None
        return self._desired(s, now) if s else PetState.idle

    def tick(self, now: float) -> Optional[PetState]:
        """推进调度。返回新的显示状态（若发生切换）。"""
        want = self.desired_state(now)
        if want == self.displayed:
            self.pending = None
            return None
        if self.pending != want:
            self.pending = want
            self.pending_since = now
        if now - self.pending_since >= self.config.debounce_ms and \
                now - self.displayed_since >= self.config.min_hold_ms:
            self._commit(want, now)
            return want
        return None

    def settle(self, now: float) -> None:
        """立即显示当前应显示的状态（启动时回放完历史后使用，不做防抖）。"""
        self._commit(self.desired_state(now), now)

    def _commit(self, state: PetState, now: float) -> None:
        self.displayed = state
        self.displayed_since = now
        self.pending = None

    def reset(self, now: float) -> None:
        self._sessions = {}
        self.focused_session = None
        self._commit(PetState.idle, now)

    # MARK: 头顶气泡

    def status_line(self, now: float) -> Optional[StatusLine]:
        """气泡内容，跟随当前显示的动作（已防抖）。没有任务时返回 None（隐藏气泡）。"""
        s = self._sessions.get(self.focused_session) if self.focused_session else None
        if s is None:
            return None
        # AskUserQuestion 等“等你回答”的调用显示空闲动作，但任务仍在进行。
        waiting_for_user = s.task_active and bool(s.open) and s.open[-1].state is PetState.question_for_user
        if self.displayed is PetState.idle and not waiting_for_user:
            return None

        progress = None
        if s.todos:
            progress = Progress(sum(1 for t in s.todos if t.status is TodoStatus.completed), len(s.todos))
        in_progress = None
        for t in s.todos:
            if t.status is TodoStatus.in_progress and t.subject:
                in_progress = t.subject
                break

        d = self.displayed
        if d is PetState.failed:
            current = "出错：%s" % s.failed_detail if s.failed_detail else "出错了"
        elif d is PetState.respond:
            current = "整理回答" if s.task_active else "已回答"
        elif d in (PetState.idle, PetState.question_for_user):
            current = (s.open[-1].detail if s.open else None) or "等你回答"
        elif d is PetState.task_complete:
            current = "已完成"
        elif d is PetState.thinking:
            current = in_progress or "思考中"
        else:
            current = in_progress or s.last_detail.get(d) or _FALLBACK_TEXT[d]
        return StatusLine(title=s.title or s.prompt, current=current, progress=progress)

    def snapshot(self) -> Snapshot:
        s = self._sessions.get(self.focused_session) if self.focused_session else None
        return Snapshot(self.focused_session, bool(s and s.task_active),
                        len(s.open) if s else 0, len(self._sessions))


class HeldValue:
    """让显示的文字至少停留一段时间：同一动作里细节变得太快时不逐个闪过。"""

    def __init__(self, value, min_hold_ms: float):
        self.value = value
        self.min_hold_ms = min_hold_ms
        self._changed_at = -INF

    def update(self, new, now: float, immediate: bool = False) -> bool:
        if new == self.value:
            return False
        if not immediate and now - self._changed_at < self.min_hold_ms:
            return False
        self.value = new
        self._changed_at = now
        return True
