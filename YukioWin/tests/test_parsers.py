"""解析器测试：Deep Code（DeepSeek）会话记录、Claude Code 转录、通用收件箱。

Deep Code 的样例按 @vegamo/deepcode-cli 0.4 实际写入的字段构造：
user/assistant/tool 三种消息、messageParams.tool_calls、tool_call_id、
工具结果 JSON 里的 ok/metadata.interrupted，以及 sessions-index.json 的条目。
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.bridge import BridgeParser
from yukio.events import Kind, PetState, TodoItem, TodoStatus
from yukio.parsers_claude import ClaudeTranscriptParser
from yukio.parsers_deepcode import (DeepCodeIndexParser, DeepCodeMessageParser,
                                    parse_plan, prompt_line)

TS = "2026-09-16T12:00:00.000Z"


def dc(obj):
    return DeepCodeMessageParser().events_from_line(json.dumps(obj).encode("utf-8"))


def message(role, **kw):
    base = {"id": "m1", "sessionId": "S1", "role": role, "content": "", "contentParams": None,
            "messageParams": None, "compacted": False, "visible": True,
            "createTime": TS, "updateTime": TS}
    base.update(kw)
    return base


def tool_call(id, name, arguments):
    return {"id": id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)}}


class DeepCodeMessageTests(unittest.TestCase):
    def test_user_prompt_starts_a_task(self):
        events = dc(message("user", content="  帮我修一下登录页\n细节如下",
                            meta={"userPrompt": {"text": "帮我修一下登录页"}}))
        self.assertEqual([e.kind for e in events], [Kind.task_start])
        self.assertEqual(events[0].detail, "帮我修一下登录页")
        self.assertEqual(events[0].session, "S1")

    def test_interrupt_message_is_not_a_new_task(self):
        events = dc(message("user", content="Interrupted. Killed processes: 4321."))
        self.assertEqual([e.kind for e in events], [Kind.task_abort])

    def test_answering_a_question_continues_the_task(self):
        events = dc(message("user", content="选第二个", meta={"isAnswers": True}))
        self.assertEqual([e.kind for e in events], [Kind.thinking])

    def test_tool_calls_become_activities(self):
        events = dc(message("assistant", content="", messageParams={
            "tool_calls": [tool_call("c1", "edit", {"file_path": "C:\\proj\\login.py",
                                                    "old_string": "a", "new_string": "b"})]}))
        self.assertEqual([e.kind for e in events], [Kind.activity_start])
        self.assertEqual(events[0].activity, PetState.write_file)
        self.assertEqual(events[0].detail, "编辑 login.py")
        self.assertEqual(events[0].event_id, "c1")

    def test_read_bash_and_websearch_map_to_poses(self):
        cases = [
            ("read", {"file_path": "/a/README.md"}, PetState.read_file, "阅读 README.md"),
            ("ReadImage", {"file_path": "/a/shot.png"}, PetState.view_image, "查看 shot.png"),
            ("bash", {"command": "pytest -q"}, PetState.verify, "$ pytest -q"),
            ("bash", {"command": "rg TODO src/"}, PetState.read_file, "$ rg TODO src/"),
            ("WebSearch", {"query": "deepseek api"}, PetState.read_web, "搜索网页 deepseek api"),
            ("AskUserQuestion", {"questions": [{"question": "用哪个方案？"}]},
             PetState.question_for_user, "等你回答"),
            ("write", {"file_path": "a/b/notes.md"}, PetState.write_file, "写入 notes.md"),
        ]
        for name, args, state, detail in cases:
            events = dc(message("assistant", messageParams={"tool_calls": [tool_call("c", name, args)]}))
            self.assertEqual(events[0].activity, state, name)
            self.assertEqual(events[0].detail, detail, name)

    def test_reasoning_content_counts_as_thinking(self):
        events = dc(message("assistant", content="", messageParams={"reasoning_content": "先看看校验函数"}))
        self.assertEqual([e.kind for e in events], [Kind.thinking])

    def test_plain_assistant_text_ends_the_task(self):
        events = dc(message("assistant", content="改好了，测试也过了。"))
        self.assertEqual([e.kind for e in events], [Kind.final_answer, Kind.task_end])

    def test_narration_before_tool_calls_is_not_the_final_answer(self):
        events = dc(message("assistant", content="我先看一下这个文件。", messageParams={
            "tool_calls": [tool_call("c1", "read", {"file_path": "a.py"})]}))
        self.assertEqual([e.kind for e in events], [Kind.activity_start, Kind.thinking])

    def test_update_plan_becomes_a_todo_list(self):
        plan = "- [x] 读代码\n- [>] 改代码\n- [ ] 跑测试"
        events = dc(message("assistant", messageParams={
            "tool_calls": [tool_call("c1", "UpdatePlan", {"plan": plan})]}))
        self.assertEqual([e.kind for e in events], [Kind.activity_start, Kind.todo_list])
        self.assertEqual(events[0].activity, PetState.thinking)
        self.assertEqual(events[1].todos, [TodoItem("0", "读代码", TodoStatus.completed),
                                           TodoItem("1", "改代码", TodoStatus.in_progress),
                                           TodoItem("2", "跑测试", TodoStatus.pending)])

    def test_tool_result_ends_the_activity(self):
        ok = json.dumps({"ok": True, "name": "read", "output": "…"}, indent=2)
        events = dc(message("tool", content=ok, messageParams={"tool_call_id": "c1"},
                            meta={"function": {"name": "read"}}))
        self.assertEqual([e.kind for e in events], [Kind.activity_end])
        self.assertEqual(events[0].event_id, "c1")
        self.assertEqual(events[0].tool, "read")

    def test_failed_tool_result_makes_her_dejected(self):
        bad = json.dumps({"ok": False, "name": "bash", "error": "exit code 1"}, indent=2)
        events = dc(message("tool", content=bad, messageParams={"tool_call_id": "c2"}))
        self.assertEqual([e.kind for e in events], [Kind.activity_failed])

    def test_interrupted_or_denied_tool_is_not_a_failure(self):
        for content in (json.dumps({"ok": False, "name": "bash", "error": "stopped",
                                    "metadata": {"interrupted": True}}),
                        json.dumps({"ok": False, "name": "write", "error": "Permission denied by user"})):
            events = dc(message("tool", content=content, messageParams={"tool_call_id": "c3"}))
            self.assertEqual([e.kind for e in events], [Kind.activity_end], content)

    def test_compacted_history_is_ignored(self):
        self.assertEqual(dc(message("user", content="旧的请求", compacted=True)), [])

    def test_system_messages_are_ignored(self):
        self.assertEqual(dc(message("system", content="skill catalog", visible=False)), [])

    def test_plan_markdown_variants(self):
        items = parse_plan("1. [ ] 一\n* [>] 二\n  - [x] 三\n普通文字\n- [X] 四")
        self.assertEqual([i.subject for i in items], ["一", "二", "三", "四"])
        self.assertEqual([i.status for i in items],
                         [TodoStatus.pending, TodoStatus.in_progress,
                          TodoStatus.completed, TodoStatus.completed])

    def test_prompt_line_skips_tag_lines(self):
        self.assertEqual(prompt_line("<context>x</context>\n真正的请求"), "真正的请求")
        self.assertIsNone(prompt_line(""))


class DeepCodeIndexTests(unittest.TestCase):
    def entry(self, **kw):
        base = {"id": "S1", "summary": "修复登录页", "status": "processing",
                "createTime": TS, "updateTime": TS}
        base.update(kw)
        return base

    def test_title_then_status_changes(self):
        p = DeepCodeIndexParser()
        events = p.events(self.entry(), now=0)
        self.assertEqual([e.kind for e in events], [Kind.session_title])
        self.assertEqual(events[0].detail, "修复登录页")
        # 同样的条目不会重复产生事件。
        self.assertEqual(p.events(self.entry(), now=0), [])

    def test_ask_permission_raises_the_question_card_until_it_clears(self):
        p = DeepCodeIndexParser()
        p.events(self.entry(), now=0)
        waiting = p.events(self.entry(status="ask_permission"), now=1000)
        self.assertEqual([e.kind for e in waiting], [Kind.activity_start])
        self.assertEqual(waiting[0].activity, PetState.question_for_user)
        self.assertEqual(waiting[0].detail, "等你批准")
        back = p.events(self.entry(status="processing"), now=2000)
        self.assertEqual([e.kind for e in back], [Kind.activity_end, Kind.thinking])
        self.assertEqual(back[0].event_id, waiting[0].event_id)

    def test_interrupted_and_failed(self):
        p = DeepCodeIndexParser()
        p.events(self.entry(), now=0)
        self.assertEqual([e.kind for e in p.events(self.entry(status="interrupted"), now=1)],
                         [Kind.task_abort])
        p2 = DeepCodeIndexParser()
        p2.events(self.entry(), now=0)
        self.assertEqual([e.kind for e in p2.events(self.entry(status="failed"), now=1)],
                         [Kind.task_failed])
        p3 = DeepCodeIndexParser()
        p3.events(self.entry(), now=0)
        # 拒绝授权不算失败。
        self.assertEqual([e.kind for e in p3.events(self.entry(status="permission_denied"), now=1)],
                         [Kind.task_abort])


class ClaudeTranscriptTests(unittest.TestCase):
    def setUp(self):
        self.p = ClaudeTranscriptParser()

    def line(self, text):
        return self.p.events_from_line(text.encode("utf-8"))

    head = '"sessionId":"S1","timestamp":"2026-09-13T12:00:00.000Z"'

    def test_session_titles_and_prompt_line(self):
        t = self.line('{"type":"custom-title","customTitle":"桌宠缺失状态","sessionId":"S1"}')
        self.assertEqual([e.kind for e in t], [Kind.session_title])
        self.assertEqual(t[0].detail, "桌宠缺失状态")
        start = self.line('{"type":"user",%s,"message":{"role":"user","content":"  帮我修一下登录页\\n细节"}}' % self.head)
        self.assertEqual([e.kind for e in start], [Kind.task_start])
        self.assertEqual(start[0].detail, "帮我修一下登录页")

    def test_tool_use_and_todo_write(self):
        edit = self.line('{"type":"assistant",%s,"message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"tu_1","name":"Edit","input":{"file_path":"/a/Catalog.swift"}}]}}' % self.head)
        self.assertEqual(edit[0].detail, "编辑 Catalog.swift")
        todo = self.line('{"type":"assistant",%s,"message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"tu_4","name":"TodoWrite","input":{"todos":[{"content":"读代码","status":"completed"},{"content":"改代码","status":"in_progress"}]}}]}}' % self.head)
        self.assertEqual([e.kind for e in todo], [Kind.activity_start, Kind.todo_list])
        self.assertEqual(todo[1].todos, [TodoItem("0", "读代码", TodoStatus.completed),
                                         TodoItem("1", "改代码", TodoStatus.in_progress)])

    def test_tool_result_failure_and_refusal(self):
        fail = self.line('{"type":"user",%s,"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_1","is_error":true,"content":"exit 1"}]}}' % self.head)
        self.assertEqual([e.kind for e in fail], [Kind.activity_failed])
        deny = self.line('{"type":"user",%s,"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_1","is_error":true,"content":"The user doesn\'t want to proceed"}]}}' % self.head)
        self.assertEqual([e.kind for e in deny], [Kind.activity_end])

    def test_final_answer_and_api_error(self):
        answer = self.line('{"type":"assistant",%s,"message":{"stop_reason":"end_turn","content":[{"type":"text","text":"好了"}]}}' % self.head)
        self.assertEqual([e.kind for e in answer], [Kind.final_answer, Kind.task_end])
        err = self.line('{"type":"assistant",%s,"isApiErrorMessage":true,"message":{"model":"<synthetic>","content":[]}}' % self.head)
        self.assertEqual([e.kind for e in err], [Kind.task_failed])

    def test_sidechain_is_ignored(self):
        self.assertEqual(self.line('{"type":"user","isSidechain":true,%s,"message":{"role":"user","content":"x"}}' % self.head), [])


class BridgeTests(unittest.TestCase):
    def parse(self, obj, now=1000.0):
        return BridgeParser().events_from_line(json.dumps(obj).encode("utf-8"), fallback_ts=now)

    def test_minimal_event(self):
        events = self.parse({"kind": "task_start", "detail": "重构登录页"})
        self.assertEqual([e.kind for e in events], [Kind.task_start])
        self.assertEqual(events[0].session, "bridge")
        self.assertEqual(events[0].ts, 1000.0)

    def test_tool_is_classified_when_activity_is_missing(self):
        events = self.parse({"kind": "activity_start", "id": "t1", "tool": "edit",
                             "input": {"file_path": "a/b.py"}})
        self.assertEqual(events[0].activity, PetState.write_file)
        self.assertEqual(events[0].detail, "编辑 b.py")

    def test_explicit_activity_and_iso_timestamp(self):
        events = self.parse({"kind": "activity_start", "activity": "verify",
                             "ts": "2026-09-16T12:00:00.000Z", "detail": "跑测试"})
        self.assertEqual(events[0].activity, PetState.verify)
        self.assertEqual(events[0].ts, 1789560000000.0)  # 2026-09-16T12:00:00Z

    def test_unknown_kind_is_dropped(self):
        self.assertEqual(self.parse({"kind": "dance"}), [])


if __name__ == "__main__":
    unittest.main()
