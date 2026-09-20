"""来源测试：按 Deep Code 真实的目录结构造一份会话，验证跟随、增量读取与索引状态。

    <projects>/<项目码>/sessions-index.json
    <projects>/<项目码>/<会话 ID>.jsonl
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

from yukio.events import Kind, PetState
from yukio.router import ActivityRouter
from yukio.sources import BridgeInboxSource, ClaudeTranscriptSource, DeepCodeSource

SESSION = "3f2b1c44-0000-4000-8000-000000000001"


def ts(offset_seconds: float = 0.0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + offset_seconds)) + ".000Z"


def message(role, **kw):
    base = {"id": "m", "sessionId": SESSION, "role": role, "content": "", "contentParams": None,
            "messageParams": None, "compacted": False, "visible": True,
            "createTime": ts(), "updateTime": ts()}
    base.update(kw)
    return base


class DeepCodeSourceTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="yukio-deepcode-")
        self.projects = os.path.join(self.root, "projects")
        self.project = os.path.join(self.projects, "C--Users-leo-proj")
        os.makedirs(self.project)
        self.messages = os.path.join(self.project, SESSION + ".jsonl")
        self.index = os.path.join(self.project, "sessions-index.json")
        self.write_index("processing")
        open(self.messages, "w").close()
        self.source = DeepCodeSource(self.projects)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_index(self, status, summary="修复登录页"):
        payload = {"entries": [{"id": SESSION, "summary": summary, "assistantReply": None,
                                "status": status, "failReason": None, "createTime": ts(-60),
                                "updateTime": ts(), "processes": None}],
                   "originalPath": "C:\\Users\\leo\\proj"}
        with open(self.index, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        # 索引靠 mtime 判断有没有变，测试里连续写两次要保证时间戳不同。
        stamp = time.time() + self._bump()
        os.utime(self.index, (stamp, stamp))

    _bumps = [0]

    def _bump(self):
        self._bumps[0] += 1
        return self._bumps[0]

    def append(self, obj):
        with open(self.messages, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def poll(self):
        return self.source.poll(time.time() * 1000.0)

    def test_follows_a_whole_turn(self):
        self.assertTrue(self.source.available)
        self.poll()  # 建立跟踪，读到标题
        self.append(message("user", content="帮我修一下登录页", meta={"userPrompt": {"text": "x"}}))
        events = self.poll()
        self.assertEqual([e.kind for e in events], [Kind.task_start])
        self.assertEqual(events[0].session, SESSION)

        self.append(message("assistant", messageParams={"tool_calls": [
            {"id": "call_1", "type": "function",
             "function": {"name": "read", "arguments": json.dumps({"file_path": "C:/proj/login.py"})}}]}))
        events = self.poll()
        self.assertEqual(events[0].activity, PetState.read_file)
        self.assertEqual(events[0].detail, "阅读 login.py")

        self.append(message("tool", content=json.dumps({"ok": True, "name": "read", "output": "…"}),
                            messageParams={"tool_call_id": "call_1"}))
        events = self.poll()
        self.assertEqual([e.kind for e in events], [Kind.activity_end])

        self.append(message("assistant", content="改好了。"))
        events = self.poll()
        self.assertEqual([e.kind for e in events], [Kind.final_answer, Kind.task_end])

    def test_index_title_and_waiting_state(self):
        events = self.poll()
        self.assertEqual([e.kind for e in events], [Kind.session_title])
        self.assertEqual(events[0].detail, "修复登录页")
        self.write_index("ask_permission")
        events = self.poll()
        self.assertEqual([e.kind for e in events], [Kind.activity_start])
        self.assertEqual(events[0].activity, PetState.question_for_user)

    def test_only_new_lines_are_read(self):
        self.append(message("user", content="第一次请求"))
        self.poll()
        self.assertEqual(self.poll(), [])
        self.append(message("user", content="第二次请求"))
        events = self.poll()
        self.assertEqual([e.detail for e in events], ["第二次请求"])

    def test_half_written_line_waits_for_the_rest(self):
        self.poll()  # 先吃掉索引里的标题
        with open(self.messages, "a", encoding="utf-8") as fh:
            fh.write('{"id":"m","sessionId":"%s","role":"user","content":"半行' % SESSION)
        self.assertEqual(self.poll(), [])
        with open(self.messages, "a", encoding="utf-8") as fh:
            fh.write('请求","createTime":"%s"}\n' % ts())
        events = self.poll()
        self.assertEqual([e.kind for e in events], [Kind.task_start])
        self.assertEqual(events[0].detail, "半行请求")

    def test_deleted_session_file_aborts(self):
        self.append(message("user", content="请求"))
        self.poll()
        os.remove(self.messages)
        events = self.poll()
        self.assertEqual([e.kind for e in events], [Kind.task_abort])

    def test_drives_the_router_end_to_end(self):
        router = ActivityRouter(now=time.time() * 1000.0)
        self.append(message("user", content="帮我改一下"))
        self.append(message("assistant", messageParams={"tool_calls": [
            {"id": "c1", "type": "function",
             "function": {"name": "edit", "arguments": json.dumps({"file_path": "a.py"})}}]}))
        now = time.time() * 1000.0
        for e in self.poll():
            router.ingest(e, now)
        router.settle(now)
        self.assertEqual(router.displayed, PetState.write_file)
        line = router.status_line(now)
        self.assertEqual(line.current, "编辑 a.py")
        self.assertEqual(line.title, "修复登录页")


class BridgeInboxTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="yukio-bridge-")
        self.path = os.path.join(self.dir, "inbox.jsonl")
        open(self.path, "w").close()
        self.source = BridgeInboxSource(self.path)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_reads_appended_events_only(self):
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write('{"kind":"task_start","session":"x","detail":"旧的"}\n')
        self.assertEqual(self.source.poll(1000.0), [])   # 第一次只记住文件末尾
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write('{"kind":"activity_start","id":"t","tool":"bash","input":{"command":"pytest"}}\n')
        events = self.source.poll(2000.0)
        self.assertEqual([e.kind for e in events], [Kind.activity_start])
        self.assertEqual(events[0].activity, PetState.verify)


class ClaudeSourceTests(unittest.TestCase):
    def test_missing_directory_is_harmless(self):
        source = ClaudeTranscriptSource(os.path.join(tempfile.gettempdir(), "yukio-no-such-dir"))
        self.assertFalse(source.available)
        self.assertEqual(source.poll(time.time() * 1000.0), [])


if __name__ == "__main__":
    unittest.main()
