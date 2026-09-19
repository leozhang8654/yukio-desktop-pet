"""雪绪头顶那摞通知卡。移植自 YukioPlayer/Tests/YukioCoreTests/CardStackTests.swift。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.cards import CardStatus
from yukio.events import Kind, PetState

from test_router import Harness


def three_chats() -> Harness:
    """三条聊天各有话说：等你回答的排最前，然后出错的、答完的，最后还在干活的。"""
    h = Harness()
    h.send(Kind.task_start, session="work", detail="改登录页")
    h.send(Kind.activity_start, id="w1", activity=PetState.write_file, session="work",
           detail="编辑 Login.py")
    h.run(1000)
    h.send(Kind.task_start, session="done", detail="写个脚本")
    h.run(2000)
    h.send(Kind.final_answer, session="done")
    h.send(Kind.task_end, session="done")
    h.run(3000)
    h.send(Kind.task_start, session="ask", detail="要不要换个库")
    h.send(Kind.activity_start, id="q", activity=PetState.question_for_user, session="ask",
           detail="等你挑一个")
    h.run(6000)
    return h


def sessions(cards) -> list:
    return [c.session for c in cards]


class CardStackTests(unittest.TestCase):
    def test_cards_are_sorted_by_who_needs_you_first_and_skip_the_one_she_is_showing(self):
        h = three_chats()
        # 她跟着“等你回答”的那条，所以那条不在卡叠里（头顶气泡已经在讲它）。
        self.assertEqual(h.router.focused_session, "ask")
        cards = h.router.cards(h.now)
        self.assertEqual(sessions(cards), ["done", "work"])
        self.assertEqual(cards[0].status, CardStatus.ready)
        self.assertEqual(cards[0].title, "写个脚本")
        self.assertEqual(cards[0].subtitle, "点开看看")
        self.assertEqual(cards[0].status_label, "答完了")
        self.assertEqual(cards[1].status, CardStatus.running)
        self.assertEqual(cards[1].subtitle, "编辑 Login.py")
        # 连她正显示的那条一起列（自查用）时，等你回答的排最前。
        self.assertEqual(sessions(h.router.cards(h.now, include_focused=True)),
                         ["ask", "done", "work"])

    def test_a_failed_chat_gets_a_card_ahead_of_the_finished_one(self):
        h = three_chats()
        h.send(Kind.task_start, session="bad", detail="跑个构建")
        h.run(7000)
        h.send(Kind.task_failed, session="bad")
        h.run(8000)
        cards = h.router.cards(h.now)
        self.assertEqual(sessions(cards), ["bad", "done", "work"])
        self.assertEqual(cards[0].status, CardStatus.failed)
        self.assertEqual(cards[0].subtitle, "这一轮没做完")

    def test_dismissing_a_card_puts_the_sign_down_and_keeps_it_away_until_the_next_turn(self):
        h = three_chats()
        self.assertEqual(sessions(h.router.cards(h.now)), ["done", "work"])
        h.router.dismiss_card("done", h.now)
        self.assertEqual(sessions(h.router.cards(h.now)), ["work"])
        # 那条聊天又开工：卡重新出现。
        h.run(9000)
        h.send(Kind.task_start, session="done", detail="接着写")
        h.send(Kind.activity_start, id="d1", activity=PetState.read_file, session="done",
               detail="读 backup.sh")
        h.run(10000)
        self.assertTrue(any(c.session == "done" and c.status == CardStatus.running
                            for c in h.router.cards(h.now)))

    def test_dismissing_the_card_of_the_chat_she_is_showing_switches_her_to_the_next_one(self):
        h = three_chats()
        # 她正举着别人的问号卡；直接点掉“等你回答”的那条（卡叠里看不到它，但菜单可以）。
        self.assertEqual(h.router.focused_session, "ask")
        h.router.dismiss_card("ask", h.now)
        h.run(8000)
        # 换成答完的那条（档位比“在跑”的高）。
        self.assertEqual(h.router.focused_session, "done")
        self.assertEqual(sessions(h.router.cards(h.now)), ["work"])

    def test_muted_chats_get_no_cards(self):
        h = three_chats()
        h.router.mute_cards("work")
        self.assertTrue(h.router.is_muted("work"))
        self.assertEqual(sessions(h.router.cards(h.now)), ["done"])
        h.router.unmute_cards("work")
        self.assertEqual(sessions(h.router.cards(h.now)), ["done", "work"])

    def test_quiet_chats_drop_off_the_stack(self):
        h = three_chats()
        # 半个多小时没动静：在跑的和等你回答的都算失联，不再出卡；
        # 只剩那条举着牌子的，她自己转过去显示它，旁边就空了。
        h.run(35 * 60000)
        self.assertEqual(h.router.focused_session, "done")
        self.assertEqual(h.router.cards(h.now), [])
        self.assertEqual(sessions(h.router.cards(h.now, include_focused=True)), ["done"])


if __name__ == "__main__":
    unittest.main()
