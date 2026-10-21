"""GPT（Codex）的本机会话记录 → 事件。

Codex 把每条聊天写在 `~/.codex/sessions/<年>/<月>/<日>/rollout-<时间>-<会话 ID>.jsonl`，
一行一条 JSON：`{"timestamp", "type", "payload"}`。这是 Codex 在本地写的记录、不是公开 API，
字段会随版本变化；认不出的行直接跳过，只会少事件，不会崩溃，并按失联规则回空闲。
只读取：条目类型、时间、工具名与参数（用于分类和简短说明）、成败、请求第一行与会话 ID，
不保存、不上传任何对话内容。

同一个文件里两套记录并存，都认：
  * ``response_item`` —— 送给模型的那一份（function_call／custom_tool_call／message／reasoning），
    工具**开始**时就写下，所以动作跟得上；
  * ``event_msg`` —— 界面事件（item_completed／task_complete／turn_aborted），
    工具**结束**之后才写，用来补成败和「一轮结束」。
两套记录可能属于不同层级。仅显式调用引用或已知的同一 ID 可关联；其余回执保留为未关联。

这是 YukioPlayer/Sources/YukioCore/CodexParsers.swift 的 Python 移植，规则保持一致。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .classify import CONTINUE_PREVIOUS, classify, classify_mcp, classify_shell, describe, shell_summary
from .codex_results import CodexResultTracker, identifier
from .events import Kind, PetEvent, PetQuestion, PetState, TodoItem, TodoStatus, parse_timestamp
from .l10n import tr

SOURCE = "codex"

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def session_id_from_file_name(name: str) -> str:
    """``rollout-2026-09-22T19-10-20-<会话 ID>[_<分支 ID>].jsonl`` → 会话 ID。

    记录里的 session_meta 一到就以它为准，这里只是先有个名字。
    """
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    if base.endswith(".jsonl"):
        base = base[: -len(".jsonl")]
    last = base.rsplit("_", 1)[-1]
    tail = last[-36:]
    return tail if _UUID.match(tail) else base


def prompt_line(text: Optional[str]) -> Optional[str]:
    """请求的第一行。整条以 ``<`` 开头的是塞给模型的环境说明，不是人说的话。"""
    if not text:
        return None
    stripped = text.strip()
    if not stripped or stripped.startswith("<"):
        return None
    for raw in stripped.splitlines():
        line = " ".join(raw.split())
        if not line or line.startswith("<"):
            continue
        return line[:80]
    return None


def question_reply_calls(text):
    text = text.strip()
    start, end = '<send_user_message_question_reply>', '</send_user_message_question_reply>'
    if not (text.startswith(start) and text.endswith(end)):
        return None
    try:
        replies = json.loads(text[len(start):-len(end)])
    except ValueError:
        return set()
    if not isinstance(replies, list):
        return set()
    calls = set()
    for reply in replies:
        if not isinstance(reply, dict) or not isinstance(reply.get('answer'), str):
            continue
        try:
            ident = json.loads(reply.get('questionItemId', ''))
        except (ValueError, TypeError):
            continue
        if (isinstance(ident, list) and len(ident) == 3 and isinstance(ident[0], str)
                and ident[0].split('.')[-1] in ('request_user_input', 'request_user_input_async')
                and isinstance(ident[1], str) and ident[1] and type(ident[2]) is int and ident[2] == 0):
            calls.add(ident[1])
    return calls


def content_text(content: Any) -> str:
    """content 可能是字符串，也可能是 ``[{"type": "input_text", "text": …}]``。"""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(part.get("text", "") for part in content
                     if isinstance(part, dict) and isinstance(part.get("text"), str))


def as_dict(value: Any) -> Dict[str, Any]:
    """参数可能已经是字典，也可能是一段 JSON 文本。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def plan_items(value: Any) -> Optional[List[TodoItem]]:
    """``update_plan`` 的清单 → 任务条目。每次给出完整清单，所以整体替换、编号用序号。"""
    if not isinstance(value, list) or not value:
        return None
    out: List[TodoItem] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        subject = row.get("step") or row.get("text") or row.get("title")
        if not isinstance(subject, str) or not subject:
            continue
        status = str(row.get("status") or "").lower()
        if status in ("completed", "done", "complete"):
            state = TodoStatus.completed
        elif status in ("in_progress", "inprogress", "running", "active"):
            state = TodoStatus.in_progress
        else:
            state = TodoStatus.pending
        out.append(TodoItem(str(len(out)), subject, state))
    return out or None


