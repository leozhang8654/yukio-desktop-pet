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


def make_app(argv=None, dpi=1.0, **overrides):
    fake_win32.QUIT[:] = []
    fake_win32.CURSOR[:] = [0, 0]
    fake_win32.DPI = dpi
    CLOCK[0] = 1_780_000_000_000.0
    app_module.now_ms = now
    settings_path = os.path.join(tempfile.mkdtemp(prefix="yukio-test-"), "settings.json")
    application = object.__new__(app_module.PetApp)
    # 用临时设置文件，不碰用户自己的设置；来源用空列表，事件由测试直接喂。
    original_settings = Settings
    try:
        app_module.Settings = lambda: original_settings(settings_path)
        app_module.default_sources = lambda which: []
        application.__init__(argv or [])
    finally:
        app_module.Settings = original_settings
    for key, value in overrides.items():
        application.settings.set(key, value)
    return application


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

    def test_drag_moves_her_and_turns_around(self):
        a = make_app()
        start_x, start_y = a.pet.x, a.pet.y
        fake_win32.CURSOR[:] = [start_x + 50, start_y + 50]
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONDOWN, 0, 0)
        self.assertTrue(fake_win32.user32.captured)
        # 往左拖 40 点
        fake_win32.CURSOR[0] -= 40
        a._pet_proc(a.pet.hwnd, fake_win32.WM_MOUSEMOVE, 0, 0)
        self.assertTrue(a._dragging)
        self.assertEqual(a.pet.x, start_x - 40)
        self.assertFalse(a.running_right)
        self.assertEqual(a.run_timeline.spec.id, "running-left")
        # 再往右拖，超过阈值才转身
        fake_win32.CURSOR[0] += 40
        a._pet_proc(a.pet.hwnd, fake_win32.WM_MOUSEMOVE, 0, 0)
        self.assertTrue(a.running_right)
        a._pet_proc(a.pet.hwnd, fake_win32.WM_LBUTTONUP, 0, 0)
        self.assertFalse(a._dragging)
        self.assertIsNone(a.run_timeline)
        self.assertFalse(fake_win32.user32.captured)
        self.assertEqual(a.settings.get("originX"), a.pet.x)

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
        source_menu = {i.text: i for i in by_text["跟随对象"].submenu}
        source_menu["Deep Code（DeepSeek）"].action()
        self.assertEqual(a.settings.get("source"), "deepcode")
        by_text["回到屏幕右下角"].action()
        self.assertEqual((a.pet.x, a.pet.y), a._default_origin())
        by_text["退出雪绪"].action()
        self.assertTrue(fake_win32.QUIT)

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

    def test_tray_tooltip_follows_the_state(self):
        from yukio.events import Kind, PetEvent
        a = make_app()
        t = now()
        a.router.ingest(PetEvent(t, "test", "s", Kind.task_start), t)
        a.router.ingest(PetEvent(t, "test", "s", Kind.activity_start, event_id="t",
                                 activity=PetState.verify, detail="$ pytest"), t)
        advance(a, 80)
        self.assertEqual(a.tray.tip, "雪绪：%s" % a.catalog.label(PetState.verify))


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
