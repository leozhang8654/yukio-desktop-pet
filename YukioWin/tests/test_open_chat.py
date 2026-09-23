"""那条聊天已经开在眼前时就不举牌。移植自 YukioPlayer/Tests/YukioCoreTests/OpenChatTests.swift。

举牌是为了"这条答完了，点我跳过去看"。那条聊天要是本来就开在眼前，人已经看见了，
再举一块牌只是挡路。举牌有两条路——当前跟着的那条走 _desired，别的聊天走
_arm_pending_signs——两条都要盖住，否则那条会从身侧的卡叠里冒出来。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.l10n import set_language  # noqa: E402
set_language("zh")   # 这些测试按中文文案断言


def setUpModule():
    set_language("zh")   # 前一个模块的应用测试可能把语言切回了英文

from yukio.chatlinks import number_of, value_of
from yukio.events import Kind, PetState
from yukio.router import RouterConfig

from test_router import Harness


def _config():
    cfg = RouterConfig()
    cfg.complete_arm_ms = 8000
    cfg.respond_hold_ms = 3000
    return cfg


class OpenChatTests(unittest.TestCase):
    def test_no_card_when_that_chat_is_already_in_sight(self):
        """答完时那条聊天正开在眼前：不举牌。"""
        h = Harness(config=_config())
        h.router.open_chat_session = h.session
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(60000)
        self.assertNotIn(PetState.task_complete, h.states)
        self.assertIsNone(h.router.completed_session)

    def test_card_still_goes_up_when_not_in_sight(self):
        """对照：同样的时序，人没开着那条聊天时照常举牌。"""
        h = Harness(config=_config())
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(60000)
        self.assertIn(PetState.task_complete, h.states)
        self.assertEqual(h.router.completed_session, h.session)

    def test_another_chat_in_sight_does_not_suppress_this_one(self):
        """开着的是另一条聊天：这条还是要举牌。"""
        h = Harness(config=_config())
        h.router.open_chat_session = "别的聊天"
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(60000)
        self.assertIn(PetState.task_complete, h.states)

    def test_raised_card_goes_down_when_you_open_that_chat_yourself(self):
        """牌子已经举着，人自己切到那条聊天：牌子就此放下，不用再点她一下。"""
        h = Harness(config=_config())
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(20000)
        self.assertEqual(h.router.displayed, PetState.task_complete)

        h.router.open_chat_session = h.session
        h.run(h.now + 2000)
        self.assertEqual(h.router.displayed, PetState.idle)
        self.assertIsNone(h.router.completed_session)
        # 切走也不会自己举回来：这一轮已经算看过了。
        h.router.open_chat_session = None
        h.run(h.now + 20000)
        self.assertEqual(h.router.displayed, PetState.idle)

    def test_a_chat_in_sight_is_not_armed_even_while_she_follows_another(self):
        """她正跟着 s1，s2 在背后答完了而 s2 正开在眼前：s2 不该进卡叠。"""
        h = Harness(config=_config())
        h.router.open_chat_session = "s2"
        h.send(Kind.task_start, session="s1")
        h.send(Kind.task_start, session="s2")
        h.run(1000)
        h.send(Kind.final_answer, session="s2")
        h.send(Kind.task_end, session="s2")
        h.run(20000)
        self.assertIsNone(h.router.completed_session)
        rows = h.router.session_summaries(h.now)
        self.assertFalse(any(r.id == "s2" and r.raised_sign for r in rows))

    def test_a_chat_out_of_sight_is_still_armed(self):
        """对照：s2 没开在眼前时照常举牌，会进卡叠。"""
        h = Harness(config=_config())
        h.send(Kind.task_start, session="s1")
        h.send(Kind.task_start, session="s2")
        h.run(1000)
        h.send(Kind.final_answer, session="s2")
        h.send(Kind.task_end, session="s2")
        h.run(20000)
        rows = h.router.session_summaries(h.now)
        self.assertTrue(any(r.id == "s2" and r.raised_sign for r in rows))


class NumberFieldTests(unittest.TestCase):
    def test_number_field_is_read_from_record_head(self):
        """lastFocusedAt 是裸数字，不是带引号的值：字符串版取不到，数字版取得到。"""
        head = b'{"sessionId":"local_a","cliSessionId":"c0a8","lastFocusedAt":1758342937123,'
        self.assertEqual(number_of("lastFocusedAt", head), 1758342937123.0)
        self.assertIsNone(value_of("lastFocusedAt", head))
        self.assertEqual(value_of("cliSessionId", head), "c0a8")

    def test_missing_field_is_none(self):
        self.assertIsNone(number_of("lastFocusedAt", b'{"sessionId":"local_a"}'))


if __name__ == "__main__":
    unittest.main()
