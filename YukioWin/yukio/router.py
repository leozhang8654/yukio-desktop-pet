"""把事件流变成“当前该显示什么”，并施加防抖与最短保持。

时间全部由调用方传入（毫秒），因此可以用虚拟时钟完整测试。
实时模式传入墙钟；回放历史记录时传入事件自身的时间戳。

移植自 YukioPlayer/Sources/YukioCore/ActivityRouter.swift，数值与行为保持一致。
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional

from .cards import ActivityCard, CardStatus
from .events import Kind, PetEvent, PetState, TodoItem, TodoStatus
from .l10n import tr

INF = float("inf")

#: 勾选卡的三种情形：没举、举着、用户点过了（这一轮不再举）。
SIGN_NONE = "none"
SIGN_RAISED = "raised"
SIGN_DISMISSED = "dismissed"


class RouterConfig:
    """路由与调度参数。数值是待调起点，不是用户指定的精确值。"""

    def __init__(self):
        #: 候选状态需稳定这么久才生效（建议 300–600 ms）。
        self.debounce_ms = 400.0
        #: 每个显示状态至少保持这么久（建议 1–2 s）。
        self.min_hold_ms = 1500.0
        #: 工具结束后仍按该工具的活动计算这么久：合并同类连续短调用。
        self.tool_grace_ms = 3500.0
        #: 任务结束后先显示“递交报告”这么久（够播完整理文件那一下），之后换成“完成任务”的勾选卡。
        self.respond_hold_ms = 3000.0
        #: 勾选卡举起来就不自己放下：一直举到用户点击（点击后跳到对应的聊天）。
        #: 这个值只决定“多久之内结束的任务才举牌”：启动时回放到的旧记录不会举一块过期的牌。
        #: 须大于 respond_hold_ms，否则勾选卡永远不出现。
        self.complete_arm_ms = 8000.0
        #: 举着的牌子被晾这么久还没点，就先让位给还在干活的聊天；牌子不放下，
        #: 等那条聊天也停下来时再举回来。
        self.sign_yield_ms = 15 * 60 * 1000.0
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

    def __init__(self, id: str, source: str, now: float):
        #: 这条聊天的会话 ID，也就是 _sessions 字典里的键。判断"这条是不是正开在眼前"要用。
        self.id = id
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
        #: 勾选卡：任务刚结束时举起，举到用户点击为止（见 ActivityRouter.dismiss_completion）。
        #: 三种情形："none" 没举、"raised" 举着、"dismissed" 用户点过了（这一轮不再举）。
        self.sign = SIGN_NONE
        #: 牌子举起来的时刻：晾太久（sign_yield_ms）就先让位给还在干活的聊天。
        self.sign_raised_at: Optional[float] = None
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
        self.sign = SIGN_NONE
        self.sign_raised_at = None

    def end_task(self, now: float, ts: float, keep_answer: bool) -> None:
        self.task_active = False
        self.task_ended_at = now
        self.task_ended_ts = max(self.task_ended_ts, ts)
        self.open = []
        self.last_tool_ended_at = None
        self.failed_at = None
        if not keep_answer:
            self.final_answer_at = None
            self.sign = SIGN_NONE
            self.sign_raised_at = None

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


def state_text(state: PetState) -> str:
    """状态的说法（按界面语言）：气泡没有更具体的文字时用它，聊天列表里也用它。"""
    return {
        PetState.read_file: tr("Reading a file", "阅读文件"),
        PetState.view_image: tr("Viewing an image", "查看图片"),
        PetState.write_file: tr("Editing a file", "修改文件"),
        PetState.verify: tr("Running tests", "运行测试"),
        PetState.read_web: tr("Browsing the web", "浏览网页"),
        PetState.default_work: tr("Working", "处理中"),
        PetState.thinking: tr("Thinking", "思考中"),
        PetState.respond: tr("Writing the answer", "整理回答"),
        PetState.failed: tr("Something went wrong", "出错了"),
        PetState.question_for_user: tr("Waiting for your answer", "等你回答"),
        PetState.task_complete: tr("Done · click to open", "已完成 · 点我打开对话"),
        PetState.idle: tr("Waiting for your answer", "等你回答"),
    }[state]


def state_name(state: PetState) -> str:
    """菜单第一行与托盘提示里的状态名（不是气泡文字）。"""
    return {
        PetState.thinking: tr("Thinking", "思考"),
        PetState.read_file: tr("Reading a file", "读文件"),
        PetState.view_image: tr("Viewing an image", "看图片"),
        PetState.write_file: tr("Editing a file", "写文件"),
        PetState.verify: tr("Running tests", "跑测试"),
        PetState.read_web: tr("Browsing the web", "看网页"),
        PetState.respond: tr("Handing in the answer", "递交回答"),
        PetState.task_complete: tr("Holding the done card", "举着勾选卡"),
        PetState.question_for_user: tr("Holding the question card", "立着问号卡"),
        PetState.default_work: tr("Working", "敲键盘"),
        PetState.failed: tr("Failed", "沮丧"),
        PetState.idle: tr("Idle", "空闲"),
    }[state]


def held_name() -> str:
    """被大手拎着时的状态名。"""
    return tr("Picked up", "被大手拎着")


def ago_text(ms: float) -> str:
    seconds = int(max(0.0, ms) / 1000)
    if seconds < 60:
        return tr("just now", "刚刚")
    if seconds < 3600:
        return tr("%d min ago", "%d 分钟前") % (seconds // 60)
    return tr("%d h ago", "%d 小时前") % (seconds // 3600)


def display_name(title: Optional[str], id: str, max_len: int = 32) -> str:
    """聊天名：会话标题或请求第一行；都没有时用会话 ID 前 8 位。头顶那摞卡也用它。"""
    t = (title or "").strip()
    if not t:
        return tr("Session %s…", "会话 %s…") % id[:8]
    return t[:max_len] + "…" if len(t) > max_len else t


class SessionSummary(NamedTuple):
    """一条聊天（会话）的概要：多个聊天同时跑时，菜单里按这个列出来挑一条跟。"""

    #: 会话 ID（记录文件名），也是点击举牌时用来找聊天的那个 ID。
    id: str
    #: 会话标题；没有标题时是这一轮请求的第一行；都没有时 None。
    title: Optional[str]
    #: 这条聊天此刻会让雪绪显示什么（不经防抖，也不会顺手把勾选卡举起来）。
    state: PetState
    #: 任务进行中且没有失联。
    live: bool
    #: 已经举起勾选卡，等人点（被别的聊天挤掉焦点时仍然举着）。
    raised_sign: bool
    #: 距最近一次事件多久（毫秒）。
    quiet_ms: float
    #: 雪绪当前跟的就是这条。
    focused: bool
    #: 用户在菜单里挑定了这条。
    pinned: bool
    #: 轮到你了：在等你回答、出错停住、或举着勾选卡。
    wants_you: bool = False
    #: 牌子举太久没人点，已经先让位给还在干活的聊天（牌子仍举着）。
    sign_yielded: bool = False

    @property
    def name(self) -> str:
        """聊天名：会话标题或请求第一行；都没有时用会话 ID 前 8 位。"""
        return display_name(self.title, self.id)

    @property
    def status_text(self) -> str:
        """正在做什么：在跑的显示动作，等你处理的说在等什么，其余显示多久没动静。"""
        if self.sign_yielded:
            return tr("Holding the sign for you (stepped aside)", "举着牌子等你（先让位了）")
        if self.raised_sign or self.state is PetState.task_complete:
            return tr("Holding the sign, click her", "举着牌子等你点")
        if self.live:
            return state_text(self.state)
        if self.state is PetState.respond:
            return tr("Just answered", "刚答完")
        if self.state is PetState.failed:
            return tr("Stopped on an error", "出错停住了")
        return ago_text(self.quiet_ms)

    @property
    def menu_label(self) -> str:
        return "%s · %s" % (self.name, self.status_text)


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
        #: 用户在菜单里挑定的聊天：不为 None 时只跟这条，别的聊天再忙也抢不走。
        #: 只在本次运行内有效，重开回到自动。
        self.pinned_session: Optional[str] = None
        #: 此刻正开在眼前的那条聊天（会话 ID）。由 app 每隔一会儿填：桌面版 Claude 在最前面、
        #: 且选中的就是这条时才有值，否则 None。
        #:
        #: 举牌是为了"这条答完了、点我跳过去看"。要是那条聊天本来就开在眼前，人自己已经看见了，
        #: 再举一块牌只是挡路——所以这条聊天不举牌；已经举着的，等你切过去也就放下。
        self.open_chat_session: Optional[str] = None
        self._sessions: Dict[str, _Session] = {}
        self._anonymous = 0
        #: 被点掉／划掉的卡：会话 → 那一轮的 key，下一轮会重新出现。
        self._dismissed_cards: Dict[str, str] = {}
        #: 不再出卡的聊天（本次运行内）。
        self._muted_sessions = set()

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
            s = _Session(e.session, e.source, now)
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

    def _desired(self, s: _Session, now: float, arming: bool = True) -> PetState:
        """arming=False：只看不动，不会把勾选卡举起来（列聊天、出卡时用）。"""
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
        if s.final_answer_at is not None and s.task_ended_at is not None:
            age = now - s.task_ended_at
            # 先递交报告（整理文件那一下），再举勾选卡。
            if age < min(cfg.respond_hold_ms, cfg.complete_arm_ms):
                return PetState.respond
            # 举起来就不放下：等用户点击（点击后 dismiss_completion 把它记成 dismissed）。
            # 举牌只发生在任务刚结束时，所以启动时回放到的旧记录不会举牌。
            # 那条聊天正开在眼前：答完的结果他自己看得见，不举牌；已经举着的也就此放下。
            in_sight = self.open_chat_session is not None and self.open_chat_session == s.id
            if s.sign == SIGN_RAISED:
                if in_sight:
                    if arming:
                        s.sign = SIGN_DISMISSED
                else:
                    return PetState.task_complete
            elif s.sign == SIGN_NONE and age < cfg.complete_arm_ms:
                if in_sight:
                    if arming:
                        s.sign = SIGN_DISMISSED
                else:
                    if arming:
                        s.sign = SIGN_RAISED
                        s.sign_raised_at = now
                    return PetState.task_complete
        if s.failed_at is not None and now - s.failed_at < cfg.failed_linger_ms:
            return PetState.failed
        return PetState.idle

    def _completion_pending(self, s: _Session, now: float) -> bool:
        """这条聊天刚答完、正等着举牌或已经举着牌：答完的提示要让人看见。"""
        if s.sign == SIGN_RAISED:
            return True
        if s.sign != SIGN_NONE or s.final_answer_at is None or s.task_ended_at is None:
            return False
        return now - s.task_ended_at < self.config.complete_arm_ms

    def _waiting_for_user(self, s: _Session, now: float) -> bool:
        """这条聊天在等你拿主意（AskUserQuestion 还没结束）。"""
        return (self._is_live(s, now) and bool(s.open)
                and s.open[-1].state is PetState.question_for_user)

    def _failed_pending(self, s: _Session, now: float) -> bool:
        """整轮出错停在那儿（工具出错时任务还在跑，不算）。"""
        if s.task_active or s.failed_at is None:
            return False
        return now - s.failed_at < self.config.failed_linger_ms

    def _needs_user(self, s: _Session, now: float) -> bool:
        """轮到你了：举着牌子、刚答完、整轮出错、或在等你回答。这类聊天比“还在干活”的优先。"""
        return (self._completion_pending(s, now) or self._waiting_for_user(s, now)
                or self._failed_pending(s, now))

    def _attention_rank(self, s: _Session, now: float) -> Optional[int]:
        """等你处理的分档，越小越先看。和 ChatGPT 桌面版那只宠物的排法一致：

        等你回答 → 出错 → 答完举牌 →（下面才是还在干活的）。牌子晾过头的降到干活之后。
        同一档里给最近的那条。
        """
        if self._waiting_for_user(s, now):
            return 0
        if self._failed_pending(s, now):
            return 1
        if self._completion_pending(s, now) and not self._sign_overdue(s, now):
            return 2
        return None

    def _sign_overdue(self, s: _Session, now: float) -> bool:
        """牌子举了这么久都没人点：先让位给还在干活的聊天。牌子不放下，那条也停了就举回来。"""
        if s.sign != SIGN_RAISED or s.sign_raised_at is None:
            return False
        return now - s.sign_raised_at >= self.config.sign_yield_ms

    def _arm_pending_signs(self, now: float) -> None:
        """任何刚答完的聊天都先把牌子举起来，哪怕这会儿她在跟别的聊天。

        不然别处一忙，这条的牌子过了 complete_arm_ms 就再也举不起来，那一轮的完成提示就丢了。
        仍受 complete_arm_ms 约束：启动时回放到的旧记录不会举一块过期的牌。
        """
        cfg = self.config
        for s in self._sessions.values():
            if s.sign != SIGN_NONE or s.final_answer_at is None or s.task_ended_at is None:
                continue
            age = now - s.task_ended_at
            if cfg.respond_hold_ms <= age < cfg.complete_arm_ms:
                # 那条聊天正开在眼前：人已经看见了，这一轮就不举牌（也不进身侧那叠卡）。
                if self.open_chat_session == s.id:
                    s.sign = SIGN_DISMISSED
                    continue
                s.sign = SIGN_RAISED
                s.sign_raised_at = now

    def _update_focus(self, now: float) -> None:
        self._arm_pending_signs(now)
        # 用户在菜单里挑定了一条：只跟这条，完成与提问也不抢。
        if self.pinned_session is not None:
            if self.pinned_session in self._sessions:
                self.focused_session = self.pinned_session
                return
            # 挑定的那条已经不在了（reset 之后）：回到自动。
            self.pinned_session = None
        # 等你处理的优先：别的聊天还在干活也要先让你看见。
        # 先按档（等你回答 → 出错 → 答完举牌），同档里给最近的那条；处理掉一条再露出下一条。
        best = None
        for k, v in self._sessions.items():
            # 卡被点掉／划掉的那一轮：知道了，先别再抢。
            if self._is_card_dismissed(k, v):
                continue
            rank = self._attention_rank(v, now)
            if rank is None:
                continue
            key = (rank, -v.last_event_at)
            if best is None or key < best[0]:
                best = (key, k)
        if best is not None:
            self.focused_session = best[1]
            return
        f = self.focused_session
        if f is not None:
            s = self._sessions.get(f)
            if s is not None and self._is_live(s, now):
                return
        live = [(k, v) for k, v in self._sessions.items() if self._is_live(v, now)]
        if live:
            self.focused_session = max(live, key=lambda kv: kv[1].last_event_at)[0]
            return
        # 没人在干活了：晾久让位的牌子重新举回来。
        # 当前这条还有东西要显示（沮丧、没停完的递交报告）时先不换。
        if f is not None:
            s = self._sessions.get(f)
            if s is not None and self._desired(s, now, arming=False) is not PetState.idle:
                return
        overdue = [(k, v) for k, v in self._sessions.items()
                   if self._needs_user(v, now) and not self._is_card_dismissed(k, v)]
        if overdue:
            self.focused_session = max(overdue, key=lambda kv: kv[1].last_event_at)[0]
        # 都没有时保持原焦点，让“递交报告”能停留完。

    # MARK: 多个聊天同时跑时挑一条

    def session_summaries(self, now: float, quiet_within_ms: float = INF,
                          limit: Optional[int] = None) -> List[SessionSummary]:
        """最近的聊天，按“先看谁”排：等你处理的在最前，然后是在跑的，再按安静时间。

        quiet_within_ms：多久没动静就不列了（等你处理的、在跑的、挑定的、正跟着的一定保留）。
        """
        self._update_focus(now)
        rows = []
        for id, s in self._sessions.items():
            live = self._is_live(s, now)
            wants = self._needs_user(s, now) and not self._is_card_dismissed(id, s)
            focused = id == self.focused_session
            pinned = id == self.pinned_session
            quiet = max(0.0, now - s.last_event_at)
            if not (wants or live or focused or pinned or quiet <= quiet_within_ms):
                continue
            # 等你处理的按档排在最前（0–2），然后是在干活的，再是挑定／正跟着的，最后其余。
            rank = self._attention_rank(s, now) if wants else None
            if rank is None:
                rank = 3 if wants else (4 if live else (5 if (pinned or focused) else 6))
            rows.append((rank, quiet, SessionSummary(
                id=id, title=s.title or s.prompt, state=self._desired(s, now, arming=False),
                live=live, raised_sign=s.sign == SIGN_RAISED, quiet_ms=quiet,
                focused=focused, pinned=pinned, wants_you=wants,
                sign_yielded=self._sign_overdue(s, now))))
        # 同样新旧时按 ID 排，给个稳定顺序。
        rows.sort(key=lambda r: (r[0], r[1], r[2].id))
        out = [r[2] for r in rows]
        return out if limit is None else out[:limit]

    def pin_session(self, id: Optional[str], now: float) -> bool:
        """在菜单里挑一条聊天跟：传 None 回到自动（完成与提问优先）。挑中立刻生效，不等防抖。

        返回 False 表示播放器没见过这条聊天（菜单只会给出见过的）。
        """
        if id is not None:
            if id not in self._sessions:
                return False
            self.pinned_session = id
            self.focused_session = id
        else:
            self.pinned_session = None
        self._commit(self.desired_state(now), now)
        return True

    def desired_state(self, now: float) -> PetState:
        """不考虑防抖时，此刻“应该”显示的状态。"""
        self._update_focus(now)
        s = self._sessions.get(self.focused_session) if self.focused_session else None
        return self._desired(s, now) if s else PetState.idle

    @property
    def completed_session(self) -> Optional[str]:
        """正举着勾选卡的会话 ID：点击雪绪时跳到这条聊天。没举牌时为 None。"""
        if self.displayed is not PetState.task_complete or not self.focused_session:
            return None
        s = self._sessions.get(self.focused_session)
        return self.focused_session if s is not None and s.sign == SIGN_RAISED else None

    @property
    def asking_session(self) -> Optional[str]:
        """正立着问号卡的会话 ID：点击雪绪时跳到这条聊天去回答。没在问时为 None。

        和勾选卡不同，点了不收卡：问题还等着你答，卡片等 AskUserQuestion 结束自己收。
        """
        if self.displayed is not PetState.question_for_user or not self.focused_session:
            return None
        return self.focused_session if self.focused_session in self._sessions else None

    def dismiss_completion(self, now: float) -> bool:
        """用户点了举着的牌子：放下，立刻回到此刻该显示的状态（不等防抖）。返回是否真的放下了。"""
        s = self._sessions.get(self.focused_session) if self.focused_session else None
        if s is None or s.sign != SIGN_RAISED:
            return False
        s.sign = SIGN_DISMISSED
        self._commit(self.desired_state(now), now)
        return True

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
        self.pinned_session = None
        self._dismissed_cards = {}
        self._muted_sessions = set()
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
            current = tr("Error: %s", "出错：%s") % s.failed_detail if s.failed_detail else tr("Something went wrong", "出错了")
        elif d is PetState.respond:
            current = tr("Writing the answer", "整理回答") if s.task_active else tr("Answered", "已回答")
        elif d in (PetState.idle, PetState.question_for_user):
            # 问号卡也能点（跳到这条聊天去回答），和勾选卡一样在气泡里说一声，不然没人知道能点。
            current = tr("Your turn · click to open", "%s · 点我打开对话" % (
                (s.open[-1].detail if s.open else None) or "等你回答"))
        elif d is PetState.task_complete:
            current = tr("Done · click to open", "已完成 · 点我打开对话")
        elif d is PetState.thinking:
            current = in_progress or tr("Thinking", "思考中")
        else:
            current = in_progress or s.last_detail.get(d) or state_text(d)
        return StatusLine(title=s.title or s.prompt, current=current, progress=progress)

    # MARK: 头顶那摞通知卡

    def cards(self, now: float, limit: int = 6, include_focused: bool = False) -> List[ActivityCard]:
        """头顶那摞卡：除了她正跟着的那条，其余有话要跟你说的聊天。

        排序和焦点用的是同一套档位（等你回答 → 出错 → 答完 → 在跑），同档里最近的在前。
        消掉的、静音的、没话要说的不列。

        include_focused=True 时连她正显示的那条也列出来（--cards 自查用）。
        """
        self._update_focus(now)
        rows = []
        for id, s in self._sessions.items():
            if not include_focused and id == self.focused_session:
                continue
            if id in self._muted_sessions:
                continue
            status = self._card_status(s, now)
            if status is None or self._is_card_dismissed(id, s):
                continue
            quiet = max(0.0, now - s.last_event_at)
            rows.append((CardStatus.rank(status), quiet, ActivityCard(
                session=id, title=display_name(s.title or s.prompt, id),
                subtitle=self._card_subtitle(s, status, now), status=status, quiet_ms=quiet)))
        rows.sort(key=lambda r: (r[0], r[1], r[2].session))
        return [r[2] for r in rows[:limit]]

    def dismiss_card(self, session: str, now: float) -> None:
        """点掉一张卡（打开那条聊天之后，或按卡上的 ✕）。

        举着的勾选卡就此放下；其余的卡这一轮不再出现，那条聊天下一轮有动静时会再来。
        """
        s = self._sessions.get(session)
        if s is None:
            return
        if s.sign == SIGN_RAISED:
            s.sign = SIGN_DISMISSED
        self._dismissed_cards[session] = self._card_turn_key(s)
        if session == self.focused_session:
            self._commit(self.desired_state(now), now)

    def mute_cards(self, session: str) -> None:
        """这条聊天不再出卡（本次运行内有效）。"""
        self._muted_sessions.add(session)

    def unmute_cards(self, session: str) -> None:
        self._muted_sessions.discard(session)

    def is_muted(self, session: str) -> bool:
        return session in self._muted_sessions

    def _card_status(self, s: _Session, now: float) -> Optional[str]:
        """这条聊天该出什么卡；没话要说时 None。"""
        if self._waiting_for_user(s, now):
            return CardStatus.waiting
        if self._failed_pending(s, now):
            return CardStatus.failed
        if self._completion_pending(s, now):
            return CardStatus.ready
        if self._is_live(s, now):
            return CardStatus.running
        return None

    def _card_subtitle(self, s: _Session, status: str, now: float) -> str:
        if status == CardStatus.waiting:
            return (s.open[-1].detail if s.open else None) or tr("Needs your decision", "等你拿主意")
        if status == CardStatus.failed:
            return (tr("Error: %s", "出错：%s") % s.failed_detail) if s.failed_detail else tr("Didn't finish this turn", "这一轮没做完")
        if status == CardStatus.ready:
            return tr("Take a look", "点开看看")
        state = self._desired(s, now, arming=False)
        for t in s.todos:
            if t.status is TodoStatus.in_progress and t.subject:
                return t.subject
        return s.last_detail.get(state) or state_text(state)

    def _is_card_dismissed(self, id: str, s: _Session) -> bool:
        """这张卡这一轮被点掉过吗。"""
        return self._dismissed_cards.get(id) == self._card_turn_key(s)

    @staticmethod
    def _card_turn_key(s: _Session) -> str:
        """卡片按“这一轮”记消掉：那条聊天下一轮开始（task_started_ts 变了）时会重新出现。"""
        def stamp(v: float) -> str:
            # 没开始／没结束时是 -inf，不能直接转整数。
            return str(int(v)) if v not in (INF, -INF) else "-"
        return "%s-%s" % (stamp(s.task_started_ts), stamp(s.task_ended_ts))

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
