"""多个聊天同时跑：谁优先、怎么挑一条跟。移植自 YukioPlayer/Tests/YukioCoreTests/ChatPickTests.swift。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.events import Kind, PetState
from yukio.router import RouterConfig

from test_router import Harness


class ChatPickTests(unittest.TestCase):
    def test_a_finished_chat_takes_over_even_while_another_chat_keeps_working(self):
        h = Harness()
        h.send(Kind.task_start, session="A")
        h.send(Kind.activity_start, id="a1", activity=PetState.read_file, session="A")
        h.run(2000)
        self.assertEqual(h.router.focused_session, "A")

        h.send(Kind.task_start, session="B")
        h.run(2500)
        h.send(Kind.final_answer, session="B")
        h.send(Kind.task_end, session="B")
        h.run(3200)
        # B 答完了：哪怕 A 还在读文件，也先把 B 的完成提示显示出来。
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.respond)

        h.send(Kind.activity_end, id="a1", session="A")
        h.send(Kind.activity_start, id="a2", activity=PetState.write_file, session="A")
        h.run(12000)
        self.assertEqual(h.router.displayed, PetState.task_complete)
        self.assertEqual(h.router.completed_session, "B")

        # 点掉牌子：回到仍在干活的 A。
        self.assertTrue(h.router.dismiss_completion(h.now))
        self.assertEqual(h.router.focused_session, "A")
        self.assertEqual(h.router.displayed, PetState.write_file)

    def test_the_older_card_comes_back_after_you_handle_the_newer_one(self):
        h = Harness()
        h.send(Kind.task_start, session="B")
        h.run(1000)
        h.send(Kind.final_answer, session="B")
        h.send(Kind.task_end, session="B")
        h.run(6000)
        self.assertEqual(h.router.displayed, PetState.task_complete)
        self.assertEqual(h.router.completed_session, "B")

        # C 随后提问：更近的先给你看，B 的牌子仍举着。
        h.send(Kind.task_start, session="C")
        h.send(Kind.activity_start, id="q", activity=PetState.question_for_user, session="C")
        h.run(9000)
        self.assertEqual(h.router.focused_session, "C")
        self.assertEqual(h.router.displayed, PetState.question_for_user)

        h.send(Kind.activity_end, id="q", session="C")
        h.send(Kind.activity_start, id="c1", activity=PetState.read_file, session="C")
        h.run(13000)
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.task_complete)

    def test_an_ignored_card_yields_after_a_while_and_comes_back_when_the_other_chat_stops(self):
        cfg = RouterConfig()
        cfg.sign_yield_ms = 15 * 60 * 1000
        h = Harness(cfg)
        h.send(Kind.task_start, session="A", detail="改登录页")
        h.send(Kind.activity_start, id="a1", activity=PetState.read_file, session="A")
        h.run(1000)
        h.send(Kind.task_start, session="B", detail="写个脚本")
        h.run(2000)
        h.send(Kind.final_answer, session="B")
        h.send(Kind.task_end, session="B")
        h.run(12000)
        # 先举牌：A 还在读文件也抢不走。
        self.assertEqual(h.router.displayed, PetState.task_complete)
        self.assertEqual(h.router.completed_session, "B")

        # 晾了一刻钟没人点：先让位给还在干活的 A，牌子不放下。
        h.run(16 * 60000)
        self.assertEqual(h.router.focused_session, "A")
        self.assertEqual(h.router.displayed, PetState.read_file)
        self.assertIsNone(h.router.completed_session)
        listed = h.router.session_summaries(h.now)
        self.assertEqual(listed[0].id, "B")        # 仍排在最前，等你处理
        self.assertTrue(listed[0].sign_yielded)
        self.assertEqual(listed[0].menu_label, "写个脚本 · 举着牌子等你（先让位了）")

        # A 也停了：牌子重新举回来，点它照样跳回 B。
        h.send(Kind.task_abort, session="A")
        h.run(16 * 60000 + 5000)
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.task_complete)
        self.assertEqual(h.router.completed_session, "B")
        self.assertTrue(h.router.dismiss_completion(h.now))
        self.assertIs(h.router.displayed, PetState.idle)

    def test_a_question_outranks_a_newer_finished_chat_and_a_stuck_chat_outranks_work(self):
        h = Harness()
        # A 在等你拿主意。
        h.send(Kind.task_start, session="A")
        h.send(Kind.activity_start, id="q", activity=PetState.question_for_user, session="A")
        h.run(2000)
        # B 稍后才答完：虽然更近，问号卡仍排在勾选卡前面（和 GPT 那只宠物的档位一致）。
        h.send(Kind.task_start, session="B")
        h.run(3000)
        h.send(Kind.final_answer, session="B")
        h.send(Kind.task_end, session="B")
        h.run(9000)
        self.assertEqual(h.router.focused_session, "A")
        self.assertEqual(h.router.displayed, PetState.question_for_user)

        # C 整轮出错：排在问号卡之后、勾选卡之前，所以还是 A。
        h.send(Kind.task_start, session="C")
        h.run(10000)
        h.send(Kind.task_failed, session="C")
        h.run(12000)
        self.assertEqual(h.router.focused_session, "A")

        # A 答完了问题、接着干活：这时轮到出错的 C，而不是还举着牌子的 B。
        h.send(Kind.activity_end, id="q", session="A")
        h.send(Kind.activity_start, id="a1", activity=PetState.write_file, session="A")
        h.run(14000)
        self.assertEqual(h.router.focused_session, "C")
        self.assertEqual(h.router.displayed, PetState.failed)

        # C 的沮丧停留完，才轮到 B 的勾选卡（答完时她在跟别人，牌子也没丢）。
        h.run(22000)
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.task_complete)

    def test_a_stuck_chat_is_listed_ahead_of_the_ones_still_working(self):
        h = Harness()
        h.send(Kind.task_start, session="work", detail="改登录页")
        h.send(Kind.activity_start, id="w1", activity=PetState.write_file, session="work")
        h.run(1000)
        h.send(Kind.task_start, session="bad", detail="跑个构建")
        h.run(2000)
        h.send(Kind.task_failed, session="bad")
        h.run(4000)
        chats = h.router.session_summaries(h.now)
        self.assertEqual([c.id for c in chats], ["bad", "work"])
        self.assertTrue(chats[0].wants_you and not chats[1].wants_you)
        self.assertEqual(chats[0].menu_label, "跑个构建 · 出错停住了")

    def test_a_chat_that_finishes_while_she_follows_another_one_keeps_its_card(self):
        h = Harness()
        h.send(Kind.task_start, session="A")
        h.send(Kind.activity_start, id="a1", activity=PetState.read_file, session="A")
        h.run(1000)
        h.send(Kind.task_start, session="B")
        h.run(2000)
        h.send(Kind.final_answer, session="B")
        h.send(Kind.task_end, session="B")
        # 挑定 A：她一直跟 A，但 B 答完的牌子照样举起来存着，不会因为没轮到就丢了。
        h.router.pin_session("A", h.now)
        h.run(20000)
        self.assertEqual(h.router.displayed, PetState.read_file)
        listed = h.router.session_summaries(h.now)
        self.assertTrue(next(c for c in listed if c.id == "B").raised_sign)
        # 列聊天只看不动：看完了她还是跟着 A。
        self.assertEqual(h.router.displayed, PetState.read_file)
        # 回到自动：B 的牌子这才露出来。
        h.router.pin_session(None, h.now)
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.task_complete)
        self.assertEqual(h.router.completed_session, "B")

    def test_a_question_takes_over_from_another_chats_work(self):
        h = Harness()
        h.send(Kind.task_start, session="A")
        h.send(Kind.activity_start, id="a1", activity=PetState.default_work, session="A")
        h.run(2000)
        h.send(Kind.task_start, session="B")
        h.send(Kind.activity_start, id="q", activity=PetState.question_for_user, session="B")
        h.run(4500)
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.question_for_user)

        # 回答之后 B 接着干活，焦点留在 B，A 不来抢。
        h.send(Kind.activity_end, id="q", session="B")
        h.send(Kind.activity_start, id="b1", activity=PetState.write_file, session="B")
        h.run(8000)
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.write_file)

    def test_pinned_chat_is_not_stolen_by_other_chats(self):
        h = Harness()
        h.send(Kind.task_start, session="A")
        h.send(Kind.activity_start, id="a1", activity=PetState.read_file, session="A")
        h.run(1000)
        h.send(Kind.task_start, session="B")
        h.send(Kind.activity_start, id="b1", activity=PetState.write_file, session="B")
        h.run(3000)
        self.assertEqual(h.router.displayed, PetState.read_file)

        # 挑定 B：立刻换过去，不等防抖。
        self.assertTrue(h.router.pin_session("B", h.now))
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.write_file)

        # A 答完也抢不走挑定的 B。
        h.send(Kind.activity_end, id="a1", session="A")
        h.send(Kind.final_answer, session="A")
        h.send(Kind.task_end, session="A")
        h.run(8000)
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.write_file)

        # 回到自动：A 的完成提示这时才轮到（还在停留时间之内）。
        self.assertTrue(h.router.pin_session(None, h.now))
        self.assertIsNone(h.router.pinned_session)
        self.assertEqual(h.router.focused_session, "A")
        self.assertEqual(h.router.displayed, PetState.task_complete)

    def test_pinned_chat_stays_even_after_it_stops(self):
        h = Harness()
        h.send(Kind.task_start, session="A")
        h.send(Kind.activity_start, id="a1", activity=PetState.read_file, session="A")
        h.run(1000)
        h.send(Kind.task_start, session="B")
        h.send(Kind.activity_start, id="b1", activity=PetState.write_file, session="B")
        h.run(3000)
        h.router.pin_session("B", h.now)
        h.send(Kind.activity_end, id="b1", session="B")
        h.send(Kind.task_abort, session="B")
        h.run(9000)
        # 挑定的那条停了就空闲等着，不会自己跑去跟 A。
        self.assertEqual(h.router.focused_session, "B")
        self.assertEqual(h.router.displayed, PetState.idle)

        h.router.pin_session(None, h.now)
        self.assertEqual(h.router.focused_session, "A")
        self.assertEqual(h.router.displayed, PetState.read_file)

    def test_chat_list_puts_the_ones_waiting_for_you_first(self):
        h = Harness()
        h.send(Kind.task_start, session="old", detail="看看昨天的报错")
        h.run(1000)
        h.send(Kind.task_abort, session="old")
        h.run(600000)
        h.send(Kind.task_start, session="work", detail="改登录页")
        h.send(Kind.activity_start, id="w1", activity=PetState.write_file, session="work")
        h.run(605000)
        h.send(Kind.task_start, session="done", detail="写个脚本")
        h.send(Kind.session_title, session="done", detail="写个备份脚本")
        h.run(606000)
        h.send(Kind.final_answer, session="done")
        h.send(Kind.task_end, session="done")
        h.run(612000)

        chats = h.router.session_summaries(h.now)
        self.assertEqual([c.id for c in chats], ["done", "work", "old"])
        self.assertEqual(chats[0].menu_label, "写个备份脚本 · 举着牌子等你点")
        self.assertTrue(chats[0].raised_sign and chats[0].focused)
        self.assertEqual(chats[1].menu_label, "改登录页 · 修改文件")
        self.assertEqual(chats[2].menu_label, "看看昨天的报错 · 10 分钟前")

        # 安静太久的不列；等你处理的和在跑的一定留着。
        self.assertEqual([c.id for c in h.router.session_summaries(h.now, quiet_within_ms=60000)],
                         ["done", "work"])
        self.assertEqual([c.id for c in h.router.session_summaries(h.now, limit=1)], ["done"])

    def test_a_chat_without_a_title_is_listed_by_its_session_id(self):
        h = Harness()
        h.send(Kind.task_start, session="c0a80650-7c4e-4a1b-9c3d-000000000000")
        h.run(1000)
        chats = h.router.session_summaries(h.now)
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0].menu_label, "会话 c0a80650… · 思考中")

    def test_picking_a_chat_the_player_has_never_seen_changes_nothing(self):
        h = Harness()
        h.send(Kind.task_start, session="A")
        h.run(1000)
        self.assertFalse(h.router.pin_session("从没见过", h.now))
        self.assertIsNone(h.router.pinned_session)
        self.assertEqual(h.router.focused_session, "A")


if __name__ == "__main__":
    unittest.main()
