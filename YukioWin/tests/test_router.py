"""路由、防抖、保持时间与气泡文字的测试。移植自 YukioPlayer/Tests/YukioCoreTests。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yukio.demo import demo_steps, DEMO_DURATION_MS
from yukio.events import ALL_STATES, Kind, PetEvent, PetState, TodoItem, TodoStatus
from yukio.router import ActivityRouter, HeldValue, Progress, RouterConfig, StatusLine


class Harness:
    """用虚拟时钟驱动路由器，记录每次显示切换。"""

    def __init__(self, config=None, session="s1"):
        self.router = ActivityRouter(now=0, config=config)
        self.now = 0.0
        self.transitions = []
        self.session = session

    def send(self, kind, id=None, activity=None, session=None, source="test", detail=None, todos=None):
        self.router.ingest(PetEvent(self.now, source, session or self.session, kind,
                                    event_id=id, activity=activity, detail=detail, todos=todos), self.now)

    def run(self, to):
        s = self.router.tick(self.now)
        if s:
            self.transitions.append((self.now, s))
        while self.now < to:
            self.now = min(to, self.now + 25)
            s = self.router.tick(self.now)
            if s:
                self.transitions.append((self.now, s))

    @property
    def states(self):
        return [s for _, s in self.transitions]

    @property
    def line(self):
        return self.router.status_line(self.now)


class RouterTests(unittest.TestCase):
    def test_first_switch_only_waits_for_debounce(self):
        h = Harness()
        h.send(Kind.task_start)
        h.run(1000)
        self.assertEqual(h.states, [PetState.thinking])
        self.assertEqual(h.transitions[0][0], 400)

    def test_burst_of_short_reads_merges_into_one_reading_pose(self):
        h = Harness()
        h.send(Kind.task_start)
        h.run(3000)
        for i, t in enumerate([3000, 3300, 3600, 3900, 4200]):
            h.run(t)
            h.send(Kind.activity_start, id="r%d" % i, activity=PetState.read_file)
            h.run(t + 100)
            h.send(Kind.activity_end, id="r%d" % i)
        h.run(10000)
        self.assertEqual(h.states, [PetState.thinking, PetState.read_file, PetState.thinking])

    def test_rapid_alternation_shorter_than_debounce_never_flashes(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="a", activity=PetState.read_file)
        h.run(3000)
        h.send(Kind.activity_start, id="b", activity=PetState.write_file)
        h.run(3100)
        h.send(Kind.activity_end, id="b")
        h.send(Kind.activity_start, id="c", activity=PetState.read_file)
        h.run(6000)
        self.assertEqual(h.states, [PetState.read_file])

    def test_each_displayed_state_is_held_for_minimum_time(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="a", activity=PetState.read_file)
        h.run(500)
        h.send(Kind.activity_end, id="a")
        h.send(Kind.activity_start, id="b", activity=PetState.verify)
        h.run(5000)
        self.assertEqual(h.states, [PetState.read_file, PetState.verify])
        self.assertGreaterEqual(h.transitions[1][0], h.transitions[0][0] + 1500)

    def test_same_activity_does_not_restart(self):
        h = Harness()
        h.send(Kind.task_start)
        for i in range(10):
            h.send(Kind.activity_start, id="w%d" % i, activity=PetState.write_file)
            h.run(h.now + 300)
            h.send(Kind.activity_end, id="w%d" % i)
            h.run(h.now + 300)
        h.run(h.now + 100)
        self.assertEqual(h.states, [PetState.write_file])

    def test_respond_then_task_complete_then_idle(self):
        cfg = RouterConfig()
        cfg.respond_linger_ms = 8000
        cfg.respond_hold_ms = 3000
        h = Harness(cfg)
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(20000)
        self.assertEqual(h.states, [PetState.thinking, PetState.respond, PetState.task_complete, PetState.idle])
        respond_at, card_at, idle_at = h.transitions[1][0], h.transitions[2][0], h.transitions[3][0]
        self.assertTrue(2900 <= card_at - respond_at <= 3600)
        self.assertGreaterEqual(idle_at - respond_at, 7500)

    def test_respond_hold_longer_than_linger_never_shows_the_card(self):
        cfg = RouterConfig()
        cfg.respond_linger_ms = 3000
        cfg.respond_hold_ms = 8000
        h = Harness(cfg)
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(20000)
        self.assertEqual(h.states, [PetState.thinking, PetState.respond, PetState.idle])

    def test_ask_user_question_keeps_task_open(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="q", activity=PetState.question_for_user)
        h.run(4000)
        self.assertEqual(h.states, [PetState.question_for_user])
        self.assertEqual(h.line.current, "等你回答")
        h.send(Kind.activity_end, id="q")
        h.send(Kind.thinking)
        h.run(8000)
        self.assertEqual(h.states, [PetState.question_for_user, PetState.thinking])

    def test_abort_goes_to_idle_without_report(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="a", activity=PetState.verify)
        h.run(3000)
        h.send(Kind.task_abort)
        h.run(6000)
        self.assertEqual(h.states, [PetState.verify, PetState.idle])

    def test_end_before_start_is_ignored(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_end, id="x")
        h.send(Kind.activity_start, id="x", activity=PetState.read_web)
        h.run(3000)
        self.assertEqual(h.states, [PetState.thinking])

    def test_late_tool_event_after_task_end_cannot_revive(self):
        h = Harness()
        h.send(Kind.task_start)
        h.run(2000)
        h.send(Kind.task_abort)
        h.run(4000)
        h.router.ingest(PetEvent(1000, "test", "s1", Kind.activity_start, event_id="old",
                                 activity=PetState.verify), h.now)
        h.run(8000)
        self.assertEqual(h.states, [PetState.thinking, PetState.idle])

    def test_duplicate_events_from_two_adapters_are_idempotent(self):
        h = Harness()
        h.send(Kind.task_start, source="deepcode")
        h.send(Kind.task_start, source="bridge")
        h.send(Kind.activity_start, id="t1", activity=PetState.verify, source="deepcode")
        h.send(Kind.activity_start, id="t1", activity=PetState.verify, source="bridge")
        h.run(2000)
        h.send(Kind.activity_end, id="t1", source="bridge")
        h.send(Kind.activity_end, id="t1", source="deepcode")
        h.run(6000)
        self.assertEqual(h.states, [PetState.verify, PetState.thinking])
        self.assertEqual(h.router.snapshot().open_tools, 0)

    def test_continue_previous_reuses_last_tool_activity(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="b", activity=PetState.verify)
        h.run(2000)
        h.send(Kind.activity_end, id="b")
        h.send(Kind.activity_start, id="poll", activity=None)
        h.run(6000)
        self.assertEqual(h.states, [PetState.verify])

    def test_other_session_does_not_cross_talk(self):
        h = Harness()
        h.send(Kind.task_start, session="A")
        h.send(Kind.activity_start, id="a1", activity=PetState.read_file, session="A")
        h.run(1000)
        h.send(Kind.task_start, session="B")
        h.send(Kind.activity_start, id="b1", activity=PetState.write_file, session="B")
        h.run(5000)
        self.assertEqual(h.states, [PetState.read_file])
        self.assertEqual(h.router.focused_session, "A")
        h.send(Kind.task_abort, session="A")
        h.run(9000)
        self.assertEqual(h.states, [PetState.read_file, PetState.write_file])
        self.assertEqual(h.router.focused_session, "B")

    def test_stale_session_falls_back_to_idle(self):
        cfg = RouterConfig()
        cfg.stale_no_tool_ms = 60000
        h = Harness(cfg)
        h.send(Kind.task_start)
        h.run(70000)
        self.assertEqual(h.states, [PetState.thinking, PetState.idle])

    def test_long_running_tool_uses_longer_stale_limit(self):
        cfg = RouterConfig()
        cfg.stale_no_tool_ms = 60000
        cfg.stale_open_tool_ms = 300000
        h = Harness(cfg)
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="build", activity=PetState.default_work)
        h.run(200000)
        self.assertEqual(h.states, [PetState.default_work])
        h.run(320000)
        self.assertEqual(h.states, [PetState.default_work, PetState.idle])

    def test_source_lost_returns_to_idle(self):
        h = Harness()
        h.send(Kind.task_start, source="deepcode")
        h.send(Kind.activity_start, id="a", activity=PetState.read_web, source="deepcode")
        h.run(3000)
        h.router.ingest(PetEvent(h.now, "deepcode", "*", Kind.source_lost), h.now)
        h.run(6000)
        self.assertEqual(h.states, [PetState.read_web, PetState.idle])

    def test_settle_after_replay_shows_current_state_immediately(self):
        r = ActivityRouter(now=0)
        events = [
            PetEvent(1000, "t", "s", Kind.task_start),
            PetEvent(2000, "t", "s", Kind.activity_start, event_id="1", activity=PetState.read_file),
            PetEvent(2100, "t", "s", Kind.activity_end, event_id="1"),
            PetEvent(5000, "t", "s", Kind.activity_start, event_id="2", activity=PetState.verify),
        ]
        for e in events:
            r.ingest(e, e.ts)
        r.settle(5200)
        self.assertEqual(r.displayed, PetState.verify)

    def test_tool_failure_shows_dejected_until_next_activity(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="t", activity=PetState.verify)
        h.run(3000)
        h.send(Kind.activity_failed, id="t")
        h.run(5500)
        h.send(Kind.activity_start, id="fix", activity=PetState.write_file)
        h.run(9000)
        self.assertEqual(h.states, [PetState.verify, PetState.failed, PetState.write_file])

    def test_dejected_ends_in_thinking(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="t", activity=PetState.verify)
        h.run(3000)
        h.send(Kind.activity_failed, id="t")
        h.run(12000)
        self.assertEqual(h.states, [PetState.verify, PetState.failed, PetState.thinking])
        self.assertGreaterEqual(h.transitions[2][0] - h.transitions[1][0], 3500)

    def test_task_failure_shows_dejected_then_idle(self):
        h = Harness()
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.task_failed)
        h.run(20000)
        self.assertEqual(h.states, [PetState.thinking, PetState.failed, PetState.idle])
        self.assertGreaterEqual(h.transitions[2][0] - h.transitions[1][0], 7500)

    def test_new_prompt_ends_dejected_early(self):
        h = Harness()
        h.send(Kind.task_start)
        h.run(3000)
        h.send(Kind.task_failed)
        h.run(6000)
        h.send(Kind.task_start)
        h.run(9000)
        self.assertEqual(h.states, [PetState.thinking, PetState.failed, PetState.thinking])

    def test_interrupt_right_after_failure_goes_straight_to_idle(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="t", activity=PetState.verify)
        h.run(3000)
        h.send(Kind.activity_failed, id="t")
        h.run(3100)
        h.send(Kind.task_abort)
        h.run(8000)
        self.assertEqual(h.states, [PetState.verify, PetState.idle])

    def test_demo_script_shows_every_state(self):
        h = Harness(session="demo")
        for step in demo_steps("demo", 0):
            h.run(step.offset_ms)
            h.router.ingest(step.event, h.now)
        h.run(DEMO_DURATION_MS)
        shown = set(h.states)
        for s in ALL_STATES:
            if s is not PetState.idle:
                self.assertIn(s, shown, "演示中没有出现 %s" % s)
        self.assertEqual(h.states[-1], PetState.idle)
        self.assertEqual(h.states[-2], PetState.task_complete)
        self.assertEqual(h.states[-3], PetState.respond)
        for (ta, _), (tb, sb) in zip(h.transitions, h.transitions[1:]):
            self.assertGreaterEqual(tb - ta, 1500)
        reads = [t for t, s in h.transitions if t < 9000 and s is PetState.read_file]
        self.assertEqual(len(reads), 1)


class StatusLineTests(unittest.TestCase):
    def test_hidden_when_idle_and_text_follows_the_pose(self):
        h = Harness()
        self.assertIsNone(h.line)
        h.send(Kind.task_start, detail="修一下登录页")
        h.run(1000)
        self.assertEqual(h.line, StatusLine("修一下登录页", "思考中", None))
        h.send(Kind.activity_start, id="a", activity=PetState.write_file, detail="编辑 main.py")
        h.run(1200)
        self.assertEqual(h.line.current, "思考中")
        h.run(3000)
        self.assertEqual(h.line.current, "编辑 main.py")
        h.send(Kind.session_title, detail="桌宠缺失状态")
        self.assertEqual(h.line.title, "桌宠缺失状态")
        h.send(Kind.activity_end, id="a")
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(6000)
        self.assertEqual(h.line.current, "已回答")
        h.run(20000)
        self.assertIsNone(h.line)

    def test_todo_list_gives_current_item_and_progress(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.todo_update, todos=[TodoItem("1", "读代码"), TodoItem("2", "改代码"), TodoItem("3", "跑测试")])
        h.send(Kind.todo_update, todos=[TodoItem("1", status=TodoStatus.completed),
                                        TodoItem("2", status=TodoStatus.in_progress)])
        h.send(Kind.activity_start, id="e", activity=PetState.write_file, detail="编辑 a.py")
        h.run(1000)
        self.assertEqual(h.line, StatusLine(None, "改代码", Progress(1, 3)))
        h.send(Kind.todo_update, todos=[TodoItem("2", status=TodoStatus.completed),
                                        TodoItem("3", status=TodoStatus.completed)])
        h.send(Kind.todo_update, todos=[TodoItem("4", "写文档")])
        self.assertEqual(h.line.progress, Progress(0, 1))
        self.assertEqual(h.line.current, "编辑 a.py")
        h.send(Kind.todo_update, todos=[TodoItem("4", status=TodoStatus.deleted)])
        self.assertIsNone(h.line.progress)

    def test_failure_and_waiting_texts(self):
        h = Harness()
        h.send(Kind.task_start)
        h.send(Kind.activity_start, id="t", activity=PetState.verify, detail="$ pytest")
        h.run(3000)
        h.send(Kind.activity_failed, id="t")
        h.run(4000)
        self.assertEqual(h.line.current, "出错：$ pytest")
        h.send(Kind.activity_start, id="q", activity=PetState.question_for_user, detail="等你回答")
        h.run(7000)
        self.assertEqual(h.router.displayed, PetState.question_for_user)
        self.assertEqual(h.line.current, "等你回答")
        h.send(Kind.activity_end, id="q")
        h.send(Kind.final_answer)
        h.send(Kind.task_end)
        h.run(12000)
        self.assertEqual(h.router.displayed, PetState.task_complete)
        self.assertEqual(h.line.current, "已完成")


class HeldValueTests(unittest.TestCase):
    def test_each_text_stays_then_jumps_to_the_latest(self):
        v = HeldValue(None, min_hold_ms=1000)
        self.assertTrue(v.update("a", 0, immediate=True))
        self.assertFalse(v.update("b", 300))
        self.assertFalse(v.update("c", 600))
        self.assertEqual(v.value, "a")
        self.assertTrue(v.update("c", 1000))
        self.assertEqual(v.value, "c")
        self.assertTrue(v.update(None, 1100, immediate=True))
        self.assertIsNone(v.value)


if __name__ == "__main__":
    unittest.main()
