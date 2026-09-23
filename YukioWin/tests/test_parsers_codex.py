"""GPT（Codex）的记录 → 事件，以及那棵按日期分层的会话目录怎么扫。

样例按本机真实 rollout 的形状写（字段裁短，不含对话内容）。断言与 macOS 版
YukioPlayer/Tests/YukioCoreTests/CodexParserTests.swift 一一对应。
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.l10n import set_language  # noqa: E402
set_language("zh")   # 这些测试按中文文案断言


def setUpModule():
    set_language("zh")   # 前一个模块的应用测试可能把语言切回了英文


from yukio.events import Kind, PetState, TodoStatus  # noqa: E402
from yukio.parsers_codex import CodexRolloutParser, session_id_from_file_name  # noqa: E402
from yukio.sources import CodexSessionsSource  # noqa: E402

SESSION = "01a0cbf7-b0eb-7ab1-8854-5fd2a4b1cb49"


def ts(offset_seconds: float = 0.0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + offset_seconds)) + ".000Z"


def line(payload, stamp=None):
    return json.dumps({"timestamp": stamp or ts(), "type": "response_item", "payload": payload}).encode()


def event_line(payload, stamp=None):
    return json.dumps({"timestamp": stamp or ts(), "type": "event_msg", "payload": payload}).encode()


class CodexParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = CodexRolloutParser(SESSION)

    def kinds(self, events):
        return [e.kind for e in events]

    def test_session_id_comes_from_the_file_name_then_from_session_meta(self):
        self.assertEqual(session_id_from_file_name("rollout-2026-09-22T18-53-22-%s.jsonl" % SESSION), SESSION)
        # 分支出来的记录名里有两个 ID，取后面那个（新的那条）。
        self.assertEqual(session_id_from_file_name(
            "rollout-2026-09-22T19-10-20-01a0c702-e876-7f71-a663-420d6fd3e7d7_%s.jsonl" % SESSION), SESSION)
        # 认不出来时原样用文件名，至少还能把同一个文件的事件归到一起。
        self.assertEqual(session_id_from_file_name("weird-name.jsonl"), "weird-name")

        parser = CodexRolloutParser("from-file-name")
        parser.events_from_line(json.dumps({
            "timestamp": ts(), "type": "session_meta",
            "payload": {"session_id": SESSION, "cwd": "/tmp", "originator": "Codex Desktop"}}).encode())
        self.assertEqual(parser.session, SESSION)

    def test_user_message_starts_the_task_and_boilerplate_does_not(self):
        # 塞给模型的环境说明（整条以 < 开头）不是人说的话。
        self.assertEqual(self.parser.events_from_line(line(
            {"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": "<app-context>\n# Codex desktop context"}]})), [])
        self.assertEqual(self.parser.events_from_line(line(
            {"type": "message", "role": "developer",
             "content": [{"type": "input_text", "text": "You are Codex"}]})), [])

        events = self.parser.events_from_line(line(
            {"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": "把动画改顺一点\n第二行"}]}))
        self.assertEqual(self.kinds(events), [Kind.task_start])
        self.assertEqual(events[0].detail, "把动画改顺一点")
        self.assertEqual(events[0].source, "codex")
        self.assertEqual(events[0].session, SESSION)

        # 界面那一份也写了同一条消息；路由器按 duplicate_task_start_ms 去重，这里只看认得出来。
        events = self.parser.events_from_line(event_line(
            {"type": "item_completed", "thread_id": SESSION,
             "item": {"type": "UserMessage", "content": [{"type": "text", "text": "把动画改顺一点"}]}}))
        self.assertEqual(self.kinds(events), [Kind.task_start])

    def test_turn_ends_with_final_answer_then_task_end(self):
        done = self.parser.events_from_line(event_line({"type": "task_complete", "last_agent_message": "做完了"}))
        self.assertEqual(self.kinds(done), [Kind.final_answer, Kind.task_end])
        # 没有回答的一轮（被压缩、被接管）只算结束，不走递交报告。
        quiet = self.parser.events_from_line(event_line({"type": "task_complete", "last_agent_message": ""}))
        self.assertEqual(self.kinds(quiet), [Kind.task_end])
        # 用户按停不算失败。
        stopped = self.parser.events_from_line(event_line({"type": "turn_aborted", "reason": "interrupted"}))
        self.assertEqual(self.kinds(stopped), [Kind.task_abort])
        broke = self.parser.events_from_line(event_line({"type": "error", "message": "stream error"}))
        self.assertEqual(self.kinds(broke), [Kind.task_failed])

    def start_exec(self, script):
        events = self.parser.events_from_line(line(
            {"type": "custom_tool_call", "name": "exec", "call_id": "call_1", "input": script}))
        return events[0]

    def test_exec_script_says_what_it_is_doing(self):
        read = self.start_exec('const r = await tools.exec_command({cmd:"sed -n \'1,240p\' main.swift","workdir":"/tmp"});text(r.output)')
        self.assertEqual(read.activity, PetState.read_file)
        self.assertEqual(read.detail, "$ sed -n 1,240p")

        test = self.start_exec('const r = await tools.exec_command({cmd:"cd app && swift test"});')
        self.assertEqual(test.activity, PetState.verify)

        patch = self.start_exec('text(await tools.apply_patch("*** Begin Patch\n*** Update File: /tmp/main.swift\n"))')
        self.assertEqual(patch.activity, PetState.write_file)
        self.assertEqual(patch.detail, "编辑 main.swift")

        image = self.start_exec('image((await tools.view_image({path:"/tmp/shot.png"})).content)')
        self.assertEqual(image.activity, PetState.view_image)
        self.assertEqual(image.detail, "查看 shot.png")

        # 等一条还在跑的命令：延续上一个动作（activity 为 None）。
        wait = self.start_exec('text(await tools.write_stdin({session_id:"2",chars:"y\\n"}))')
        self.assertIsNone(wait.activity)

    def test_tool_calls_pair_up_and_failures_make_her_sad(self):
        start = self.parser.events_from_line(line(
            {"type": "custom_tool_call", "name": "exec", "call_id": "call_1",
             "input": 'await tools.exec_command({cmd:"rg TODO"})'}))
        self.assertEqual(self.kinds(start), [Kind.activity_start])
        self.assertEqual(start[0].event_id, "call_1")

        # 界面那一份先写「这条命令失败了」，紧接着才是输出。
        item = self.parser.events_from_line(event_line(
            {"type": "item_completed", "item": {"type": "CommandExecution", "status": "failed", "exit_code": 1}}))
        self.assertEqual(item, [])
        end = self.parser.events_from_line(line(
            {"type": "custom_tool_call_output", "call_id": "call_1",
             "output": [{"type": "input_text", "text": "no matches"}]}))
        self.assertEqual(self.kinds(end), [Kind.activity_failed])
        self.assertEqual(end[0].event_id, "call_1")

        # 下一次成功的调用不该还带着上一次的失败。
        self.parser.events_from_line(line(
            {"type": "custom_tool_call", "name": "exec", "call_id": "call_2",
             "input": 'await tools.exec_command({cmd:"rg TODO"})'}))
        ok = self.parser.events_from_line(line(
            {"type": "custom_tool_call_output", "call_id": "call_2",
             "output": [{"type": "input_text", "text": "ok"}]}))
        self.assertEqual(self.kinds(ok), [Kind.activity_end])

    def test_classic_cli_tools_are_understood(self):
        shell = self.parser.events_from_line(line(
            {"type": "function_call", "name": "shell", "call_id": "c1",
             "arguments": json.dumps({"command": ["bash", "-lc", "cat README.md"]})}))[0]
        self.assertEqual(shell.activity, PetState.read_file)

        ask = self.parser.events_from_line(line(
            {"type": "function_call", "name": "request_user_input_async", "call_id": "c2",
             "arguments": json.dumps({"questions": [{"title": "要哪一种？"}]})}))[0]
        self.assertEqual(ask.activity, PetState.question_for_user)
        self.assertEqual(ask.detail, "要哪一种？")

        search = self.parser.events_from_line(line(
            {"type": "function_call", "name": "web_search", "call_id": "c3",
             "arguments": json.dumps({"query": "swift testing"})}))[0]
        self.assertEqual(search.activity, PetState.read_web)

        # 老版把退出码写在输出里。
        failed = self.parser.events_from_line(line(
            {"type": "function_call_output", "call_id": "c1",
             "output": json.dumps({"output": "boom", "metadata": {"exit_code": 2}})}))
        self.assertEqual(self.kinds(failed), [Kind.activity_failed])

    def test_plan_updates_become_the_task_list(self):
        events = self.parser.events_from_line(line(
            {"type": "function_call", "name": "update_plan", "call_id": "c9",
             "arguments": json.dumps({"plan": [{"step": "读代码", "status": "completed"},
                                               {"step": "改动画", "status": "in_progress"}]})}))
        self.assertEqual(self.kinds(events), [Kind.activity_start, Kind.todo_list])
        self.assertEqual(events[0].activity, PetState.thinking)
        self.assertEqual([t.subject for t in events[1].todos], ["读代码", "改动画"])
        self.assertEqual([t.status for t in events[1].todos], [TodoStatus.completed, TodoStatus.in_progress])

    def test_web_search_items_show_up_as_browsing(self):
        events = self.parser.events_from_line(event_line(
            {"type": "item_completed", "item": {"type": "WebSearch", "id": "ws-1", "query": "blender 5 release"}}))
        self.assertEqual(self.kinds(events), [Kind.activity_start, Kind.activity_end])
        self.assertEqual(events[0].activity, PetState.read_web)
        self.assertEqual(events[0].detail, "搜索网页 blender 5 release")


class CodexSourceTests(unittest.TestCase):
    """按 Codex 真实的目录结构造一份会话：<sessions>/<年>/<月>/<日>/rollout-….jsonl"""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="yukio-codex-")
        self.day = os.path.join(self.root, "sessions", "2026", "09", "22")
        os.makedirs(self.day)
        self.path = os.path.join(self.day, "rollout-2026-09-22T18-53-22-%s.jsonl" % SESSION)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def append(self, data: bytes):
        with open(self.path, "ab") as fh:
            fh.write(data + b"\n")

    def test_sessions_are_found_under_the_date_folders_and_only_new_lines_are_read(self):
        self.append(line({"type": "message", "role": "user",
                          "content": [{"type": "input_text", "text": "改动画"}]}, stamp=ts(-5)))
        source = CodexSessionsSource(os.path.join(self.root, "sessions"))
        now = time.time() * 1000.0
        first = source.poll(now)
        self.assertTrue(source.status.directory_found)
        self.assertEqual(source.status.tracked_files, 1)
        self.assertEqual([e.kind for e in first], [Kind.task_start])
        self.assertEqual(first[0].session, SESSION)

        self.append(line({"type": "custom_tool_call", "name": "exec", "call_id": "c1",
                          "input": 'await tools.exec_command({cmd:"cat a.txt"})'}))
        more = source.poll(now + 1)
        self.assertEqual([e.kind for e in more], [Kind.activity_start])
        self.assertEqual(more[0].activity, PetState.read_file)
        self.assertEqual(source.poll(now + 2), [])


if __name__ == "__main__":
    unittest.main()
