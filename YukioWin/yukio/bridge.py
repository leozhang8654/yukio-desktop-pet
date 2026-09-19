"""通用事件收件箱：任何工具都能用一行 JSON 驱动雪绪。

用途：
  * Deep Code 的 `notify` 脚本（每轮结束时执行）——见 scripts/yukio-notify.py；
  * 别的 DeepSeek 客户端、编辑器插件、自己的脚本；
  * Deep Code 换了会话记录格式时的保底通道。

用法：往收件箱文件里追加 JSON（一行一个，也可以多行拼接）：

    {"kind": "task_start", "session": "build", "detail": "重构登录页"}
    {"kind": "activity_start", "id": "t1", "tool": "edit", "input": {"file_path": "a.py"}}
    {"kind": "activity_end", "id": "t1"}
    {"kind": "final_answer"} {"kind": "task_end"}

字段：
  kind      必填，见 events.Kind（task_start/task_end/task_abort/task_failed/
            activity_start/activity_end/activity_failed/thinking/final_answer/
            session_title/todo_list/todo_update）
  session   可选，默认 "bridge"；用来区分同时进行的多个会话
  id        可选，工具调用 ID，用来配对开始与结束
  activity  可选，直接指定动作（thinking/read_file/view_image/write_file/verify/
            read_web/respond/default_work/question_for_user…）
  tool+input 可选，交给内置分类规则决定动作与气泡文字
  detail    可选，气泡里那句话
  ts        可选，毫秒时间戳；不填用收到的时间
  todos     可选，[{"id","subject","status"}]，status 为 pending/in_progress/completed/deleted
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .classify import CONTINUE_PREVIOUS, classify, describe
from .events import Kind, PetEvent, PetState, TodoItem, TodoStatus, parse_timestamp

SOURCE = "bridge"


class BridgeParser:
    source = SOURCE

    def events_from_line(self, data: bytes, fallback_session: str = "",
                         fallback_ts: float = 0.0) -> List[PetEvent]:
        try:
            obj = json.loads(data.decode("utf-8", "replace"))
        except ValueError:
            return []
        return self.events(obj, fallback_ts) if isinstance(obj, dict) else []

    def events(self, obj: Dict[str, Any], received_at: float) -> List[PetEvent]:
        raw_kind = obj.get("kind") or obj.get("event")
        if not isinstance(raw_kind, str):
            return []
        try:
            kind = Kind(raw_kind)
        except ValueError:
            return []
        session = obj.get("session")
        session = session if isinstance(session, str) and session else "bridge"
        ts = obj.get("ts")
        if isinstance(ts, str):
            ts = parse_timestamp(ts)
        if not isinstance(ts, (int, float)) or isinstance(ts, bool):
            ts = received_at

        tool = obj.get("tool") if isinstance(obj.get("tool"), str) else None
        input = obj.get("input") if isinstance(obj.get("input"), dict) else {}
        activity: Optional[PetState] = None
        raw_activity = obj.get("activity")
        if isinstance(raw_activity, str):
            try:
                activity = PetState(raw_activity)
            except ValueError:
                activity = None
        elif tool and kind is Kind.activity_start:
            guess = classify(tool, input)
            activity = None if guess == CONTINUE_PREVIOUS else guess

        detail = obj.get("detail")
        if not isinstance(detail, str) or not detail.strip():
            detail = describe(tool, input) if tool else None
        else:
            detail = detail.strip()[:120]

        todos = None
        raw_todos = obj.get("todos")
        if isinstance(raw_todos, list):
            todos = []
            for i, t in enumerate(raw_todos):
                if not isinstance(t, dict):
                    continue
                status = t.get("status")
                try:
                    parsed = TodoStatus(status) if isinstance(status, str) else None
                except ValueError:
                    parsed = None
                subject = t.get("subject") if isinstance(t.get("subject"), str) else t.get("content")
                todos.append(TodoItem(str(t.get("id", i)),
                                      subject if isinstance(subject, str) else None, parsed))

        event_id = obj.get("id")
        return [PetEvent(float(ts), SOURCE, session, kind,
                         event_id=event_id if isinstance(event_id, str) else None,
                         activity=activity, tool=tool, detail=detail, todos=todos)]
