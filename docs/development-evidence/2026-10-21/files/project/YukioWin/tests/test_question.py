"""抄题与在雪绪这边回答。移植自 YukioPlayer/Tests/YukioCoreTests/QuestionTests.swift。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.l10n import set_language  # noqa: E402
set_language("zh")   # 这些测试按中文文案断言


def setUpModule():
    set_language("zh")   # 前一个模块的应用测试可能把语言切回了英文

from yukio.answer import COPIED, TYPED, AnswerDelivery, Backend, SETTLE_MS, WAIT_FOR_FRONT_MS
from yukio.classify import describe, question as tool_question
from yukio.events import Kind, PetEvent, PetQuestion, PetState
from yukio.parsers_claude import ClaudeTranscriptParser
from yukio.question import QuestionCardLayout

from test_router import Harness

#: Claude Code 写进转录里的真实形状。
CLAUDE_INPUT = {
    "questions": [{
        "question": "发到 GitHub 的安装包要包含另一个会话没提交的改动吗？",
        "header": "发布范围",
        "multiSelect": False,
        "options": [
            {"label": "一起发（推荐）", "description": "分两次提交，合并进 main，发 v0.1.0"},
            {"label": "只发图标这版", "description": "从干净工作树重新打包"},
            {"label": "先别提交推送"},
        ],
    }],
}


class ParseTests(unittest.TestCase):
    def test_copies_question_header_and_options(self):
        q = PetQuestion.parse(CLAUDE_INPUT)
        self.assertEqual(q.text, "发到 GitHub 的安装包要包含另一个会话没提交的改动吗？")
        self.assertEqual(q.header, "发布范围")
        self.assertFalse(q.multi_select)
        self.assertEqual([o.label for o in q.options], ["一起发（推荐）", "只发图标这版", "先别提交推送"])
        self.assertEqual(q.options[0].detail, "分两次提交，合并进 main，发 v0.1.0")
        self.assertIsNone(q.options[2].detail)

    def test_copies_codex_shape_with_plain_string_options(self):
        q = PetQuestion.parse({"questions": [{"title": "先跑测试还是先打包？",
                                              "options": ["先跑测试", "先打包"], "multi_select": True}]})
        self.assertEqual(q.text, "先跑测试还是先打包？")
        self.assertTrue(q.multi_select)
        self.assertEqual([o.label for o in q.options], ["先跑测试", "先打包"])

    def test_copies_flat_shape(self):
        q = PetQuestion.parse({"prompt": "要我继续吗？"})
        self.assertEqual(q.text, "要我继续吗？")
        self.assertEqual(q.options, [])

    def test_ignores_tools_that_are_not_asking(self):
        self.assertIsNone(tool_question("bash", {"command": "echo question"}))
        self.assertIsNotNone(tool_question("AskUserQuestion", CLAUDE_INPUT))
        self.assertIsNotNone(tool_question("request_user_input", CLAUDE_INPUT))

    def test_short_label_prefers_the_header(self):
        self.assertEqual(PetQuestion.parse(CLAUDE_INPUT).short_label, "发布范围")
        self.assertEqual(len(PetQuestion("长" * 60).short_label), 41)   # 40 个字加一个省略号
        self.assertEqual(PetQuestion("第一行\n第二行").short_label, "第一行 第二行")

    def test_describe_uses_the_question(self):
        self.assertEqual(describe("AskUserQuestion", CLAUDE_INPUT), "发布范围")
        self.assertEqual(describe("AskUserQuestion", {}), "等你回答")

    def test_transcript_carries_the_question(self):
        obj = {
            "type": "assistant", "sessionId": "s", "timestamp": "2026-09-22T10:00:00.000Z",
            "message": {"stop_reason": "tool_use", "content": [
                {"type": "tool_use", "id": "t1", "name": "AskUserQuestion", "input": CLAUDE_INPUT}]},
        }
        events = ClaudeTranscriptParser().events(obj)
        start = [e for e in events if e.kind is Kind.activity_start][0]
        self.assertIs(start.activity, PetState.question_for_user)
        self.assertEqual(start.question.text, CLAUDE_INPUT["questions"][0]["question"])
        self.assertEqual(start.detail, "发布范围")


class RouterQuestionTests(unittest.TestCase):
    def test_hands_out_the_question_while_the_card_is_up(self):
        h = Harness()
        h.send(Kind.task_start)
        question = PetQuestion.parse(CLAUDE_INPUT)
        h.router.ingest(PetEvent(h.now, "test", h.session, Kind.activity_start, event_id="q",
                                 activity=PetState.question_for_user, tool="AskUserQuestion",
                                 detail=question.short_label, question=question), h.now)
        h.run(4000)
        self.assertIs(h.router.displayed, PetState.question_for_user)
        pending = h.router.asking_question
        self.assertEqual(pending.session, h.session)
        self.assertEqual(pending.call_id, "q")
        self.assertEqual(len(pending.question.options), 3)
        h.send(Kind.activity_end, id="q")
        h.send(Kind.thinking)
        h.run(8000)
        self.assertIsNone(h.router.asking_question)

    def test_no_question_text_means_no_card(self):
        """Deep Code 只报一个「等你回答」的状态，没有题目：身边不立卡。"""
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="q", activity=PetState.question_for_user, detail="等你批准")
        h.run(4000)
        self.assertEqual(h.router.asking_session, h.session)
        self.assertIsNone(h.router.asking_question)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.question = PetQuestion.parse(CLAUDE_INPUT)
        self.layout = QuestionCardLayout(self.question)

    def test_every_control_is_reachable_and_the_text_is_not(self):
        from yukio.question import probe_points
        hits = dict((name, self.layout.hit(x, y)) for name, (x, y) in probe_points(self.layout))
        self.assertEqual(hits["选项1"].kind, "option")
        self.assertEqual(hits["选项1"].index, 0)
        self.assertEqual(hits["选项3"].index, 2)
        self.assertEqual(hits["输入框"].kind, "input")
        self.assertEqual(hits["送出"].kind, "send")
        self.assertEqual(hits["打开聊天"].kind, "open_chat")
        self.assertEqual(hits["✕"].kind, "close")
        self.assertIsNone(hits["问题正文（不可点）"])
        self.assertIsNone(self.layout.hit(-5, -5))

    def test_long_question_is_wrapped_and_clipped(self):
        long = PetQuestion("这是一句很长的话。" * 40)
        layout = QuestionCardLayout(long)
        self.assertLessEqual(len(layout._question_lines), 6)
        self.assertTrue(layout._question_lines[-1].endswith("…"))

    def test_answered_card_drops_the_input_box(self):
        """答过之后那块地方是一行「已送出」：输入框和送出键都不在了，选项还能再点。"""
        layout = QuestionCardLayout(self.question, sent_notice="答案已送出")
        self.assertIsNone(layout.input_rect)
        kinds = set()
        for _, (x, y) in _every_point(layout):
            hit = layout.hit(x, y)
            if hit:
                kinds.add(hit.kind)
        self.assertNotIn("input", kinds)
        self.assertNotIn("send", kinds)
        self.assertIn("option", kinds)

    def test_card_is_pushed_to_the_left_when_the_right_edge_is_close(self):
        size = (280.0, 240.0)
        # 她靠着屏幕右边：卡片立到左边去。
        x, _ = QuestionCardLayout.origin(size, (1200, 500, 192, 208), (0, 0, 1440, 900))
        self.assertLess(x, 1200)
        # 中间：立在右边。
        x, _ = QuestionCardLayout.origin(size, (400, 500, 192, 208), (0, 0, 1440, 900))
        self.assertGreater(x, 400 + 192)


def _every_point(layout):
    """卡片上每隔几个点取一个，用来看有哪些东西还能点。"""
    w, h = layout.size_px
    return [("%d,%d" % (x, y), (x, y)) for y in range(2, h, 4) for x in range(2, w, 8)]


class FakeBackend:
    """假的按键后端：记下都送了什么，并让"谁在最前面"可以被测试摆布。"""

    def __init__(self, front=None):
        self.front = front
        self.typed = []
        self.returns = 0
        self.clipboard = None
        self.fail_typing = False

    def backend(self) -> Backend:
        return Backend(foreground_exe=lambda: self.front,
                       send_text=self._send_text,
                       send_return=self._send_return,
                       set_clipboard=self._clipboard)

    def _send_text(self, text):
        if self.fail_typing:
            return False
        self.typed.append(text)
        return True

    def _send_return(self):
        self.returns += 1
        return True

    def _clipboard(self, text):
        self.clipboard = text
        return True


class DeliveryTests(unittest.TestCase):
    def test_types_the_answer_once_the_app_is_in_front(self):
        fake = FakeBackend(front=None)
        delivery = AnswerDelivery(fake.backend())
        opened = []
        self.assertIsNone(delivery.start("一起发", "Claude.exe", lambda: opened.append(1), 0))
        self.assertEqual(opened, [1])
        self.assertEqual(fake.clipboard, "一起发")       # 先放一份进粘贴板当退路
        self.assertIsNone(delivery.tick(100))            # 还没到前面
        fake.front = "Claude.exe"
        self.assertIsNone(delivery.tick(200))            # 到了，等它站稳
        self.assertEqual(fake.typed, [])
        self.assertEqual(delivery.tick(200 + SETTLE_MS), TYPED)
        self.assertEqual(fake.typed, ["一起发"])
        self.assertEqual(fake.returns, 1)
        self.assertFalse(delivery.busy)

    def test_never_types_into_another_app(self):
        """等不到那个应用跑到前面：只留粘贴板，一个键都不按。"""
        fake = FakeBackend(front="explorer.exe")
        delivery = AnswerDelivery(fake.backend())
        delivery.start("一起发", "Claude.exe", lambda: None, 0)
        self.assertIsNone(delivery.tick(100))
        self.assertEqual(delivery.tick(WAIT_FOR_FRONT_MS + 1), COPIED)
        self.assertEqual(fake.typed, [])
        self.assertEqual(fake.returns, 0)
        self.assertEqual(fake.clipboard, "一起发")

    def test_switching_away_while_it_settles_stops_the_typing(self):
        fake = FakeBackend(front="Claude.exe")
        delivery = AnswerDelivery(fake.backend())
        delivery.start("一起发", "Claude.exe", lambda: None, 0)
        self.assertIsNone(delivery.tick(0))
        fake.front = "explorer.exe"                      # 这半秒里切走了
        self.assertEqual(delivery.tick(SETTLE_MS + 1), COPIED)
        self.assertEqual(fake.typed, [])

    def test_no_window_to_open_copies_only(self):
        """终端里跑的会话没有可跳的窗口：直接告诉你已复制。"""
        fake = FakeBackend()
        delivery = AnswerDelivery(fake.backend())
        self.assertEqual(delivery.start("继续", None, lambda: None, 0), COPIED)
        self.assertEqual(fake.clipboard, "继续")
        self.assertFalse(delivery.busy)

    def test_empty_answer_does_nothing(self):
        fake = FakeBackend()
        delivery = AnswerDelivery(fake.backend())
        self.assertIsNone(delivery.start("   ", "Claude.exe", lambda: None, 0))
        self.assertIsNone(fake.clipboard)


if __name__ == "__main__":
    unittest.main()