# MARK: exec 的 JS 正文


def _literal(text: str, start: int) -> str:
    """读一段 JS 字符串字面量，解掉常见转义。"""
    quote = text[start]
    out: List[str] = []
    i = start + 1
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                pass
            elif nxt == "u":
                i += 4
            else:
                out.append(nxt)
            i += 2
            continue
        if c == quote:
            return "".join(out)
        out.append(c)
        i += 1
    return "".join(out)


def string_value(key: str, script: str) -> Optional[str]:
    """从 JS 正文里取 ``key: "值"``（``{cmd:"…"}`` 与 ``{"cmd":"…"}`` 都认）。"""
    i = 0
    while True:
        i = script.find(key, i)
        if i < 0:
            return None
        start = i
        i += len(key)
        if start > 0 and (script[start - 1].isalnum() or script[start - 1] == "_"):
            continue
        j = i
        if j < len(script) and script[j] in "\"'":
            j += 1
        while j < len(script) and script[j] == " ":
            j += 1
        if j >= len(script) or script[j] != ":":
            continue
        j += 1
        while j < len(script) and script[j] == " ":
            j += 1
        if j < len(script) and script[j] in "\"'`":
            return _literal(script, j)


def display_name(path: str) -> str:
    """路径 → 文件名（file:// 与百分号转义也认）。"""
    from urllib.parse import unquote

    text = path[7:] if path.startswith("file://") else path
    text = unquote(text)
    return text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or text


def patch_target(patch: str) -> Optional[str]:
    """补丁正文里改的是哪个文件。"""
    for marker in ("*** Update File: ", "*** Add File: ", "*** Delete File: ", "*** Move to: "):
        at = patch.find(marker)
        if at < 0:
            continue
        line = patch[at + len(marker):].splitlines()[0] if patch[at + len(marker):] else ""
        line = line.replace("\\n", "").strip()
        if line:
            return display_name(line)
    return None


def browser_state(code: str) -> PetState:
    """计算机操作／浏览器脚本：截图算看图，开标签页与读页面算看网页，其余算工作。"""
    lower = code.lower()
    if "screenshot" in lower or "captureimage" in lower:
        return PetState.view_image
    for hint in ("browsertab", "browser", "navigate", "openurl", "gettabcontext", "readpage", "chrome"):
        if hint in lower:
            return PetState.read_web
    return PetState.default_work


def classify_exec(script: str):
    """exec 的 JS 正文 → (活动, 说明)。认不出来返回 None，交给调用方按工具名兜底。"""
    if "view_image" in script:
        path = string_value("path", script)
        name = display_name(path) if path else None
        return PetState.view_image, (tr("Viewing %s", "查看 %s") % name if name else None)
    if "apply_patch" in script or "*** Begin Patch" in script:
        name = patch_target(script)
        return PetState.write_file, (tr("Editing %s", "编辑 %s") % name if name
                                     else tr("Editing a file", "修改文件"))
    if "write_stdin" in script or "tools.wait(" in script or "read_output" in script:
        return CONTINUE_PREVIOUS, None
    if "exec_command" in script:
        command = string_value("cmd", script)
        if not command:
            return PetState.default_work, None
        summary = shell_summary(command)
        return classify_shell(command), ("$ %s" % summary if summary else None)
    if "imagegen" in script or "image_gen" in script:
        return PetState.default_work, tr("Drawing a picture", "画图")
    if "cua." in script:
        return browser_state(script), None
    return None


