"""播放器主体的逻辑测试：主循环换帧、气泡摆位、拖动、菜单、设置。

窗口层换成 tests/fake_win32.py，所以这些测试在任何平台都能跑；
真正的系统调用（分层窗口、托盘、弹菜单）没有被覆盖，只能在 Windows 上实机看。
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from yukio.l10n import set_language  # noqa: E402
set_language("zh")   # 这些测试按中文文案断言


def setUpModule():
    set_language("zh")   # 前一个模块的应用测试可能把语言切回了英文
sys.path.insert(0, HERE)

import fake_win32
import yukio
sys.modules["yukio.win32"] = fake_win32
yukio.win32 = fake_win32

from yukio import app as app_module
from yukio.events import PetState
from yukio.settings import Settings


CLOCK = [1_780_000_000_000.0]


def now() -> float:
    return CLOCK[0]


def advance(application, ticks: int, step: float = 33.0):
    """按 33 ms 一拍推进假时钟并调用 tick()。"""
    for _ in range(ticks):
        CLOCK[0] += step
        application.tick()


def make_app(argv=None, dpi=1.0, first_run=False, sources=None, **overrides):
    """first_run=False 时先放一份设置文件：这样就不是“第一次打开”，不会自动播演示。"""
    fake_win32.QUIT[:] = []
    fake_win32.CURSOR[:] = [0, 0]
    fake_win32.DPI = dpi
    CLOCK[0] = 1_780_000_000_000.0
    app_module.now_ms = now
    settings_path = os.path.join(tempfile.mkdtemp(prefix="yukio-test-"), "settings.json")
    if not first_run:
        with open(settings_path, "w", encoding="utf-8") as fh:
            fh.write('{"language": "zh"}')   # 测试按中文文案断言
    application = object.__new__(app_module.PetApp)
    # 用临时设置文件，不碰用户自己的设置；来源用空列表，事件由测试直接喂。
    original_settings = Settings
    try:
        app_module.Settings = lambda: original_settings(settings_path)
        app_module.default_sources = lambda which: list(sources or [])
        application.__init__(argv or [])
        set_language("zh")   # 第一次打开（没有设置文件）时默认英文，测试仍按中文断言
    finally:
        app_module.Settings = original_settings
    for key, value in overrides.items():
        application.settings.set(key, value)
    return application


class _FakeLinks:
    """冒充桌面版 Claude 的会话记录：只认这几条会话。"""

    def __init__(self, urls):
        self.urls = urls

    def chat_url(self, session):
        return self.urls.get(session)


class AppLogicTests(unittest.TestCase):
    def test_starts_idle_and_paints_one_frame(self):
        a = make_app()
        self.assertEqual(a.shown_state, PetState.idle)
        self.assertEqual(len(a.pet.images), 1)
        self.assertEqual(a.pet.images[0][2], (192, 208))
        # 右下角：工作区右边缘往里 24 点、下边缘往上 12 点。
        self.assertEqual((a.pet.x, a.pet.y), (1920 - 192 - 24, 1080 - 208 - 12))

    def test_high_dpi_renders_bigger_pixels(self):
        a = make_app(dpi=1.5)
        self.assertEqual(a.pet_size, (288, 312))
        self.assertEqual(a.pet.images[-1][2], (288, 312))

    def test_demo_runs_through_states_and_shows_the_bubble(self):
        a = make_app(["--demo"])
        seen = set()
        bubbles = []
        # 演示脚本 60 秒，按 33 ms 一拍推进（假时钟）。
        for _ in range(2000):
            CLOCK[0] += 33
            a.tick()
            seen.add(a.shown_state)
            if a.bubble_hold.value is not None:
                bubbles.append(a.bubble_hold.value.current)
        for state in (PetState.read_file, PetState.view_image, PetState.write_file,
                      PetState.verify, PetState.read_web, PetState.failed,
                      PetState.question_for_user, PetState.respond, PetState.task_complete):
            self.assertIn(state, seen, state)
        self.assertTrue(bubbles)
        self.assertIn("修正表单校验", bubbles)
        # 气泡跟着雪绪放在头顶上方、且不超出屏幕。
        self.assertLess(a.bubble.y, a.pet.y + a.library.head_top_inset)
        self.assertGreaterEqual(a.bubble.x, 0)

    def test_drag_lifts_her_by_an_invisible_hand_and_puts_her_back(self):
        a = make_app()
        start_x, start_y = a.pet.x, a.pet.y
        fake_win32.CURSOR[:] = [start_x + 50, start_y + 50]
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONDOWN, 0, 0)
        self.assertTrue(fake_win32.user32.captured)
        # 往左拖 40 点：她被拎起来，窗口临时放大到容得下摆动与下坠。
        fake_win32.CURSOR[0] -= 40
        a._pet_proc(a.pet.hwnd, fake_win32.WM_MOUSEMOVE, 0, 0)
        self.assertTrue(a._dragging)
        self.assertIsNotNone(a.swing)
        self.assertEqual(a.held_timeline.spec.id, "held")
        self.assertEqual(a.pet.images[-1][2], a.hang_geo.panel_size)
        self.assertGreater(a.hang_geo.panel_size[0], 192)
        # 平时那块跟着鼠标走了 40 点。
        self.assertEqual(a._normal_frame(), (start_x - 40, start_y))

        # 往左甩：身体落在后面，也就是脚偏向右（正角）。
        for _ in range(6):
            CLOCK[0] += 33
            fake_win32.CURSOR[0] -= 30
            a._pet_proc(a.pet.hwnd, fake_win32.WM_MOUSEMOVE, 0, 0)
        self.assertGreater(a.swing.angle_degrees, 2)

        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONUP, 0, 0)
        self.assertFalse(a._dragging)
        self.assertFalse(fake_win32.user32.captured)
        # 松手：位置按平时那块 192×208 存，不是放大的窗口。
        self.assertEqual(a.settings.get("originX"), a._normal_frame()[0])

        # 晃一会儿自己停稳，窗口还原成平时那块。
        advance(a, 90)
        self.assertIsNone(a.swing)
        self.assertEqual(a.pet.images[-1][2], (192, 208))
        self.assertEqual((a.pet.x, a.pet.y), (a.settings.get("originX"), a.settings.get("originY")))

    def test_grabbing_again_while_she_is_still_swinging_keeps_one_window(self):
        a = make_app()
        fake_win32.CURSOR[:] = [a.pet.x + 50, a.pet.y + 50]
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONDOWN, 0, 0)
        fake_win32.CURSOR[0] -= 40
        a._pet_proc(a.pet.hwnd, fake_win32.WM_MOUSEMOVE, 0, 0)
        panel = a.hang_geo.panel_size
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONUP, 0, 0)
        advance(a, 2)
        # 还在晃就又抓住：窗口已经是放大的，不再叠一次偏移。
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONDOWN, 0, 0)
        fake_win32.CURSOR[0] -= 20
        a._pet_proc(a.pet.hwnd, fake_win32.WM_MOUSEMOVE, 0, 0)
        self.assertEqual(a.hang_geo.panel_size, panel)
        self.assertIsNone(a._released_at)

    def test_drag_beyond_the_screen_is_clamped_back(self):
        a = make_app()
        fake_win32.CURSOR[:] = [500, 500]
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONDOWN, 0, 0)
        fake_win32.CURSOR[:] = [5000, 5000]
        a._pet_proc(a.pet.hwnd, fake_win32.WM_MOUSEMOVE, 0, 0)
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONUP, 0, 0)
        self.assertLessEqual(a.pet.x + a.pet_size[0], 1920)
        self.assertLessEqual(a.pet.y + a.pet_size[1], 1080)

    def test_menu_toggles_and_scale(self):
        a = make_app()
        a.show_menu()
        texts = [i.text for i in fake_win32.LAST_MENU]
        self.assertIn("跟随 AI 活动", texts)
        self.assertIn("退出雪绪", texts)
        by_text = {i.text: i for i in fake_win32.LAST_MENU}
        self.assertTrue(by_text["跟随 AI 活动"].checked)
        by_text["跟随 AI 活动"].action()
        self.assertFalse(a.follow)
        by_text["头顶显示任务"].action()
        self.assertFalse(a.show_bubble)
        foot_before = a.pet.y + a.pet_size[1]
        size_menu = {i.text: i for i in by_text["大小"].submenu}
        size_menu["150%"].action()
        self.assertEqual(a.user_scale, 1.5)
        self.assertEqual(a.pet_size, (288, 312))
        # 以脚下为锚：缩放后落脚点不跳。
        self.assertAlmostEqual(a.pet.y + a.pet_size[1], foot_before, delta=1)
        source_menu = {i.text: i for i in by_text["跟随的助手"].submenu}
        source_menu["DeepSeek（Deep Code）"].action()
        self.assertEqual(a.settings.get("source"), "deepcode")
        source_menu["GPT（Codex）"].action()
        self.assertEqual(a.settings.get("source"), "gpt")
        by_text["回到屏幕右下角"].action()
        self.assertEqual((a.pet.x, a.pet.y), a._default_origin())
        by_text["退出雪绪"].action()
        self.assertTrue(fake_win32.QUIT)

    def test_menu_lets_you_pick_which_chat_to_follow(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        t = now()
        a.router.ingest(PetEvent(t, "test", "A", Kind.task_start, detail="改登录页"), t)
        a.router.ingest(PetEvent(t, "test", "A", Kind.activity_start, event_id="a1",
                                 activity=PetState.read_file), t)
        advance(a, 30)          # 先跟上 A（真实主循环 30 Hz，不会两条一起进来）
        t = now()
        a.router.ingest(PetEvent(t, "test", "B", Kind.task_start, detail="写个脚本"), t)
        a.router.ingest(PetEvent(t, "test", "B", Kind.activity_start, event_id="b1",
                                 activity=PetState.write_file), t)
        advance(a, 60)
        a.show_menu()
        picker = [i for i in fake_win32.LAST_MENU if i.text.startswith("跟随的聊天")][0]
        self.assertEqual(picker.text, "跟随的聊天（2 条在跑）")
        rows = {i.text: i for i in picker.submenu}
        self.assertTrue(rows["自动（完成和提问优先）"].checked)
        # 自动跟着的那条前面有箭头；两条都列出来。
        self.assertIn("→ 改登录页 · 阅读文件", rows)
        self.assertIn("写个脚本 · 修改文件", rows)
        # 挑定 B：立刻换过去，菜单里改成打勾。
        rows["写个脚本 · 修改文件"].action()
        self.assertEqual(a.router.pinned_session, "B")
        self.assertEqual(a.router.displayed, PetState.write_file)
        a.show_menu()
        picker = [i for i in fake_win32.LAST_MENU if i.text.startswith("跟随的聊天")][0]
        rows = {i.text: i for i in picker.submenu}
        self.assertFalse(rows["自动（完成和提问优先）"].checked)
        self.assertTrue(rows["写个脚本 · 修改文件"].checked)
        self.assertIn("正在跟：写个脚本 · 修改文件（挑定的）", [i.text for i in fake_win32.LAST_MENU])
        # 回到自动。
        rows["自动（完成和提问优先）"].action()
        self.assertIsNone(a.router.pinned_session)

    def test_paused_following_keeps_her_idle(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        a.settings.set("follow", False)
        t = now()
        a.router.ingest(PetEvent(t, "test", "s", Kind.task_start), t)
        a.router.ingest(PetEvent(t, "test", "s", Kind.activity_start, event_id="t",
                                 activity=PetState.write_file), t)
        advance(a, 60)
        self.assertEqual(a.shown_state, PetState.idle)
        a.settings.set("follow", True)
        advance(a, 80)
        self.assertEqual(a.shown_state, PetState.write_file)

    def test_clicking_the_raised_sign_opens_that_chat_and_puts_it_down(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        fake_win32.OPENED_URLS[:] = []
        # 假的会话记录：点牌子时按它查出深链。
        a.links = _FakeLinks({"S": "claude://code/continue?session=local_test"})
        t = now()
        a.router.ingest(PetEvent(t, "test", "S", Kind.task_start), t)
        advance(a, 30)
        t = now()
        a.router.ingest(PetEvent(t, "test", "S", Kind.final_answer), t)
        a.router.ingest(PetEvent(t, "test", "S", Kind.task_end), t)
        advance(a, 400)         # 递交报告 → 举勾选卡
        self.assertEqual(a.shown_state, PetState.task_complete)
        self.assertEqual(a.router.completed_session, "S")

        # 按下又抬起、中间没动：算点了她一下。
        fake_win32.CURSOR[:] = [a.pet.x + 90, a.pet.y + 150]
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONDOWN, 0, 0)
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONUP, 0, 0)
        self.assertEqual(fake_win32.OPENED_URLS, ["claude://code/continue?session=local_test"])
        self.assertIsNone(a.router.completed_session)
        advance(a, 80)
        self.assertEqual(a.shown_state, PetState.idle)

    def test_clicking_the_question_card_opens_the_chat_but_keeps_the_card_up(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        fake_win32.OPENED_URLS[:] = []
        a.links = _FakeLinks({"S": "claude://code/continue?session=local_ask"})
        t = now()
        a.router.ingest(PetEvent(t, "test", "S", Kind.task_start), t)
        a.router.ingest(PetEvent(t, "test", "S", Kind.activity_start, event_id="q",
                                 activity=PetState.question_for_user, detail="等你挑一个"), t)
        advance(a, 60)
        self.assertEqual(a.shown_state, PetState.question_for_user)
        fake_win32.CURSOR[:] = [a.pet.x + 90, a.pet.y + 150]
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONDOWN, 0, 0)
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONUP, 0, 0)
        self.assertEqual(fake_win32.OPENED_URLS, ["claude://code/continue?session=local_ask"])
        # 问题还等着你答：卡片不收。
        advance(a, 30)
        self.assertEqual(a.shown_state, PetState.question_for_user)

    def test_a_chat_she_is_not_showing_gets_a_card_above_the_bubble(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        fake_win32.OPENED_URLS[:] = []
        a.links = _FakeLinks({"B": "claude://code/continue?session=local_b"})
        t = now()
        a.router.ingest(PetEvent(t, "test", "A", Kind.task_start, detail="改登录页"), t)
        a.router.ingest(PetEvent(t, "test", "A", Kind.activity_start, event_id="a1",
                                 activity=PetState.question_for_user, detail="等你挑一个"), t)
        advance(a, 20)
        t = now()
        a.router.ingest(PetEvent(t, "test", "B", Kind.task_start, detail="写个脚本"), t)
        a.router.ingest(PetEvent(t, "test", "B", Kind.activity_start, event_id="b1",
                                 activity=PetState.write_file, detail="编辑 backup.py"), t)
        advance(a, 60)
        # 她跟着“等你回答”的 A；B 挂一张卡在气泡上面。
        self.assertEqual(a.router.focused_session, "A")
        self.assertEqual([c.session for c in a.cards_hold.value], ["B"])
        self.assertTrue(a.cards.visible)
        self.assertLessEqual(a.cards.y + a.cards.height, a.bubble.y)
        self.assertAlmostEqual(a.cards.x + a.cards.width / 2, a.pet.x + a.pet_size[0] / 2, delta=2)

        # 点卡片正文：去那条聊天，卡收起。
        fake_win32.CURSOR[:] = [a.cards.x + 40, a.cards.y + a.cards.height // 2]
        a._cards_proc(a.cards.hwnd, fake_win32.WM_LBUTTONUP, 0, 0)
        self.assertEqual(fake_win32.OPENED_URLS, ["claude://code/continue?session=local_b"])
        self.assertEqual(a.cards_hold.value, [])

    def test_cards_can_be_turned_off_in_the_menu(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        t = now()
        for session, detail in (("A", "改登录页"), ("B", "写个脚本")):
            a.router.ingest(PetEvent(t, "test", session, Kind.task_start, detail=detail), t)
            a.router.ingest(PetEvent(t, "test", session, Kind.activity_start, event_id=session,
                                     activity=PetState.write_file), t)
        advance(a, 60)
        self.assertTrue(a.cards_hold.value)
        a.show_menu()
        by_text = {i.text: i for i in fake_win32.LAST_MENU}
        self.assertTrue(by_text["头顶显示别的聊天"].checked)
        by_text["头顶显示别的聊天"].action()
        self.assertFalse(a.show_cards)
        self.assertEqual(a.cards_hold.value, [])

    def test_scale_menu_covers_fifty_to_two_hundred_in_five_percent_steps(self):
        a = make_app()
        a.show_menu()
        size_menu = {i.text: i for i in
                     {i.text: i for i in fake_win32.LAST_MENU}["大小"].submenu}
        self.assertIn("50%", size_menu)
        self.assertIn("200%", size_menu)
        size_menu["放大一点（+5%）"].action()
        self.assertAlmostEqual(a.user_scale, 1.05)
        for _ in range(30):
            a.show_menu()
            rows = {i.text: i for i in
                    {i.text: i for i in fake_win32.LAST_MENU}["大小"].submenu}
            if rows["放大一点（+5%）"].enabled:
                rows["放大一点（+5%）"].action()
        # 顶到上限就停住，不会越界。
        self.assertAlmostEqual(a.user_scale, 2.0)
        a.settings.set("scale", 99.0)
        self.assertAlmostEqual(a.user_scale, 2.0)
        a.settings.set("scale", "坏掉的设置")
        self.assertAlmostEqual(a.user_scale, 1.0)

    def test_tray_tooltip_follows_the_state(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        t = now()
        a.router.ingest(PetEvent(t, "test", "s", Kind.task_start), t)
        a.router.ingest(PetEvent(t, "test", "s", Kind.activity_start, event_id="t",
                                 activity=PetState.verify, detail="$ pytest"), t)
        advance(a, 80)
        from yukio.router import state_name
        self.assertEqual(a.tray.tip, "雪绪：%s" % state_name(PetState.verify))


if __name__ == "__main__":
    unittest.main()


class TrayTests(unittest.TestCase):
    def test_taskbar_restart_re_adds_the_icon(self):
        a = make_app()
        a.tray.added = False
        a._on_control_message(fake_win32.TASKBAR_CREATED, 0, 0)
        self.assertTrue(a.tray.added)

    def test_tray_click_opens_the_menu(self):
        a = make_app()
        fake_win32.LAST_MENU[:] = []
        a._on_control_message(fake_win32.WM_TRAY, 0, fake_win32.WM_RBUTTONUP)
        self.assertTrue(fake_win32.LAST_MENU)

    def test_second_launch_asks_the_running_one_to_show_its_menu(self):
        a = make_app()
        fake_win32.LAST_MENU[:] = []
        a._on_control_message(a.control.show_menu_message, 0, 0)
        self.assertTrue(fake_win32.LAST_MENU)


class StateFileTests(unittest.TestCase):
    def test_state_file_records_the_current_pose(self):
        from yukio.events import Kind, PetEvent
        path = os.path.join(tempfile.mkdtemp(prefix="yukio-state-"), "state.txt")
        os.environ["YUKIO_STATE_FILE"] = path
        try:
            a = make_app()
            t = now()
            a.router.ingest(PetEvent(t, "test", "s", Kind.task_start, detail="改一改"), t)
            a.router.ingest(PetEvent(t, "test", "s", Kind.activity_start, event_id="t",
                                     activity=PetState.write_file, detail="编辑 login.py"), t)
            advance(a, 80)
        finally:
            os.environ.pop("YUKIO_STATE_FILE", None)
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines[0], "write_file")
        self.assertEqual(lines[2], "编辑 login.py")


class SettingsTests(unittest.TestCase):
    def test_settings_file_with_a_bom_still_loads(self):
        """Windows 上的记事本和 PowerShell 写 UTF-8 会带 BOM，不能因此把设置悄悄重置。"""
        from yukio.settings import Settings
        path = os.path.join(tempfile.mkdtemp(prefix="yukio-bom-"), "settings.json")
        with open(path, "wb") as fh:
            fh.write(b"\xef\xbb\xbf" + b'{"scale": 1.5, "follow": false}')
        s = Settings(path)
        self.assertEqual(s.get("scale"), 1.5)
        self.assertFalse(s.get("follow"))

    def test_broken_settings_fall_back_to_defaults(self):
        from yukio.settings import Settings
        path = os.path.join(tempfile.mkdtemp(prefix="yukio-bad-"), "settings.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{ 这不是 JSON")
        s = Settings(path)
        self.assertEqual(s.get("scale"), 1.0)


class FirstRunTests(unittest.TestCase):
    def test_first_run_without_any_agent_plays_the_demo(self):
        """刚下载的人可能两个工具都没装：先演一遍，别让她干坐着。"""
        a = make_app(first_run=True)
        self.assertIsNotNone(a.demo)
        advance(a, 40)
        self.assertNotEqual(a.shown_state, PetState.idle)

    def test_second_run_does_not(self):
        a = make_app(first_run=True)
        # 第一次跑完会写下设置；拿同一份设置再开一次就不该再演示。
        again = object.__new__(app_module.PetApp)
        original = app_module.Settings
        try:
            app_module.Settings = lambda: original(a.settings.path)
            again.__init__([])
        finally:
            app_module.Settings = original
        self.assertIsNone(again.demo)

    def test_an_available_source_means_no_demo(self):
        class FakeSource:
            label = "假来源"
            available = True
            status = type("S", (), {"events_received": 0})()

            def poll(self, now):
                return []

        a = make_app(first_run=True, sources=[FakeSource()])
        self.assertIsNone(a.demo)
