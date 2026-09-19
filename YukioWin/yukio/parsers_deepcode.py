"""Deep Code CLI（DeepSeek 终端版）的本地会话记录 → 事件。

Deep Code 把每个项目的会话存在 `~/.deepcode/projects/<项目码>/` 下：

    sessions-index.json   会话列表：标题（summary）、状态、更新时间
    <会话 ID>.jsonl       消息记录，一行一条

消息的字段（由 Deep Code 0.4 写入）：

    {"id", "sessionId", "role": "user|assistant|tool|system", "content",
     "messageParams": {"tool_calls": [...], "reasoning_content": "...",
                       "tool_call_id": "..."},
     "meta": {...}, "visible", "compacted", "createTime", "updateTime"}

这是 Deep Code 在本地写的会话记录，不是公开 API，字段可能随版本变化；
解析失败时只会少事件，不会崩溃，并按失联规则回空闲。
只读取：角色、时间、工具名与参数（用于分类和简短说明）、工具是否报错、任务清单，
不保存、不上传任何对话内容。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .classify import CONTINUE_PREVIOUS, classify, describe
from .events import Kind, PetEvent, PetState, TodoItem, TodoStatus, parse_timestamp

SOURCE = "deepcode"

#: Deep Code 的会话状态（sessions-index.json 里的 status）。
STATUS_PROCESSING = "processing"
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_INTERRUPTED = "interrupted"
STATUS_ASK_PERMISSION = "ask_permission"
STATUS_WAITING_FOR_USER = "waiting_for_user"
STATUS_PERMISSION_DENIED = "permission_denied"

#: 中断时 Deep Code 追加的用户消息以这句开头。
_INTERRUPT_PREFIX = "Interrupted."

_PLAN_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*\[([ >xX~!\-])\]\s*(.+?)\s*$")


def prompt_line(text: Optional[str]) -> Optional[str]:
    """请求的第一行（跳过标签行、合并空白），没有会话标题时当作“大任务”。"""
    if not text:
        return None
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line or line.startswith("<"):
            continue
        return line[:80]
    return None


def parse_plan(markdown: str) -> List[TodoItem]:
    """UpdatePlan 的 markdown 清单 → 任务条目。`[ ]` 未开始、`[>]` 进行中、`[x]` 已完成。"""
    items: List[TodoItem] = []
    for line in (markdown or "").splitlines():
        m = _PLAN_LINE.match(line)
        if not m:
            continue
        mark, subject = m.group(1), m.group(2).strip()
        if not subject:
            continue
        if mark in ("x", "X"):
            status = TodoStatus.completed
        elif mark == ">":
            status = TodoStatus.in_progress
        else:
            status = TodoStatus.pending
        # 编号用序号：UpdatePlan 每次给出完整清单，整体替换。
        items.append(TodoItem(str(len(items)), subject, status))
    return items


def _tool_arguments(function: Any) -> Dict[str, Any]:
    if not isinstance(function, dict):
        return {}
    raw = function.get("arguments")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _tool_result_outcome(content: Any) -> str:
    """工具结果 → "ok" / "failed" / "interrupted"。

    Deep Code 把结果写成 JSON 文本：{"ok": bool, "name": ..., "output"/"error": ...}；
    被用户中断时 metadata.interrupted 为真——中断和拒绝授权都不算失败，不让她沮丧。
    """
    if not isinstance(content, str):
        return "ok"
    text = content.strip()
    if not text.startswith("{"):
        return "ok"
    try:
        parsed = json.loads(text)
    except ValueError:
        return "ok"
    if not isinstance(parsed, dict):
        return "ok"
    metadata = parsed.get("metadata")
    if isinstance(metadata, dict) and metadata.get("interrupted") is True:
        return "interrupted"
    error = parsed.get("error")
    if isinstance(error, str) and ("denied" in error.lower() or "cancell" in error.lower()):
        return "interrupted"
    return "ok" if parsed.get("ok", True) else "failed"


class DeepCodeMessageParser:
    """一条消息 → 若干事件。"""

    source = SOURCE

    def events_from_line(self, data: bytes, fallback_session: str = "",
                         fallback_ts: float = 0.0) -> List[PetEvent]:
        try:
            obj = json.loads(data.decode("utf-8", "replace"))
        except ValueError:
            return []
        if not isinstance(obj, dict):
            return []
        return self.events(obj, fallback_session, fallback_ts)

    def events(self, obj: Dict[str, Any], fallback_session: str = "",
               fallback_ts: float = 0.0) -> List[PetEvent]:
        session = obj.get("sessionId") or fallback_session
        if not isinstance(session, str) or not session:
            return []
        if obj.get("compacted") is True:
            # 被长会话压缩标记的历史消息：重写文件时会重新出现，不当成新活动。
            return []
        ts = parse_timestamp(obj.get("createTime")) or fallback_ts
        role = obj.get("role")
        meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
        params = obj.get("messageParams") if isinstance(obj.get("messageParams"), dict) else {}
        content = obj.get("content") if isinstance(obj.get("content"), str) else ""

        def ev(kind, event_id=None, activity=None, tool=None, detail=None, todos=None):
            return PetEvent(ts, SOURCE, session, kind, event_id=event_id, activity=activity,
                            tool=tool, detail=detail, todos=todos)

        if role == "user":
            stripped = content.strip()
            if stripped.startswith(_INTERRUPT_PREFIX):
                return [ev(Kind.task_abort)]
            if meta.get("isAnswers") is True:
                # 回答 AskUserQuestion：同一轮任务继续，不是新任务。
                return [ev(Kind.thinking)]
            if not stripped:
                return []
            if stripped.startswith("<") and stripped.endswith(">"):
                return []
            return [ev(Kind.task_start, detail=prompt_line(content))]

        if role == "assistant":
            out: List[PetEvent] = []
            tool_calls = params.get("tool_calls")
            if isinstance(params.get("reasoning_content"), str) and params["reasoning_content"].strip():
                out.append(ev(Kind.thinking))
            if isinstance(tool_calls, list) and tool_calls:
                for call in tool_calls:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function")
                    name = function.get("name") if isinstance(function, dict) else None
                    if not isinstance(name, str) or not name:
                        continue
                    args = _tool_arguments(function)
                    kind = classify(name, args)
                    activity = None if kind == CONTINUE_PREVIOUS else kind
                    call_id = call.get("id") if isinstance(call.get("id"), str) else None
                    out.append(ev(Kind.activity_start, event_id=call_id, activity=activity,
                                  tool=name, detail=describe(name, args)))
                    if name.lower() == "updateplan":
                        plan = args.get("plan")
                        if isinstance(plan, str):
                            out.append(ev(Kind.todo_list, todos=parse_plan(plan)))
                if content.strip():
                    # 调用工具前的过程说明不是最终回答。
                    out.append(ev(Kind.thinking))
                return out
            if content.strip():
                out.append(ev(Kind.final_answer))
                out.append(ev(Kind.task_end))
            return out

        if role == "tool":
            call_id = params.get("tool_call_id")
            call_id = call_id if isinstance(call_id, str) and call_id else None
            function = meta.get("function")
            tool = function.get("name") if isinstance(function, dict) else None
            outcome = _tool_result_outcome(content)
            kind = Kind.activity_failed if outcome == "failed" else Kind.activity_end
            return [ev(kind, event_id=call_id, tool=tool if isinstance(tool, str) else None)]

        return []


class DeepCodeIndexParser:
    """sessions-index.json 的条目 → 标题与状态事件。

    索引比消息文件更早反映“正在等你批准”“已中断”“本轮失败”这些状态：
    消息文件里没有对应记录，只有索引会改。
    """

    source = SOURCE

    def __init__(self):
        self._status: Dict[str, str] = {}
        self._title: Dict[str, str] = {}
        #: 为等待类状态开的合成工具调用 ID（等待结束时要关掉）。
        self._waiting: Dict[str, str] = {}

    def events(self, entry: Dict[str, Any], now: float) -> List[PetEvent]:
        session = entry.get("id")
        if not isinstance(session, str) or not session:
            return []
        ts = parse_timestamp(entry.get("updateTime")) or now
        out: List[PetEvent] = []

        summary = entry.get("summary")
        if isinstance(summary, str) and summary.strip() and self._title.get(session) != summary:
            self._title[session] = summary
            out.append(PetEvent(0, SOURCE, session, Kind.session_title, detail=summary.strip()[:80]))

        status = entry.get("status")
        if not isinstance(status, str):
            return out
        previous = self._status.get(session)
        if status == previous:
            return out
        self._status[session] = status

        def ev(kind, event_id=None, activity=None, detail=None):
            return PetEvent(ts, SOURCE, session, kind, event_id=event_id, activity=activity, detail=detail)

        waiting_id = self._waiting.pop(session, None)
        if waiting_id and status not in (STATUS_ASK_PERMISSION, STATUS_WAITING_FOR_USER):
            out.append(ev(Kind.activity_end, event_id=waiting_id))

        if status in (STATUS_ASK_PERMISSION, STATUS_WAITING_FOR_USER):
            # 等你批准／等你回答：立问号卡。消息文件里这一刻没有任何记录。
            call_id = "wait:%s:%s" % (session, int(ts))
            self._waiting[session] = call_id
            detail = "等你批准" if status == STATUS_ASK_PERMISSION else "等你回答"
            out.append(ev(Kind.activity_start, event_id=call_id,
                          activity=PetState.question_for_user, detail=detail))
        elif status == STATUS_INTERRUPTED or status == STATUS_PERMISSION_DENIED:
            # 中断、拒绝授权都不算失败。
            out.append(ev(Kind.task_abort))
        elif status == STATUS_FAILED:
            out.append(ev(Kind.task_failed))
        elif status == STATUS_PROCESSING and previous is not None:
            # 恢复运行：让“沮丧”“等你回答”尽快退场。
            out.append(ev(Kind.thinking))
        return out

    def forget(self, session: str) -> None:
        self._status.pop(session, None)
        self._title.pop(session, None)
        self._waiting.pop(session, None)
