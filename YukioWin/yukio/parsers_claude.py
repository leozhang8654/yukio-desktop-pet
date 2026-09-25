"""Claude Code 会话转录（~/.claude/projects/<项目>/<会话>.jsonl）→ 事件。

保留这一路是因为：在 Windows 上把 Claude Code 指向 DeepSeek 的 Anthropic 兼容端点
（ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic）时，跑的是 DeepSeek 模型，
写出来的仍是 Claude Code 格式的转录。两种 DeepSeek 用法因此都能跟随。

这是 Claude Code 本地写入的会话记录，不是公开 API；字段可能随版本变化。
移植自 YukioPlayer/Sources/YukioCore/ClaudeParsers.swift。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .classify import CONTINUE_PREVIOUS, classify, describe, question
from .events import Kind, PetEvent, TodoItem, TodoStatus, parse_timestamp

SOURCE = "claude-transcript"


def prompt_line(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line or line.startswith("<"):
            continue
        return line[:80]
    return None


def _is_failure(result: Dict[str, Any]) -> bool:
    """工具结果是否算失败：is_error 为真，且不是用户拒绝授权或中断。"""
    if result.get("is_error") is not True:
        return False
    content = result.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    else:
        text = ""
    return not ("doesn't want to proceed" in text or text.startswith("[Request interrupted"))


def _todo_id(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _task_events(tool: str, input: Dict[str, Any]):
    """任务清单工具 → (事件类型, 条目)。"""
    if tool == "TodoWrite":
        todos = input.get("todos")
        if not isinstance(todos, list):
            return None
        items = []
        for i, t in enumerate(todos):
            if not isinstance(t, dict):
                continue
            status = t.get("status")
            try:
                parsed = TodoStatus(status) if isinstance(status, str) else TodoStatus.pending
            except ValueError:
                parsed = TodoStatus.pending
            items.append(TodoItem(_todo_id(t.get("id")) or str(i),
                                  t.get("content") or t.get("activeForm"), parsed))
        return Kind.todo_list, items
    if tool == "TaskUpdate":
        tid = _todo_id(input.get("taskId"))
        if not tid:
            return None
        status = input.get("status")
        try:
            parsed = TodoStatus(status) if isinstance(status, str) else None
        except ValueError:
            parsed = None
        subject = input.get("subject") if isinstance(input.get("subject"), str) else None
        if parsed is None and subject is None:
            return None
        return Kind.todo_update, [TodoItem(tid, subject, parsed)]
    return None


def _task_created(result: Any) -> Optional[TodoItem]:
    """TaskCreate 的结果：{"task": {"id": "3", "subject": "…"}}。"""
    if not isinstance(result, dict):
        return None
    task = result.get("task")
    if not isinstance(task, dict):
        return None
    tid = _todo_id(task.get("id"))
    subject = task.get("subject")
    if not tid or not isinstance(subject, str):
        return None
    return TodoItem(tid, subject)


class ClaudeTranscriptParser:
    source = SOURCE

    def events_from_line(self, data: bytes, fallback_session: str = "",
                         fallback_ts: float = 0.0) -> List[PetEvent]:
        try:
            obj = json.loads(data.decode("utf-8", "replace"))
        except ValueError:
            return []
        return self.events(obj) if isinstance(obj, dict) else []

    def events(self, obj: Dict[str, Any]) -> List[PetEvent]:
        type_ = obj.get("type")
        session = obj.get("sessionId")
        if not isinstance(type_, str) or not isinstance(session, str):
            return []
        # 子代理（sidechain）的活动不驱动主角色。
        if obj.get("isSidechain") is True:
            return []
        if type_ in ("custom-title", "ai-title"):
            title = obj.get("customTitle") or obj.get("aiTitle")
            if not isinstance(title, str):
                return []
            return [PetEvent(0, SOURCE, session, Kind.session_title, detail=title)]
        ts = parse_timestamp(obj.get("timestamp"))
        if ts is None:
            return []

        def ev(kind, event_id=None, activity=None, tool=None, detail=None, todos=None, question=None):
            return PetEvent(ts, SOURCE, session, kind, event_id=event_id, activity=activity,
                            tool=tool, detail=detail, todos=todos, question=question)

        if type_ == "user":
            if obj.get("isMeta") is True or obj.get("isCompactSummary") is True:
                return []
            message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, list):
                results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if results:
                    out = []
                    for b in results:
                        tid = b.get("tool_use_id")
                        if not isinstance(tid, str):
                            continue
                        out.append(ev(Kind.activity_failed if _is_failure(b) else Kind.activity_end, event_id=tid))
                    item = _task_created(obj.get("toolUseResult"))
                    if item:
                        out.append(ev(Kind.todo_update, todos=[item]))
                    return out
                text = "\n".join(b.get("text", "") for b in content
                                 if isinstance(b, dict) and b.get("type") == "text")
                kind = self._user_text(text, bool(content))
                return [ev(kind, detail=prompt_line(text))] if kind else []
            if isinstance(content, str):
                kind = self._user_text(content, False)
                return [ev(kind, detail=prompt_line(content))] if kind else []
            return []

        if type_ == "assistant":
            message = obj.get("message")
            if not isinstance(message, dict):
                return []
            if message.get("model") == "<synthetic>":
                # 客户端合成的消息：本轮不会再有真实回答。
                return [ev(Kind.task_failed if obj.get("isApiErrorMessage") is True else Kind.task_abort)]
            stop = message.get("stop_reason")
            blocks = message.get("content") if isinstance(message.get("content"), list) else []
            out: List[PetEvent] = []
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                btype = b.get("type")
                if btype == "tool_use":
                    name = b.get("name") or ""
                    input = b.get("input") if isinstance(b.get("input"), dict) else {}
                    kind = classify(name, input)
                    activity = None if kind == CONTINUE_PREVIOUS else kind
                    bid = b.get("id") if isinstance(b.get("id"), str) else None
                    out.append(ev(Kind.activity_start, event_id=bid, activity=activity,
                                  tool=name, detail=describe(name, input),
                                  question=question(name, input)))
                    task = _task_events(name, input)
                    if task:
                        out.append(ev(task[0], todos=task[1]))
                elif btype in ("thinking", "redacted_thinking"):
                    out.append(ev(Kind.thinking))
                elif btype == "text":
                    if stop in ("end_turn", "stop_sequence"):
                        out.append(ev(Kind.final_answer))
                        out.append(ev(Kind.task_end))
                    else:
                        out.append(ev(Kind.thinking))
            return out

        if type_ == "system":
            # Stop hook 摘要只在一轮结束后出现，可作为结束的补充信号。
            return [ev(Kind.task_end)] if obj.get("subtype") == "stop_hook_summary" else []
        return []

    @staticmethod
    def _user_text(text: str, has_other_blocks: bool) -> Optional[Kind]:
        t = text.strip()
        if t.startswith("[Request interrupted by user"):
            return Kind.task_abort
        # 本地命令（/clear、/model 等）的回显不会触发模型回答。
        if t.startswith("<local-command-") or t.startswith("<command-name>") or t.startswith("<command-message>"):
            return None
        if not t and not has_other_blocks:
            return None
        return Kind.task_start