def classify_tool(tool: str, namespace: Optional[str], arguments: Dict[str, Any], script: Optional[str]):
    """Codex 的工具 → (活动, 说明)。活动可能是 CONTINUE_PREVIOUS。"""
    key = (tool or "").lower()
    if script:
        hit = classify_exec(script)
        if hit:
            return hit

    if key in ("shell", "local_shell", "exec", "exec_command", "container.exec", "run_command", "run_terminal_cmd"):
        command = _command(arguments)
        if not command:
            return PetState.default_work, None
        summary = shell_summary(command)
        return classify_shell(command), ("$ %s" % summary if summary else None)
    if key in ("apply_patch", "applypatch", "edit_file", "write_file", "create_file", "str_replace_editor"):
        patch = arguments.get("input") or arguments.get("patch") or script or ""
        name = patch_target(patch if isinstance(patch, str) else "") or _path(arguments)
        return PetState.write_file, (tr("Editing %s", "编辑 %s") % name if name else None)
    if key in ("update_plan", "update_todo", "set_plan"):
        return PetState.thinking, tr("Updating the task list", "整理任务清单")
    if key in ("view_image", "read_image", "show_image"):
        name = _path(arguments)
        return PetState.view_image, (tr("Viewing %s", "查看 %s") % name if name else None)
    if key in ("web_search", "search_web", "browser_search"):
        query = arguments.get("query") or arguments.get("q")
        return PetState.read_web, (tr("Searching the web: %s", "搜索网页 %s") % query
                                   if isinstance(query, str) and query else None)
    if key in ("wait", "wait_agent", "write_stdin", "read_output", "kill_command", "sleep", "clock"):
        # 等一条还在跑的命令／等另一个智能体：延续上一个动作，别切回敲键盘。
        return CONTINUE_PREVIOUS, None
    if key in ("request_user_input_async", "request_user_input", "ask_user", "ask_user_question"):
        return PetState.question_for_user, (_question(arguments) or tr("Needs your answer", "等你回答"))
    if key in ("spawn_agent", "followup_task", "interrupt_agent", "list_agents"):
        what = arguments.get("task") or arguments.get("prompt") or arguments.get("name")
        return PetState.thinking, (tr("Delegating: %s", "委派：%s") % what if isinstance(what, str) and what
                                   else tr("Delegating to a helper", "委派助手"))

    if namespace:
        full = namespace + "__" + tool if namespace.startswith("mcp__") else "mcp__%s__%s" % (namespace, tool)
        code = arguments.get("code")
        state = browser_state(code) if isinstance(code, str) and code else classify_mcp(full, arguments)
        title = arguments.get("title")
        detail = title.strip() if isinstance(title, str) and title.strip() else describe(full, arguments)
        return state, detail

    # 兜底：认 Claude／Deep Code 那套工具名。
    return classify(tool, arguments), describe(tool, arguments)


def _command(arguments: Dict[str, Any]) -> str:
    """``command`` 可能是字符串，也可能是 ``["bash", "-lc", "…"]``。"""
    for key in ("command", "cmd", "script"):
        value = arguments.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            words = [w for w in value if isinstance(w, str)]
            if len(words) >= 2 and words[0].rsplit("/", 1)[-1] in ("bash", "sh", "zsh"):
                return words[-1]
            return " ".join(words)
    return ""


def _path(arguments: Dict[str, Any]) -> Optional[str]:
    for key in ("path", "file_path", "filepath", "file", "image_path"):
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return display_name(value)
    return None


def _question(arguments: Dict[str, Any]) -> Optional[str]:
    q = PetQuestion.parse(arguments)
    return q.short_label if q else None


#: Codex 那几种问话工具名（`classify_tool` 里用的是同一组）。
_ASK_TOOLS = ("request_user_input_async", "request_user_input", "ask_user", "ask_user_question",
              "askuserquestion")


def tool_question(tool: str, arguments: Dict[str, Any]) -> Optional[PetQuestion]:
    """这次调用是不是在问你话；是就把问题抄下来。"""
    if not isinstance(tool, str) or tool.lower() not in _ASK_TOOLS:
        return None
    return PetQuestion.parse(arguments)


