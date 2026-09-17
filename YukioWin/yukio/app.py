"""桌面播放器本体：窗口、拖动、托盘菜单、30 Hz 主循环。

只在 Windows 上运行。其余平台上用 --check / --snapshot / --bubble / --replay / --watch
可以离线检查素材、气泡排版与事件解析。
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from typing import List, Optional, Tuple

from .catalog import AnimationCatalog, RUNNING_LEFT_ID, RUNNING_RIGHT_ID, SpriteTimeline, assets_root
from .demo import DEMO_DURATION_MS, demo_steps
from .events import PetState
from .router import ActivityRouter, HeldValue
from .settings import Settings
from .sources import app_data_dir, default_sources
from .sprites import SpriteLibrary

FRAME_MS = 33          # 约 30 Hz：小幅动作一帧 33–67 ms，眨眼 50–110 ms，都能按时换帧
POLL_EVERY_TICKS = 8   # 约每 0.27 秒读一次会话记录
BUBBLE_FADE_MS = 180.0
PET_W, PET_H = 192, 208


def now_ms() -> float:
    return time.time() * 1000.0


class PetApp:
    def __init__(self, argv: List[str]):
        from . import win32
        self.win32 = win32
        self.argv = argv
        self.settings = Settings()
        root = assets_root()
        if not root:
            raise SystemExit("找不到素材目录 Assets（可用 YUKIO_ASSETS 指定）")
        self.catalog = AnimationCatalog.load(root)
        self.library = SpriteLibrary(self.catalog, root)
        self.sources = default_sources(self.settings.get("source"))

        start = now_ms()
        self.router = ActivityRouter(now=start)
        # 先恢复“此刻在做什么”，再显示窗口：第一帧就是正确动作。
        for source in self.sources:
            for e in source.poll(start):
                self.router.ingest(e, min(e.ts, start))
        self.router.settle(start)

        self.shown_state = self.router.displayed if self.follow else PetState.idle
        self.timeline = SpriteTimeline(self.catalog.spec(self.shown_state), start)
        self.run_timeline: Optional[SpriteTimeline] = None
        self.running_right = True
        self._direction_accum = 0.0
        self._direction_decided = False
        self._painted: Optional[Tuple[str, int, int, int]] = None

        self.bubble_hold = HeldValue(None, min_hold_ms=1200)
        self._bubble_image = None
        self._bubble_alpha = 0.0
        self._bubble_target = 0.0
        self._bubble_placed_for_drag = False

        self.demo = None            # (start_ms, steps, next_index, router)
        self.tick_count = 0
        # 设了 YUKIO_STATE_FILE 就把当前动作写进这个文件（冒烟测试和排查用，平时不写）。
        self._state_file = os.environ.get("YUKIO_STATE_FILE") or None
        self._dragging = False
        self._drag_pending = False
        self._drag_start = (0, 0)
        self._origin_start = (0, 0)
        self._last_mouse_x = 0

        self.control = win32.ControlWindow(self._on_control_message)
        self.pet = win32.LayeredWindow("YukioPet", wnd_proc=self._pet_proc)
        self.bubble = win32.LayeredWindow("YukioBubble", click_through=True)
        self.tray = win32.TrayIcon(self.control.hwnd, self._tray_icon_path(), self._tray_tip())

        x, y = self._restored_origin()
        self.pet.x, self.pet.y = x, y
        self._render(now_ms())
        self._write_state_file()
        if "--demo" in argv or self._should_greet():
            self.start_demo()
        # 记下“来过一次”，下次就不再自动演示了。
        self.settings.save()

    def _should_greet(self) -> bool:
        """第一次打开、又没有任何会话记录可跟时，先自己演一遍。

        不然刚下载的人双击完只看到一个坐着不动的小人，会以为坏了。
        """
        if os.path.exists(self.settings.path):
            return False
        return not any(getattr(source, "available", False) for source in self.sources)

    # MARK: 设置

    @property
    def follow(self) -> bool:
        return bool(self.settings.get("follow", True))

    @property
    def show_bubble(self) -> bool:
        return bool(self.settings.get("showBubble", True))

    @property
    def user_scale(self) -> float:
        try:
            return float(self.settings.get("scale", 1.0))
        except (TypeError, ValueError):
            return 1.0

    @property
    def scale(self) -> float:
        """实际缩放 = 用户选的大小 × 屏幕缩放（125% 的屏幕上素材按 1.25 倍画，不糊）。"""
        return self.user_scale * self.win32.dpi_scale(getattr(getattr(self, "pet", None), "hwnd", None))

    @property
    def pet_size(self) -> Tuple[int, int]:
        s = self.scale
        return (max(1, int(round(PET_W * s))), max(1, int(round(PET_H * s))))

    # MARK: 位置

    def _default_origin(self) -> Tuple[int, int]:
        w, h = self.pet_size
        left, top, right, bottom = self.win32.work_area()
        return (right - w - int(24 * self.scale), bottom - h - int(12 * self.scale))

    def _restored_origin(self) -> Tuple[int, int]:
        x, y = self.settings.get("originX"), self.settings.get("originY")
        if x is None or y is None:
            return self._default_origin()
        w, h = self.pet_size
        left, top, right, bottom = self.win32.work_area(int(x) + w // 2, int(y) + h // 2)
        # 显示器拔掉或排列变化后，保存的位置可能已不在任何屏幕上。
        if int(x) + w < left or int(x) > right or int(y) + h < top or int(y) > bottom:
            return self._default_origin()
        return (int(x), int(y))

    def _clamp_to_screen(self) -> None:
        w, h = self.pet_size
        cx, cy = self.pet.x + w // 2, self.pet.y + h // 2
        left, top, right, bottom = self.win32.work_area(cx, cy)
        x = min(max(self.pet.x, left), max(left, right - w))
        y = min(max(self.pet.y, top), max(top, bottom - h))
        if (x, y) != (self.pet.x, self.pet.y):
            self.pet.move(x, y)

    def _save_position(self) -> None:
        self.settings.set("originX", int(self.pet.x))
        self.settings.set("originY", int(self.pet.y))

    # MARK: 画面

    def _render(self, now: float) -> None:
        timeline = self.run_timeline or self.timeline
        spec_id, index = timeline.spec.id, timeline.frame
        w, h = self.pet_size
        key = (spec_id, index, w, h)
        if key == self._painted:
            return
        frame = self.library.frame(spec_id, index)
        image = frame.image
        if (w, h) != image.size:
            from PIL import Image
            image = image.resize((w, h), Image.BILINEAR)
        self.pet.show_image(image, self.pet.x, self.pet.y)
        self._painted = key

    def _position_bubble(self) -> None:
        from .bubble import BubbleLayout
        self._bubble_placed_for_drag = self._dragging
        if self._bubble_image is None:
            return
        s = self.scale
        size_pt = (self._bubble_image.size[0] / s, self._bubble_image.size[1] / s)
        # 跑动时头发扬起，气泡抬高，免得压住头顶；松手后回到坐姿的高度。
        head_top = self.library.running_top_inset if self._dragging else self.library.head_top_inset
        w, h = self.pet_size
        x, y = BubbleLayout.origin(size_pt, (self.pet.x / s, self.pet.y / s, w / s, h / s), head_top)
        x, y = x * s, y * s
        left, top, right, bottom = self.win32.work_area(self.pet.x + w // 2, self.pet.y + h // 2)
        bw, bh = self._bubble_image.size
        x = min(max(x, left + 4), max(left, right - bw - 4))
        y = max(y, top + 2)
        self.bubble.x, self.bubble.y = int(x), int(y)

    def _update_bubble(self, now: float) -> None:
        from .bubble import BubbleLayout
        if self._dragging != self._bubble_placed_for_drag:
            self._position_bubble()
            self._paint_bubble()
        source = self.demo[3] if self.demo else (self.router if self.follow else None)
        line = source.status_line(now) if (self.show_bubble and source) else None
        visibility_changed = (line is None) != (self.bubble_hold.value is None)
        if self.bubble_hold.update(line, now, immediate=visibility_changed):
            if self.bubble_hold.value is not None:
                self._bubble_image = BubbleLayout(self.bubble_hold.value, self.scale).render()
                self._bubble_target = 1.0
                self._position_bubble()
                self._paint_bubble()
            else:
                self._bubble_target = 0.0
        # 淡入淡出
        if self._bubble_alpha != self._bubble_target:
            step = FRAME_MS / BUBBLE_FADE_MS
            if self._bubble_alpha < self._bubble_target:
                self._bubble_alpha = min(self._bubble_target, self._bubble_alpha + step)
            else:
                self._bubble_alpha = max(self._bubble_target, self._bubble_alpha - step)
            self._paint_bubble()

    def _paint_bubble(self) -> None:
        if self._bubble_image is None or self._bubble_alpha <= 0.01:
            self.bubble.hide()
            return
        image = self._bubble_image
        if self._bubble_alpha < 0.99:
            image = image.copy()
            alpha = image.getchannel("A").point(lambda v, k=self._bubble_alpha: int(v * k))
            image.putalpha(alpha)
        self.bubble.show_image(image, self.bubble.x, self.bubble.y)

    # MARK: 主循环

    def tick(self) -> None:
        now = now_ms()
        self.tick_count += 1
        if self.tick_count % POLL_EVERY_TICKS == 0:
            # 事件始终进入路由器；暂停跟随只影响显示。
            for source in self.sources:
                try:
                    for e in source.poll(now):
                        self.router.ingest(e, min(e.ts, now))
                except Exception:
                    traceback.print_exc()
        self.router.tick(now)

        if self.demo:
            start, steps, index, router = self.demo
            elapsed = now - start
            while index < len(steps) and steps[index].offset_ms <= elapsed:
                event = steps[index].event
                event.ts = now
                router.ingest(event, now)
                index += 1
            router.tick(now)
            self.demo = (start, steps, index, router)
            if elapsed > DEMO_DURATION_MS:
                self.stop_demo()

        target = self.demo[3].displayed if self.demo else (self.router.displayed if self.follow else PetState.idle)
        if target != self.shown_state:
            self.shown_state = target
            self.timeline = SpriteTimeline(self.catalog.spec(target), now)
            self.tray.set_tip(self._tray_tip())
            self._write_state_file()
        self.timeline.advance(now)
        if self.run_timeline:
            self.run_timeline.advance(now)
        self._render(now)
        self._update_bubble(now)

    def _write_state_file(self) -> None:
        if not self._state_file:
            return
        source = self.demo[3] if self.demo else (self.router if self.follow else None)
        line = source.status_line(now_ms()) if source else None
        try:
            with open(self._state_file, "w", encoding="utf-8") as fh:
                fh.write("%s\n%s\n%s\n" % (self.shown_state.value,
                                             self.catalog.label(self.shown_state),
                                             line.current if line else ""))
        except OSError:
            pass

    def run(self) -> int:
        self.control.start_timer(FRAME_MS)
        try:
            return self.win32.run_message_loop()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        try:
            self.control.stop_timer()
            self.tray.remove()
            self.bubble.destroy()
            self.pet.destroy()
            self.control.destroy()
        except Exception:
            pass

    # MARK: 消息

    def _on_control_message(self, msg: int, wparam: int, lparam: int) -> Optional[int]:
        w = self.win32
        control = getattr(self, "control", None)
        if control is None:
            # CreateWindowEx 建窗口的过程中就会发消息进来，这时 __init__ 还没走完。
            return None
        if msg == w.WM_TIMER:
            try:
                self.tick()
            except Exception:
                traceback.print_exc()
            return 0
        if msg == w.WM_TRAY:
            event = w.loword(lparam)
            if event in (w.WM_RBUTTONUP, w.WM_LBUTTONUP, w.WM_LBUTTONDBLCLK):
                self.show_menu()
            return 0
        if msg == getattr(w, "TASKBAR_CREATED", -1):
            tray = getattr(self, "tray", None)
            if tray is not None:
                tray.re_add()
            return 0
        if msg == control.show_menu_message:
            # 又双击了一次 Yukio.exe：把菜单弹出来（而不是再开一只）。
            self.show_menu()
            return 0
        if msg in (w.WM_DESTROY, w.WM_CLOSE):
            w.quit_loop()
            return 0
        return None

    def _pet_proc(self, hwnd, msg, wparam, lparam):
        w = self.win32
        if getattr(self, "pet", None) is None:
            return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        try:
            if msg == w.WM_LBUTTONDOWN:
                w.user32.SetCapture(hwnd)
                self._drag_pending = True
                self._dragging = False
                self._drag_start = w.cursor_pos()
                self._last_mouse_x = self._drag_start[0]
                self._origin_start = (self.pet.x, self.pet.y)
                return 0
            if msg == w.WM_MOUSEMOVE and self._drag_pending:
                mx, my = w.cursor_pos()
                dx, dy = mx - self._drag_start[0], my - self._drag_start[1]
                if not self._dragging and (dx * dx + dy * dy) > 9:
                    self._dragging = True
                    self._direction_decided = False
                    self._direction_accum = 0.0
                    self._start_run(self.running_right)
                if self._dragging:
                    self.pet.move(self._origin_start[0] + dx, self._origin_start[1] + dy)
                    self._position_bubble()
                    self._paint_bubble()
                    self._drag_moved(mx - self._last_mouse_x)
                    self._last_mouse_x = mx
                return 0
            if msg == w.WM_LBUTTONUP:
                w.user32.ReleaseCapture()
                was_dragging = self._dragging
                self._drag_pending = False
                self._dragging = False
                if was_dragging:
                    self.run_timeline = None
                    self._painted = None
                    self._clamp_to_screen()
                    self._save_position()
                    self._position_bubble()
                    self._paint_bubble()
                    self._render(now_ms())
                return 0
            if msg in (w.WM_RBUTTONUP, w.WM_LBUTTONDBLCLK):
                self.show_menu()
                return 0
            if msg == w.WM_SETCURSOR and self._dragging:
                w.user32.SetCursor(w.user32.LoadCursorW(None, w.c_void_p(w.IDC_SIZEALL)))
                return 1
        except Exception:
            traceback.print_exc()
        return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # MARK: 拖动时的跑动

    def _start_run(self, right: bool) -> None:
        self.running_right = right
        spec = self.catalog.specs[RUNNING_RIGHT_ID if right else RUNNING_LEFT_ID]
        self.run_timeline = SpriteTimeline(spec, now_ms())
        self._render(now_ms())

    def _drag_moved(self, dx: float) -> None:
        if dx == 0:
            return
        if not self._direction_decided:
            self._direction_decided = True
            if (dx > 0) != self.running_right:
                self._start_run(dx > 0)
            return
        # 反向移动累计超过 6 点才转身，避免手抖来回翻转。
        threshold = 6 * self.scale
        if self.running_right:
            self._direction_accum = min(0.0, self._direction_accum + dx)
            if self._direction_accum < -threshold:
                self._direction_accum = 0.0
                self._start_run(False)
        else:
            self._direction_accum = max(0.0, self._direction_accum + dx)
            if self._direction_accum > threshold:
                self._direction_accum = 0.0
                self._start_run(True)

    # MARK: 托盘与菜单

    def _tray_icon_path(self) -> Optional[str]:
        path = os.path.join(app_data_dir(), "tray.ico")
        try:
            if not os.path.exists(path):
                avatar = self.library.avatar_image(256)
                if avatar is None:
                    return None
                os.makedirs(os.path.dirname(path), exist_ok=True)
                avatar.save(path, format="ICO",
                            sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64)])
        except (OSError, ValueError):
            return None
        return path

    def _tray_tip(self) -> str:
        return "雪绪：%s" % self.catalog.label(self.shown_state)

    def _source_label(self) -> str:
        names = {"auto": "自动（Deep Code 与 Claude Code 都跟）",
                 "deepcode": "只跟 Deep Code（DeepSeek）",
                 "claude": "只跟 Claude Code"}
        return names.get(self.settings.get("source"), "自动")

    def show_menu(self) -> None:
        w = self.win32
        Item, SEP = w.MenuItem, w.SEPARATOR
        items: List[w.MenuItem] = [Item("雪绪 · %s" % self.catalog.label(self.shown_state), None)]
        if self.demo:
            items.append(Item("正在播放模拟演示（不是真实活动）", None))
        elif not self.follow:
            items.append(Item("已暂停跟随，保持空闲", None))
        else:
            found = 0
            for source in self.sources:
                if getattr(source, "available", False):
                    found += 1
                    received = getattr(source.status, "events_received", 0)
                    items.append(Item("跟随 %s · 已收到 %d 个事件" % (source.label, received), None))
            if not found:
                missing = [(s.label, getattr(s, "projects_dir", "")) for s in self.sources
                           if getattr(s, "projects_dir", "")]
                for label, where in missing[:2]:
                    items.append(Item("没找到 %s 的记录：%s" % (label, where), None))
                if not missing:
                    items.append(Item("没有可跟随的来源", None))
            snap = self.router.snapshot()
            if snap.focused_session:
                items.append(Item("会话 %s… · %s · 未完成工具 %d" %
                                  (snap.focused_session[:8], "进行中" if snap.task_active else "已结束",
                                   snap.open_tools), None))
        items.append(SEP)
        if self.demo:
            items.append(Item("停止模拟演示", self.stop_demo))
        else:
            items.append(Item("播放模拟演示", self.start_demo))
        items.append(Item("跟随 AI 活动", self._toggle_follow, checked=self.follow))
        items.append(Item("头顶显示任务", self._toggle_bubble, checked=self.show_bubble))
        items.append(Item("跟随对象", None, submenu=[
            Item("自动（哪个有动静跟哪个）", lambda: self._set_source("auto"),
                 checked=self.settings.get("source") == "auto"),
            Item("Deep Code（DeepSeek）", lambda: self._set_source("deepcode"),
                 checked=self.settings.get("source") == "deepcode"),
            Item("Claude Code", lambda: self._set_source("claude"),
                 checked=self.settings.get("source") == "claude"),
        ]))
        items.append(Item("大小", None, submenu=[
            Item("%d%%" % int(s * 100), lambda s=s: self._set_scale(s),
                 checked=abs(self.user_scale - s) < 0.01)
            for s in (1.0, 1.25, 1.5, 2.0)]))
        items.append(Item("回到屏幕右下角", self._reset_position))
        items.append(SEP)
        items.append(Item("退出雪绪", self.quit))
        w.show_menu(self.control.hwnd, items)

    def _toggle_follow(self) -> None:
        self.settings.set("follow", not self.follow)

    def _toggle_bubble(self) -> None:
        self.settings.set("showBubble", not self.show_bubble)

    def _set_source(self, which: str) -> None:
        self.settings.set("source", which)
        self.sources = default_sources(which)
        now = now_ms()
        for source in self.sources:
            for e in source.poll(now):
                self.router.ingest(e, min(e.ts, now))

    def _set_scale(self, scale: float) -> None:
        old_w, old_h = self.pet_size
        self.settings.set("scale", scale)
        new_w, new_h = self.pet_size
        # 以脚下中点为锚：缩放后落脚点不跳。
        self.pet.x = int(self.pet.x + (old_w - new_w) / 2)
        self.pet.y = int(self.pet.y + (old_h - new_h))
        self._painted = None
        self._clamp_to_screen()
        self._save_position()
        self._render(now_ms())
        self.bubble_hold.value = None      # 让气泡按新比例重画
        self._bubble_image = None
        self._bubble_alpha = 0.0
        self.bubble.hide()

    def _reset_position(self) -> None:
        x, y = self._default_origin()
        self.pet.move(x, y)
        self._save_position()
        self._position_bubble()
        self._paint_bubble()

    def start_demo(self) -> None:
        now = now_ms()
        self.demo = (now, demo_steps("demo", now), 0, ActivityRouter(now=now))

    def stop_demo(self) -> None:
        self.demo = None

    def quit(self) -> None:
        self.win32.quit_loop()


def _redirect_output_when_frozen() -> Optional[str]:
    """打包成 exe 后没有终端：把报错写进 %LOCALAPPDATA%\\Yukio\\error.log。"""
    if not getattr(sys, "frozen", False):
        return None
    path = os.path.join(app_data_dir(), "error.log")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        stream = open(path, "a", encoding="utf-8", buffering=1)
        stream.write("\n===== %s 启动 =====\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        sys.stdout = stream
        sys.stderr = stream
        return path
    except OSError:
        return None


def run_app(argv: List[str]) -> int:
    if os.name != "nt":
        sys.stderr.write(
            "桌面播放器只能在 Windows 上运行。\n"
            "在 macOS / Linux 上可以用这些模式离线检查：\n"
            "  python run.py --check\n"
            "  python run.py --snapshot out.png\n"
            "  python run.py --bubble out.png\n"
            "  python run.py --replay 会话.jsonl [--with-bubble]\n"
            "  python run.py --watch 60\n"
            "（macOS 上的雪绪请用仓库里的 YukioPlayer，那是原生 Swift 版。）\n")
        return 2
    from . import win32
    log_path = _redirect_output_when_frozen()
    win32.set_dpi_aware()
    if "--allow-multiple" not in argv and win32.already_running():
        # 已经有一只在跑：让她弹出菜单，自己退出。
        win32.ask_running_instance_to_show_menu()
        return 0
    try:
        app = PetApp(argv)
    except Exception as exc:
        traceback.print_exc()
        sys.stderr.write("雪绪启动失败：%s\n" % exc)
        win32.message_box("雪绪没能启动：\n\n%s\n\n%s" %
                          (exc, ("详细报错写在 " + log_path) if log_path
                           else "从命令行跑 python run.py 可以看到完整报错"))
        return 1
    return app.run()