class CodexRolloutParser:
    """一个实例跟一个文件；结果按调用身份隔离，不按到达顺序猜测。"""

    source = SOURCE

    def __init__(self, session: str = ""):
        self.session = session
        self._results = CodexResultTracker()
        self.last_tool_results = []
        self._async_questions = set()

    def history_checkpoint(self):
        return dict(version=1, session=self.session, results=dict(
            turn_id=self._results.turn_id, closed=self._results.closed,
            calls=[dict(id=k, outcomes=sorted(v)) for k, v in self._results.calls.items()],
            retired=list(self._results.retired)))

    @classmethod
    def from_history_checkpoint(cls, state):
        from collections import OrderedDict
        if state['version'] != 1 or not isinstance(state['session'], str):
            raise ValueError('Invalid activity history checkpoint')
        result = cls(state['session'])
        saved = state['results']
        calls, retired = saved['calls'], saved['retired']
        if (len(calls) > 4096 or len(retired) > 4096
                or len({c['id'] for c in calls}) != len(calls) or len(set(retired)) != len(retired)
                or type(saved['closed']) is not bool
                or saved.get('turn_id') is not None and not isinstance(saved['turn_id'], str)
                or any(not isinstance(c['id'], str) or not isinstance(c['outcomes'], list)
                       or any(o not in ('succeeded', 'failed', 'cancelled', 'unknown') for o in c['outcomes']) for c in calls)
                or any(not isinstance(c, str) for c in retired)):
            raise ValueError('Invalid activity history checkpoint')
        result._results.turn_id = saved.get('turn_id')
        result._results.closed = saved['closed']
        result._results.calls = OrderedDict((c['id'], set(c['outcomes'])) for c in calls)
        result._results.retired = OrderedDict((c, None) for c in retired)
        return result

    def events_from_line(self, data: bytes, fallback_session: str = "", fallback_ts: float = 0.0) -> List[PetEvent]:
        self.last_tool_results = []
        try:
            obj = json.loads(data.decode("utf-8", "replace"))
        except ValueError:
            return []
        if not isinstance(obj, dict):
            return []
        if not self.session and fallback_session:
            self.session = session_id_from_file_name(fallback_session)
        return self.events(obj, fallback_ts)

    def events(self, obj: Dict[str, Any], now: float = 0.0) -> List[PetEvent]:
        self.last_tool_results = []
        payload = obj.get("payload")
        payload = payload if isinstance(payload, dict) else obj
        kind = payload.get("type") or obj.get("type") or ""
        ts = parse_timestamp(obj.get("timestamp")) or parse_timestamp(payload.get("timestamp")) or now

        if kind == "session_meta":
            found = payload.get("session_id") or payload.get("id")
            if isinstance(found, str) and found:
                if found != self.session:
                    self._results.reset()
                    self._async_questions.clear()
                self.session = found
            return []
        if not self.session:
            found = payload.get("thread_id") or payload.get("session_id")
            if isinstance(found, str) and found:
                self.session = found
        if not self.session:
            return []
        if identifier(payload.get("thread_id")) not in (None, self.session):
            return []

        def ev(kind_, event_id=None, activity=None, tool=None, detail=None, todos=None, at=None,
               question=None):
            return PetEvent(ts if at is None else at, SOURCE, self.session, kind_, event_id=event_id,
                            activity=activity, tool=tool, detail=detail, todos=todos, question=question)

        if kind in ("task_started", "turn_context"):
            turn = identifier(payload.get("turn_id"))
            if turn and turn != self._results.turn_id:
                self._async_questions.clear()
            self._results.begin_turn(turn)
            return []
        if kind == "task_complete":
            if not self._results.matches_turn(payload.get("turn_id")):
                return []
            self._async_questions.clear()
            self._results.close_turn()
            # 有回答才算答完：没有 last_agent_message 的一轮（被压缩、被接管）只算结束。
            answered = bool(payload.get("last_agent_message"))
            return [ev(Kind.final_answer), ev(Kind.task_end)] if answered else [ev(Kind.task_end)]
        if kind == "turn_aborted":
            if not self._results.matches_turn(payload.get("turn_id")):
                return []
            self._async_questions.clear()
            self._results.close_turn()
            # 用户按停、或被新一轮顶掉：都不算失败，不让她沮丧。
            reason = str(payload.get("reason") or "").lower()
            return [ev(Kind.task_failed if "error" in reason else Kind.task_abort)]
        if kind in ("error", "stream_error"):
            if not self._results.matches_turn(payload.get("turn_id")):
                return []
            self._async_questions.clear()
            self._results.close_turn()
            return [ev(Kind.task_failed)]
        if kind in ("item_completed", "item_started", "item_updated"):
            return self._item(payload.get("item"), payload, ts, ev, completed=kind == "item_completed")

        if kind == "message":
            role = payload.get("role")
            text = content_text(payload.get("content"))
            if role == "user":
                return self._user_message(text, ev)
            if role == "assistant":
                # 中间的过程说明不是最终回答：一轮什么时候结束由 task_complete 说了算。
                return [ev(Kind.thinking)] if text.strip() else []
            return []
        if kind == "reasoning":
            return [ev(Kind.thinking)]
        if kind in ("function_call", "custom_tool_call", "local_shell_call"):
            return self._tool_start(payload, ev)
        if kind in ("function_call_output", "custom_tool_call_output", "local_shell_call_output"):
            return self._tool_end(payload, ts, ev)
        if kind == "web_search_call":
            action = payload.get("action")
            query = (action or {}).get("query") if isinstance(action, dict) else None
            return self._search_pair(payload.get("id"), query or payload.get("query"), ts, ev)
        return []

    # MARK: event_msg 里的条目
    #
    # 这些条目是界面条目的回执，可能与外层 response_item 的工具不同，
    # 保存结果元数据；有身份依据时才补外层成败。网页搜索仍保留原有显示投影。

    def _item(self, item: Any, payload, ts, ev, completed: bool) -> List[PetEvent]:
        if not isinstance(item, dict):
            return []
        kind = item.get("type")
        if kind == "UserMessage":
            return self._user_message(content_text(item.get("content")), ev) if completed else []
        if kind == "AgentMessage":
            if not completed:
                return []
            # phase 有时写明这条是最终回答；没写就当过程说明。
            return [ev(Kind.final_answer if item.get("phase") == "final_answer" else Kind.thinking)]
        if kind == "Reasoning":
            return [ev(Kind.thinking)] if completed else []
        if kind in ("CommandExecution", "McpToolCall", "CollabAgentToolCall", "DynamicToolCall"):
            if completed:
                self.last_tool_results = [self._results.record(
                    session=self.session, payload=payload, item=item,
                    source_kind="item_completed", timestamp=ts)]
            return []
        if kind == "WebSearch" and completed:
            return self._search_pair(item.get("id"), item.get("query"), None, ev)
        if kind == "Extension" and completed and str(item.get("kind") or "").startswith("web."):
            return self._search_pair(item.get("id"), item.get("query"), None, ev)
        if kind in ("TodoList", "PlanUpdate") and completed:
            todos = plan_items(item.get("items") or item.get("plan"))
            return [ev(Kind.todo_list, todos=todos)] if todos else []
        return []

    def _tool_start(self, payload: Dict[str, Any], ev) -> List[PetEvent]:
        name = payload.get("name") or ""
        namespace = payload.get("namespace")
        arguments = as_dict(payload.get("arguments"))
        script = payload.get("input") if isinstance(payload.get("input"), str) else None
        call = identifier(payload.get("call_id")) or identifier(payload.get("id"))
        state, detail = classify_tool(name, namespace if isinstance(namespace, str) else None, arguments, script)
        activity = None if state == CONTINUE_PREVIOUS else state
        if payload.get("turn_id") is not None and not self._results.is_current(payload.get("turn_id")):
            return []
        self._results.start(call)
        if name.lower() == "request_user_input_async" and isinstance(call, str):
            self._async_questions.add(call)
        out = [ev(Kind.activity_start, event_id=call if isinstance(call, str) else None,
                  activity=activity, tool=name, detail=detail,
                  question=tool_question(name, arguments))]
        todos = plan_items(arguments.get("plan") or arguments.get("items") or arguments.get("todos"))
        if todos:
            out.append(ev(Kind.todo_list, todos=todos))
        return out

    def _tool_end(self, payload: Dict[str, Any], ts, ev) -> List[PetEvent]:
        result = self._results.record(session=self.session, payload=payload, item=None,
                                      source_kind=payload.get("type", "tool_output"), timestamp=ts)
        self.last_tool_results = [result]
        if not result.projection_eligible:
            return []  # Missing IDs must never close the last unrelated tool.
        call = result.call_id
        if call in self._async_questions and as_dict(payload.get("output")).get("accepted") is True:
            return []
        self._async_questions.discard(call)
        return [ev(Kind.activity_failed if result.call_outcome == 'failed' else Kind.activity_end,
                   event_id=call)]

    def _user_message(self, text, ev):
        answered = question_reply_calls(text)
        if answered is not None:
            self._async_questions.difference_update(answered)
            return [ev(Kind.activity_end, event_id=call) for call in sorted(answered)]
        line = prompt_line(text)
        return self._close_async_questions(ev) + [ev(Kind.task_start, detail=line)] if line else []

    def _close_async_questions(self, ev):
        events = [ev(Kind.activity_end, event_id=call) for call in sorted(self._async_questions)]
        self._async_questions.clear()
        return events

    def _search_pair(self, item_id: Any, query: Any, ts: Optional[float], ev) -> List[PetEvent]:
        """网页搜索在记录里只有「搜完了」这一条，没有开始。发一对开始／结束，让她照样看一下网页。"""
        call = item_id if isinstance(item_id, str) and item_id else "search-%d" % int(ts or 0)
        detail = tr("Searching the web: %s", "搜索网页 %s") % query if isinstance(query, str) and query else None
        return [ev(Kind.activity_start, event_id=call, activity=PetState.read_web, tool="web_search", detail=detail),
                ev(Kind.activity_end, event_id=call)]
