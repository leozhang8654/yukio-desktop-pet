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

from .catalog import AnimationCatalog, HELD_ID, SpriteTimeline, assets_root
from .blink import BlinkClock
from .chatlinks import ChatLinks
from .demo import DEMO_DURATION_MS, demo_steps
from .events import PetState
from .l10n import set_language, tr
from .hang import SETTLE_LIMIT_MS, HangGeometry, HangSwing, Tuning as HangTuning
from .router import ActivityRouter, HeldValue, held_name, state_name
from .settings import Settings
from .reminders import ReminderStore
from .sources import app_data_dir, default_sources
from .sprites import SpriteLibrary

FRAME_MS = 33          # 约 30 Hz：小幅动作一帧 33–67 ms，眨眼 50–110 ms，都能按时换帧
POLL_EVERY_TICKS = 8   # 约每 0.27 秒读一次会话记录
OPEN_CHAT_EVERY_TICKS = 60   # 约每 2 秒看一次"此刻开着哪条聊天"
#: 桌面版 Claude 的可执行文件名。它在最前面、且选中的就是那条聊天时，那条不举牌。
CLAUDE_DESKTOP_EXE = "Claude.exe"
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
        self.reminders = ReminderStore(os.environ.get("YUKIO_REMINDER_FILE") or
                                       os.path.join(os.path.dirname(self.settings.path), "reminders.json"))
        self.assistant = None
        self._ticking = False
        self._next_reminder_tick = 0.0
        self._assistant_only = "--assistant-only" in argv
        set_language(self.settings.get("language"))   # 先定语言，回放会话记录时生成的说明文字才是对的语言
        root = assets_root()
        if not root:
            raise SystemExit("找不到素材目录 Assets（可用 YUKIO_ASSETS 指定）")
        self.catalog = AnimationCatalog.load(root)
        self.library = SpriteLibrary(self.catalog, root)
        self.sources = default_sources(self.settings.get("source"))
        self.links = ChatLinks()

        start = now_ms()
        self.router = ActivityRouter(now=start)
        # 先恢复“此刻在做什么”，再显示窗口：第一帧就是正确动作。
        for source in self.sources:
            for e in source.poll(start):
                self.router.ingest(e, min(e.ts, start))
        self.router.settle(start)

        self.shown_state = self.router.displayed if self.follow else PetState.idle
        self.timeline = SpriteTimeline(self.catalog.spec(self.shown_state), start)
        initial_blink = self.timeline.spec.blink
        self.blink_clock = BlinkClock(initial_blink.seed if initial_blink else 11003, start)
        self.blink_level = 0
        #: 被大手拎着时的摆动与图条；都是 None 表示正常站／坐着。
        self.swing: Optional[HangSwing] = None
        self.held_timeline: Optional[SpriteTimeline] = None
        self.hang_geo: Optional[HangGeometry] = None
        #: 松手的时刻；晃停或超时后放回原来的动作。
        self._released_at: Optional[float] = None
        self._painted = None

        self.bubble_hold = HeldValue(None, min_hold_ms=1200)
        self._bubble_image = None
        self._bubble_alpha = 0.0
        self._bubble_target = 0.0
        self._bubble_placed_for_drag = False

        #: 头顶那摞“别的聊天”的卡。多一条少一条立刻生效，卡上的字跟气泡一样至少停留 1.2 秒。
        self.cards_hold = HeldValue([], min_hold_ms=1200)
        self.cards_layout = None
        self._cards_image = None
        self._cards_alpha = 0.0
        self._cards_target = 0.0
        #: “还有 N 条”展开着没有。
        self.cards_expanded = False

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
        # 卡片要能点，所以不是穿透窗口；卡与卡之间的缝隙靠分层窗口的透明像素穿透。
        self.cards = win32.LayeredWindow("YukioCards", wnd_proc=self._cards_proc)
        # 她身边那张问题卡：也要能点（选项、送出、打开聊天、✕）。
        self.question = win32.LayeredWindow("YukioQuestion", wnd_proc=self._question_proc)
        self.question_layout = None
        self._question_image = None
        self._question_alpha = 0.0
        self._question_target = 0.0
        self._question_signature = ""
        #: 此刻立在她身边的那道题（router.PendingQuestion）。
        self.shown_question = None
        #: 多选题里已经点中的那几项。
        self.picked_options = set()
        #: 按过 ✕ 的那次提问：这一轮先不在她这边答。
        self.question_dismissed_call = None
        #: 答案送出之后那行提示，下一道题清掉。
        self.answer_notice = None
        #: 真正收键盘输入的那个系统输入框（点了才建）。
        self.text_input = None
        self._delivery = None
        self._delivery_question = None
        #: 会话 → 深链（查一次要翻几百份记录，问题卡每帧都要问）。
        self._chat_url_cache = {}
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
    def show_cards(self) -> bool:
        return bool(self.settings.get("showCards", True))

    @property
    def show_question_card(self) -> bool:
        """她举着问号卡时，在身边立一张写着问题的卡、可以当场回答。

        关掉就还是老样子：只有问号卡，点她跳回聊天去答。
        """
        return bool(self.settings.get("showQuestionCard", True))

    @property
    def user_scale(self) -> float:
        return self.snap_scale(self.settings.get("scale", 1.0))

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
        if self.pet_hidden:
            self.pet.hide()
            return
        if self.swing is not None and self.hang_geo is not None and self.held_timeline is not None:
            self._render_hanging()
            return
        timeline = self.timeline
        spec_id, index = timeline.spec.id, timeline.frame
        w, h = self.pet_size
        key = (spec_id, index, self.blink_level, w, h)
        if key == self._painted:
            return
        frame = self.library.frame(spec_id, index, self.blink_level)
        source = frame.image
        image = source
        try:
            if (w, h) != source.size:
                from PIL import Image
                image = source.resize((w, h), Image.BILINEAR)
            # LayeredWindow 在返回前已经把像素复制进 DIB，可以马上释放 Pillow 图像。
            self.pet.show_image(image, self.pet.x, self.pet.y)
        finally:
            if image is not source:
                image.close()
            source.close()
        self._painted = key

    def _render_hanging(self) -> None:
        """被拎着的那一帧：绕抓手点转 angle 度，整张图按 sag 往下挪。

        坠下去时旋转中心仍是抓手那一点（相当于那截布被拉长了）。
        Pillow 的 rotate 正角是逆时针，在 y 向下的位图里正好等于「脚偏右」，
        和摆动里的约定一致（见 hang.rotate_point）。
        """
        from PIL import Image
        geo, swing, held = self.hang_geo, self.swing, self.held_timeline
        # 角度和下坠量量化到 0.5°／0.5 px：同一格里不重画，省掉一次旋转。
        key = (held.spec.id, held.frame, geo.panel_size,
               round(swing.angle_degrees * 2), round(swing.sag * 2))
        if key == self._painted:
            return
        frame = self.library.frame(held.spec.id, held.frame)
        sx, sy, sw, sh = geo.sprite_rect
        source = frame.image
        sprite = source
        canvas = None
        try:
            if (int(round(sw)), int(round(sh))) != source.size:
                sprite = source.resize((max(1, int(round(sw))), max(1, int(round(sh)))), Image.BILINEAR)
            canvas = Image.new("RGBA", geo.panel_size, (0, 0, 0, 0))
            canvas.alpha_composite(sprite, (int(round(sx)), int(round(sy + swing.sag))))
            if abs(swing.angle_degrees) > 0.01:
                rotated = canvas.rotate(swing.angle_degrees, resample=Image.BICUBIC, center=geo.pivot)
                canvas.close()
                canvas = rotated
            self.pet.show_image(canvas, self.pet.x, self.pet.y)
        finally:
            if canvas is not None:
                canvas.close()
            if sprite is not source:
                sprite.close()
            source.close()
        self._painted = key

    def _position_bubble(self) -> None:
        from .bubble import BubbleLayout
        self._bubble_placed_for_drag = self.swing is not None
        if self._bubble_image is None:
            return
        s = self.scale
        size_pt = (self._bubble_image.size[0] / s, self._bubble_image.size[1] / s)
        px, py, w, h = self._pet_rect()
        # 站着和坐着的头顶线不一样（待机是站姿，比坐着高一截），气泡贴各自那一段。
        head_top = self._head_top_points()
        x, y = BubbleLayout.origin(size_pt, (px / s, py / s, w / s, h / s), head_top)
        x, y = x * s, y * s
        left, top, right, bottom = self.win32.work_area(px + w // 2, py + h // 2)
        bw, bh = self._bubble_image.size
        x = min(max(x, left + 4), max(left, right - bw - 4))
        y = max(y, top + 2)
        self.bubble.x, self.bubble.y = int(x), int(y)

    def _pet_rect(self) -> Tuple[int, int, int, int]:
        """雪绪这会儿占的那块（像素）。被拎着时是那张更高的图，不是放大的窗口。"""
        if self.hang_geo is not None and self.swing is not None:
            sx, sy, sw, sh = self.hang_geo.sprite_rect
            return (int(self.pet.x + sx), int(self.pet.y + sy), int(round(sw)), int(round(sh)))
        w, h = self.pet_size
        return (self.pet.x, self.pet.y, w, h)

    def _head_top_points(self) -> float:
        """这会儿的头顶线（点）：气泡与卡叠贴着它放。"""
        if self.hang_geo is not None and self.swing is not None:
            # 被拎着时贴在被捏起的领口上方。
            return self.held_spec.hang.grip_y
        return self.library.head_top_inset_for(self.timeline.spec.id)

    def _update_bubble(self, now: float) -> None:
        from .bubble import BubbleLayout
        # 拎起和放下时各重新摆一次（图的高矮变了）。
        if (self.swing is not None) != self._bubble_placed_for_drag:
            self._position_bubble()
            self._paint_bubble()
            self._position_cards()
            self._position_question()
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
        if self.pet_hidden:
            self.bubble.hide()
            return
        if self._bubble_image is None or self._bubble_alpha <= 0.01:
            self.bubble.hide()
            return
        image = self._bubble_image
        if self._bubble_alpha < 0.99:
            image = image.copy()
            alpha = image.getchannel("A").point(lambda v, k=self._bubble_alpha: int(v * k))
            image.putalpha(alpha)
        self.bubble.show_image(image, self.bubble.x, self.bubble.y)

    # MARK: 点击举着的牌子：跳到对应的聊天

    def _pet_clicked(self) -> None:
        """举着牌子时点雪绪：打开这块牌子对应的那条聊天。

        勾选卡点完放下（那一轮已经结束）；问号卡不放下——问题还等着你答，
        卡片等你答完自己收。其余状态点击不做事。
        """
        now = now_ms()
        if self.demo:
            # 演示里没有真实会话可跳，只把牌子放下。
            self.demo[3].dismiss_completion(now)
            return
        if not self.follow:
            return
        if self.shown_state is PetState.task_complete:
            session = self.router.completed_session
            if session:
                self._open_chat(session)
                self.router.dismiss_completion(now)
            return
        if self.shown_state is PetState.question_for_user:
            session = self.router.asking_session
            if session:
                self._open_chat(session)

    def _open_chat(self, session: str) -> None:
        """用桌面版 Claude 注册的深链打开这条聊天。

        认不出会话时（终端里跑的 Claude Code、Deep Code 的会话）什么都不做，不乱跳到别的聊天。
        """
        try:
            url = self._chat_url(session)
        except Exception:
            traceback.print_exc()
            return
        if not url:
            return
        try:
            self.win32.open_url(url)
        except Exception:
            traceback.print_exc()

    # MARK: 头顶那摞别的聊天

    def _update_cards(self, now: float, immediate: bool = False) -> None:
        from .cardstack import COLLAPSED_COUNT, CardStackLayout
        # “头顶显示任务”是整块头顶任务 UI 的总开关；气泡关掉时，
        # 卡片和单独的“N more”也不应继续悬着。
        want = self.router.cards(now) if (self.show_bubble and self.show_cards and self.follow and not self.demo) else []
        if len(want) <= COLLAPSED_COUNT:
            self.cards_expanded = False
        # 多一条少一条立刻生效；只是卡上的字变了就按最短停留，免得一直闪。
        appeared = [c.session for c in want] != [c.session for c in self.cards_hold.value]
        if self.cards_hold.update(want, now, immediate=immediate or appeared):
            cards = self.cards_hold.value
            if not cards:
                self._cards_target = 0.0          # 内容留着，让它淡出去而不是瞬间消失
            else:
                self.cards_layout = CardStackLayout(cards, expanded=self.cards_expanded,
                                                    scale=self.scale)
                self._cards_image = self.cards_layout.render()
                self._cards_target = 1.0
                self._position_cards()
                self._paint_cards()
        self._fade_cards()

    def _position_cards(self) -> None:
        """雪绪挪了、变大小了、被拎起放下了：照当前这叠重摆一次。

        接着气泡往上叠；气泡关掉或没内容时，从头顶线开始。
        """
        from .cardstack import CardStackLayout
        if self.cards_layout is None or self._cards_image is None:
            return
        s = self.scale
        px, py, w, h = self._pet_rect()
        if self._bubble_image is not None and self._bubble_alpha > 0.01:
            bubble_top = self.bubble.y
        else:
            bubble_top = py + self._head_top_points() * s - 3 * s
        x, y = CardStackLayout.origin(self.cards_layout.size_pt,
                                      (px / s, py / s, w / s, h / s), bubble_top / s)
        x, y = x * s, y * s
        left, top, right, bottom = self.win32.work_area(px + w // 2, py + h // 2)
        cw, ch = self._cards_image.size
        x = min(max(x, left + 4), max(left, right - cw - 4))
        y = min(max(y, top + 4), max(top, bottom - ch - 4))
        self.cards.x, self.cards.y = int(x), int(y)

    def _paint_cards(self) -> None:
        if self.pet_hidden:
            self.cards.hide()
            return
        if self._cards_image is None or self._cards_alpha <= 0.01:
            self.cards.hide()
            return
        image = self._cards_image
        if self._cards_alpha < 0.99:
            image = image.copy()
            alpha = image.getchannel("A").point(lambda v, k=self._cards_alpha: int(v * k))
            image.putalpha(alpha)
        self.cards.show_image(image, self.cards.x, self.cards.y)

    def _fade_cards(self) -> None:
        if self._cards_alpha == self._cards_target:
            return
        step = FRAME_MS / BUBBLE_FADE_MS
        if self._cards_alpha < self._cards_target:
            self._cards_alpha = min(self._cards_target, self._cards_alpha + step)
        else:
            self._cards_alpha = max(self._cards_target, self._cards_alpha - step)
        self._paint_cards()

    def _cards_proc(self, hwnd, msg, wparam, lparam):
        """点卡片：正文＝打开那条聊天并收起，✕＝只收起，“还有 N 条”＝展开／收起。"""
        w = self.win32
        if getattr(self, "cards", None) is None or self.cards_layout is None:
            return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        try:
            if msg in (w.WM_LBUTTONUP, w.WM_RBUTTONUP):
                mx, my = w.cursor_pos()
                hit = self.cards_layout.hit(mx - self.cards.x, my - self.cards.y)
                if hit is None:
                    return 0
                if hit.kind == "expand":
                    self.cards_expanded = not self.cards_expanded
                    self._update_cards(now_ms(), immediate=True)
                    return 0
                card = self.cards_hold.value[hit.index] if hit.index < len(self.cards_hold.value) else None
                if card is None:
                    return 0
                if msg == w.WM_RBUTTONUP:
                    self._card_context_menu(card)
                    return 0
                self._card_tapped(card, open_chat=hit.kind == "card")
                return 0
        except Exception:
            traceback.print_exc()
        return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _card_tapped(self, card, open_chat: bool) -> None:
        if self.demo:
            return
        now = now_ms()
        if open_chat:
            self._open_chat(card.session)
        self.router.dismiss_card(card.session, now)
        self._update_cards(now, immediate=True)

    def _card_context_menu(self, card) -> None:
        w = self.win32
        Item = w.MenuItem
        w.show_menu(self.control.hwnd, [
            Item(card.title, None),
            Item(tr("Stop reminding about this chat", "不再提醒这条聊天"), lambda id=card.session: self._mute_chat(id)),
        ])

    def _mute_chat(self, session: str) -> None:
        self.router.mute_cards(session)
        self._update_cards(now_ms(), immediate=True)

    # MARK: 身边那张问题卡：在这儿直接回答

    def _update_question(self, now: float, immediate: bool = False) -> None:
        """她举着问号卡时，把那道题抄到身边这张卡上；问完就收起来。"""
        from .question import QuestionCardLayout
        source = self.demo[3] if self.demo else (self.router if self.follow else None)
        pending = source.asking_question if (source is not None and self.show_question_card) else None
        if pending is not None and pending.call_id == self.question_dismissed_call:
            pending = None
        previous = self.shown_question
        if (pending.call_id if pending else None) != (previous.call_id if previous else None):
            # 换了一道题（或问完了）：选中项、输入框、提示一律重来。
            self.picked_options = set()
            self.answer_notice = None
            if self.text_input is not None:
                self.text_input.clear()
                self.text_input.hide()
        self.shown_question = pending
        if pending is None:
            self._question_signature = ""
            self._question_target = 0.0
            if self.text_input is not None:
                self.text_input.hide()
            self._fade_question()
            return

        can_open = not self.demo and bool(self._chat_url(pending.session))
        signature = "%s|%s|%s|%s|%.2f" % (pending.call_id, sorted(self.picked_options),
                                          self.answer_notice or "", can_open, self.scale)
        if signature != self._question_signature or immediate:
            self._question_signature = signature
            self.question_layout = QuestionCardLayout(
                pending.question, picked=self.picked_options, can_open_chat=can_open,
                sent_notice=self.answer_notice, scale=self.scale)
            self._question_image = self.question_layout.render()
            self._question_target = 1.0
            self._position_question()
            self._paint_question()
        self._fade_question()

    def _position_question(self) -> None:
        """立在她身旁：右边放不下就换到左边，始终留在这块屏幕里。"""
        from .question import QuestionCardLayout
        if self.question_layout is None or self._question_image is None:
            return
        s = self.scale
        px, py, w, h = self._pet_rect()
        left, top, right, bottom = self.win32.work_area(px + w // 2, py + h // 2)
        x, y = QuestionCardLayout.origin(self.question_layout.size_pt,
                                         (px / s, py / s, w / s, h / s),
                                         (left / s, top / s, right / s, bottom / s))
        self.question.x, self.question.y = int(round(x * s)), int(round(y * s))
        self._place_text_input()

    def _paint_question(self) -> None:
        if self.pet_hidden:
            self.question.hide()
            if self.text_input is not None:
                self.text_input.hide()
            return
        if self._question_image is None or self._question_alpha <= 0.01:
            self.question.hide()
            return
        image = self._question_image
        if self._question_alpha < 0.99:
            image = image.copy()
            alpha = image.getchannel("A").point(lambda v, k=self._question_alpha: int(v * k))
            image.putalpha(alpha)
        self.question.show_image(image, self.question.x, self.question.y)

    def _fade_question(self) -> None:
        if self._question_alpha == self._question_target:
            return
        step = FRAME_MS / BUBBLE_FADE_MS
        if self._question_alpha < self._question_target:
            self._question_alpha = min(self._question_target, self._question_alpha + step)
        else:
            self._question_alpha = max(self._question_target, self._question_alpha - step)
        self._paint_question()
        if self._question_alpha <= 0.01:
            self.question.hide()

    def _ensure_text_input(self):
        """第一次要用时才建那个系统输入框。"""
        if self.text_input is None:
            try:
                self.text_input = self.win32.TextInput(on_commit=self._input_committed,
                                                       on_cancel=self._input_cancelled,
                                                       font_height=int(round(13 * self.scale)))
            except Exception:
                traceback.print_exc()
                return None
        return self.text_input

    def _place_text_input(self) -> None:
        """把输入框摆到卡片上画着框的那个位置（卡片挪了它也跟着挪）。"""
        box = self.text_input
        if box is None or not box.visible or self.question_layout is None:
            return
        rect = self.question_layout.input_rect
        if rect is None:
            box.hide()
            return
        x, y, w, h = rect
        box.move(self.question.x + x, self.question.y + y, w, h)

    def _input_committed(self, text: str) -> None:
        self._send_answer(text)

    def _input_cancelled(self) -> None:
        box = self.text_input
        if box is not None and box.text.strip():
            box.clear()          # 有字先清掉，空的时候再按才收卡
            return
        self._close_question()

    def _close_question(self) -> None:
        if self.shown_question is not None:
            self.question_dismissed_call = self.shown_question.call_id
        if self.text_input is not None:
            self.text_input.hide()
        self._update_question(now_ms(), immediate=True)

    def _question_proc(self, hwnd, msg, wparam, lparam):
        """点问题卡：选项＝直接答，输入框＝自己写一句，⏎＝送出，✕＝先不答。"""
        w = self.win32
        if getattr(self, "question", None) is None or self.question_layout is None:
            return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        try:
            if msg == w.WM_LBUTTONUP:
                mx, my = w.cursor_pos()
                hit = self.question_layout.hit(mx - self.question.x, my - self.question.y)
                if hit is None:
                    return 0
                if hit.kind == "option":
                    self._question_option_picked(hit.index)
                elif hit.kind == "input":
                    box = self._ensure_text_input()
                    if box is not None and self.question_layout.input_rect:
                        x, y, bw, bh = self.question_layout.input_rect
                        box.show(self.question.x + x, self.question.y + y, bw, bh)
                        box.focus()
                elif hit.kind == "send":
                    self._send_answer(self.text_input.text if self.text_input else "")
                elif hit.kind == "open_chat" and self.shown_question is not None:
                    self._open_chat(self.shown_question.session)
                elif hit.kind == "close":
                    self._close_question()
                return 0
        except Exception:
            traceback.print_exc()
        return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _question_option_picked(self, index: int) -> None:
        """点了一个选项：单选直接答出去，多选先记下来，写完（或按回车）一起送。"""
        pending = self.shown_question
        if pending is None or index >= len(pending.question.options):
            return
        if not pending.question.multi_select:
            self._send_answer(pending.question.options[index].label)
            return
        if index in self.picked_options:
            self.picked_options.discard(index)
        else:
            self.picked_options.add(index)
        self._update_question(now_ms(), immediate=True)

    def _composed_answer(self, typed: str) -> Optional[str]:
        """送出去的那句话：输入框里写了就用写的，没写就用点中的选项。"""
        text = (typed or "").strip()
        if text:
            return text
        pending = self.shown_question
        if pending is None or not self.picked_options:
            return None
        labels = [pending.question.options[i].label for i in sorted(self.picked_options)
                  if i < len(pending.question.options)]
        return tr(", ", "、").join(labels) if labels else None

    def _chat_url(self, session: str) -> Optional[str]:
        """这条聊天能不能跳回去（顺带给出深链）。

        查一次要翻几百份记录，问题卡每帧都要问一次「能不能跳」，所以按会话记住结果。
        """
        if self.router.session_source(session) == "codex":
            import uuid
            try:
                uuid.UUID(session)
                return "codex://threads/" + session
            except ValueError:
                return None
        if session in self._chat_url_cache:
            return self._chat_url_cache[session]
        try:
            url = self.links.chat_url(session)
        except Exception:
            url = None
        self._chat_url_cache[session] = url
        return url

    def _send_answer(self, typed: str) -> None:
        """替你把答案打进那条聊天里（见 answer.py：深链带到前面 → 逐字打 → 回车）。"""
        from .answer import AnswerDelivery, COPIED, TYPED
        pending = self.shown_question
        text = self._composed_answer(typed)
        if pending is None or not text or self.answer_notice is not None:
            return
        if self.demo:
            self.answer_notice = tr("Demo only - nothing was sent", "模拟演示，不会真的送出")
            self._update_question(now_ms(), immediate=True)
            return
        url = self._chat_url(pending.session)
        self.picked_options = set()
        if self.text_input is not None:
            self.text_input.clear()
            self.text_input.hide()
        self.answer_notice = tr("Sending...", "正在送过去…")
        self._update_question(now_ms(), immediate=True)
        if self._delivery is None:
            try:
                self._delivery = AnswerDelivery()
            except Exception:
                traceback.print_exc()
                self.answer_notice = tr("Copied - press Ctrl+V in the chat", "已复制 · 到聊天里 Ctrl+V")
                self._update_question(now_ms(), immediate=True)
                return

        def bring_to_front():
            if url:
                self.win32.open_url(url)

        # 终端里跑的会话（Deep Code、命令行 Claude）没有可跳的窗口：只复制。
        self._delivery_question = (pending.session, pending.call_id)
        target = ("Codex.exe" if url.startswith("codex://") else CLAUDE_DESKTOP_EXE) if url else None
        outcome = self._delivery.start(text, target, bring_to_front, now_ms())
        if outcome is not None:
            self._answer_finished(outcome)

    def _tick_delivery(self, now: float) -> None:
        if self._delivery is None or not self._delivery.busy:
            return
        current = self.shown_question
        if current is None or (current.session, current.call_id) != self._delivery_question:
            self._delivery.cancel()
            return
        outcome = self._delivery.tick(now)
        if outcome is not None:
            self._answer_finished(outcome)

    def _answer_finished(self, outcome: str) -> None:
        from .answer import TYPED, CLIPBOARD_CHANGED
        current = self.shown_question
        if current is None or (current.session, current.call_id) != self._delivery_question:
            return
        self.answer_notice = (tr("Typed · check the chat", "已输入并按回车 · 请在聊天中确认") if outcome == TYPED
                              else tr("Clipboard changed · answer in chat", "剪贴板已更改 · 请到聊天中回答") if outcome == CLIPBOARD_CHANGED
                              else tr("Copied - press Ctrl+V in the chat", "已复制 · 到聊天里 Ctrl+V"))
        self._update_question(now_ms(), immediate=True)

    # MARK: 主循环

    def _refresh_open_chat(self) -> None:
        """桌面版 Claude 就在最前面时，把它此刻选中的那条聊天告诉路由——那条不举牌。

        人没在看 Claude 时直接给 None，连记录都不用翻。读记录是文件操作，所以两秒才做一次；
        任何一步取不到就当"没开在眼前"，照常举牌。
        """
        try:
            if os.name != "nt":
                self.router.open_chat_session = None
                return
            from .win32 import foreground_process_name
            front = foreground_process_name()
            if not front or front.lower() != CLAUDE_DESKTOP_EXE.lower():
                self.router.open_chat_session = None
                return
            self.router.open_chat_session = self.links.focused_session()
        except Exception:
            self.router.open_chat_session = None

    def tick(self) -> None:
        # Tk.update() can dispatch Win32 timers; never reenter the app tick.
        if self._ticking:
            return
        self._ticking = True
        try:
            self._tick()
            if self.assistant is not None:
                self.assistant.pump()
        finally:
            self._ticking = False

    def _tick(self) -> None:
        now = now_ms()
        if now >= self._next_reminder_tick:
            self._next_reminder_tick = now + 1000
            fired = self.reminders.tick(now / 1000)
            if fired:
                if self.assistant is None:
                    self._ensure_assistant()
                if self.settings.get("assistantReminderSound", True):
                    try:
                        import winsound
                        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                    except (ImportError, RuntimeError):
                        pass
        self.tick_count += 1
        if self.tick_count % OPEN_CHAT_EVERY_TICKS == 0:
            self._refresh_open_chat()
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
            # 站着和坐着的头顶线不一样，气泡与卡叠跟着重贴。
            self._position_bubble()
            self._paint_bubble()
            self._position_cards()
            self._position_question()
        self.timeline.advance(now)
        blink = self.timeline.spec.blink
        if blink is not None:
            self.blink_clock.select_seed(blink.seed)
            self.blink_level = self.blink_clock.level(now, blink.levels)
        else:
            self.blink_level = 0
        if self.swing is not None:
            self._advance_hang(now)
        self._render(now)
        self._update_bubble(now)
        self._update_cards(now)
        self._update_question(now)
        self._tick_delivery(now)

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
            self._ensure_assistant()
            if "--pet-only" not in self.argv:
                self.show_assistant()
            if "--assistant-smoke" in self.argv:
                from .assistant_smoke import schedule
                schedule(self, self.argv[self.argv.index("--assistant-smoke") + 1])
            return self.win32.run_message_loop(pre_dispatch=self._pre_dispatch)
        finally:
            self.shutdown()

    def _pre_dispatch(self, msg) -> bool:
        """输入框里的回车＝送出，Esc＝收起（EDIT 控件不会把这两个键报给别人）。"""
        box = self.text_input
        return bool(box is not None and box.handle_message(msg))

    def shutdown(self) -> None:
        try:
            if self.assistant is not None:
                self.assistant.destroy()
            self.control.stop_timer()
            self.tray.remove()
            if self.text_input is not None:
                self.text_input.destroy()
            self.question.destroy()
            self.cards.destroy()
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
            # Reopening the executable returns to the assistant window.
            self.show_assistant()
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
                    self._drag_began()
                    # 拎起来之后窗口放大、原点往左上挪了一截，基准跟着换成新的那个。
                    self._origin_start = (self.pet.x, self.pet.y)
                if self._dragging:
                    self.pet.move(self._origin_start[0] + dx, self._origin_start[1] + dy)
                    self._advance_hang(now_ms())
                    self._render(now_ms())
                    self._position_bubble()
                    self._paint_bubble()
                    self._position_cards()
                    self._position_question()
                    self._last_mouse_x = mx
                return 0
            if msg == w.WM_LBUTTONUP:
                w.user32.ReleaseCapture()
                was_dragging = self._dragging
                self._drag_pending = False
                self._dragging = False
                if was_dragging:
                    self._drag_ended()
                else:
                    # 没拖动，就是点了她一下：举着牌子时跳回那条聊天。
                    self._pet_clicked()
                return 0
            if msg in (w.WM_RBUTTONUP, w.WM_LBUTTONDBLCLK):
                self.show_assistant()
                return 0
            if msg == w.WM_SETCURSOR and self._dragging:
                w.user32.SetCursor(w.user32.LoadCursorW(None, w.c_void_p(w.IDC_SIZEALL)))
                return 1
        except Exception:
            traceback.print_exc()
        return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # MARK: 拖动：被一只看不见的大手拎起来

    @property
    def held_spec(self):
        return self.catalog.specs[HELD_ID]

    def _normal_frame(self) -> Tuple[int, int]:
        """放大的窗口换算回平时那块 192×208 的左上角。"""
        if self.hang_geo is None:
            return (self.pet.x, self.pet.y)
        return (self.pet.x - self.hang_geo.offset[0], self.pet.y - self.hang_geo.offset[1])

    def _drag_began(self) -> None:
        now = now_ms()
        # 上一次还在晃就又被抓住：窗口已经是放大的，只要把手重新握上。
        if self.swing is not None:
            self._released_at = None
            self.swing.grab()
            return
        spec = self.held_spec
        s = self.scale
        length = self.library.hang_length * s
        geo = HangGeometry.make(self.pet_size, (spec.frame_width, spec.frame_height),
                                spec.hang.grip, scale=s,
                                sag_room=length * HangTuning().max_sag_ratio)
        self.hang_geo = geo
        # 窗口临时放大，容下摆动与下坠；多出来的部分是透明的，看不见也不挡点击。
        self.pet.x += geo.offset[0]
        self.pet.y += geo.offset[1]
        self.swing = HangSwing(now, length=length)
        self.held_timeline = SpriteTimeline(spec, now)
        self._released_at = None
        self._painted = None
        self._render(now)
        self._position_bubble()
        self._paint_bubble()
        self.tray.set_tip(self._tray_tip())

    def _drag_ended(self) -> None:
        if self.swing is None:
            return
        # 贴边和保存位置都按平时那块算；放大的窗口跟着挪同样的距离。
        nx, ny = self._normal_frame()
        w, h = self.pet_size
        left, top, right, bottom = self.win32.work_area(nx + w // 2, ny + h // 2)
        nx = min(max(nx, left), max(left, right - w))
        ny = min(max(ny, top), max(top, bottom - h))
        self.pet.move(nx + self.hang_geo.offset[0], ny + self.hang_geo.offset[1])
        self.settings.set("originX", int(nx))
        self.settings.set("originY", int(ny))
        self.swing.release()
        self._released_at = now_ms()
        self._position_bubble()
        self._paint_bubble()

    def _finish_hang(self) -> None:
        """晃停了（或超时、要改大小了）：窗口还原成平时那块，切回当前活动的动作。"""
        if self.swing is None:
            return
        nx, ny = self._normal_frame()
        self.swing = None
        self.held_timeline = None
        self.hang_geo = None
        self._released_at = None
        self.pet.x, self.pet.y = nx, ny
        self._painted = None
        self._render(now_ms())
        self._position_bubble()
        self._paint_bubble()
        self.tray.set_tip(self._tray_tip())

    def _advance_hang(self, now: float) -> None:
        """30 Hz 采一次抓手在屏幕上的位置，摆动按它的加速度算。"""
        geo, swing = self.hang_geo, self.swing
        if geo is None or swing is None:
            return
        # 摆动用的是「y 向上」的坐标（和 macOS 版同一套公式），屏幕的 y 向下，取反。
        swing.advance(now, self.pet.x + geo.pivot[0], -(self.pet.y + geo.pivot[1]))
        if self.held_timeline is not None:
            self.held_timeline.advance(now)
        if self._released_at is not None and (swing.settled or now - self._released_at > SETTLE_LIMIT_MS):
            self._finish_hang()

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
        label = held_name() if self.swing is not None else state_name(self.shown_state)
        return tr("Yukio: %s", "雪绪：%s") % label

    def _source_label(self) -> str:
        names = {"auto": tr("Auto (whoever is working)", "自动（谁在干活跟谁）"),
                 "deepcode": tr("DeepSeek (Deep Code) only", "只跟 DeepSeek（Deep Code）"),
                 "claude": tr("Claude Code only", "只跟 Claude Code"),
                 "gpt": tr("GPT (Codex) only", "只跟 GPT（Codex）")}
        return names.get(self.settings.get("source"), tr("Auto", "自动"))

    #: 菜单里列多久之内的聊天、最多几条。
    CHAT_LIST_WINDOW_MS = 30 * 60 * 1000.0
    CHAT_LIST_LIMIT = 10

    def _chat_picker(self, chats) -> List:
        """“跟随的聊天”子菜单：多个聊天同时跑时挑一条跟。

        默认自动——谁答完、谁在等你拿主意就先给你看，都没有时跟最近在干活的那条。
        """
        Item = self.win32.MenuItem
        rows = [Item(tr("Auto (done and questions first)", "自动（完成和提问优先）"), lambda: self._pick_chat(None),
                     checked=self.router.pinned_session is None), self.win32.SEPARATOR]
        if not chats:
            rows.append(Item(tr("No recent chats", "最近没有聊天在跑"), None))
        for c in chats:
            # 挑定的那条打勾；自动模式下此刻跟着的那条前面画个箭头（Win32 菜单只有打勾一种标记）。
            text = ("→ " if c.focused and not c.pinned else "") + c.menu_label
            rows.append(Item(text, lambda id=c.id: self._pick_chat(id), checked=c.pinned))
        return rows

    def _pick_chat(self, id: Optional[str]) -> None:
        self.router.pin_session(id, now_ms())

    def show_menu(self) -> None:
        w = self.win32
        Item, SEP = w.MenuItem, w.SEPARATOR
        chats = [] if self.demo else self.router.session_summaries(
            now_ms(), quiet_within_ms=self.CHAT_LIST_WINDOW_MS, limit=self.CHAT_LIST_LIMIT)
        label = held_name() if self.swing is not None else state_name(self.shown_state)
        items: List[w.MenuItem] = [Item(tr("Open Yukio Assistant", "打开 Yukio 助手"), self.show_assistant),
                                  Item(tr("Hide Yukio", "收起雪绪") if not self.pet_hidden else tr("Show Yukio", "显示雪绪"),
                                       lambda: self.set_hidden(not self.pet_hidden)), SEP,
                                  Item(tr("Yukio", "雪绪") + " · " + label, None)]
        if not self.demo and self.follow and self.router.completed_session:
            items.append(Item(tr("Open this chat and lower the sign", "打开这条聊天并放下牌子"), self._pet_clicked))
            items.append(Item(tr("Lower the sign, don't open the chat", "先放下牌子，不打开聊天"), self._drop_sign))
        elif not self.demo and self.follow and self.router.asking_session:
            # 问号卡不收：答完之后它自己收，这里只把聊天打开。
            items.append(Item(tr("Open this chat to answer", "打开这条聊天去回答"), self._pet_clicked))
        if self.demo:
            items.append(Item(tr("Playing the demo (not real activity)", "正在播放模拟演示（不是真实活动）"), None))
        elif not self.follow:
            items.append(Item(tr("Following paused, staying idle", "已暂停跟随，保持空闲"), None))
        else:
            found = 0
            for source in self.sources:
                if getattr(source, "available", False):
                    found += 1
                    received = getattr(source.status, "events_received", 0)
                    items.append(Item(tr("Following %s · %d events received", "跟随 %s · 已收到 %d 个事件")
                                      % (tr(source.label, getattr(source, "label_zh", source.label)), received), None))
            if not found:
                missing = [(tr(s.label, getattr(s, "label_zh", s.label)), getattr(s, "projects_dir", "")) for s in self.sources
                           if getattr(s, "projects_dir", "")]
                for label, where in missing[:2]:
                    items.append(Item(tr("No %s records found: %s", "没找到 %s 的记录：%s") % (label, where), None))
                if not missing:
                    items.append(Item(tr("No source to follow", "没有可跟随的来源"), None))
            for chat in chats:
                if chat.focused:
                    items.append(Item(tr("Following: %s%s", "正在跟：%s%s") % (chat.menu_label, tr(" (pinned)", "（挑定的）") if chat.pinned else ""),
                                      None))
        items.append(SEP)
        if self.demo:
            items.append(Item(tr("Stop demo", "停止模拟演示"), self.stop_demo))
        else:
            items.append(Item(tr("Play demo", "播放模拟演示"), self.start_demo))
        items.append(Item(tr("Follow AI activity", "跟随 AI 活动"), self._toggle_follow, checked=self.follow))
        items.append(Item(tr("Show task bubble", "头顶显示任务"), self._toggle_bubble, checked=self.show_bubble))
        items.append(Item(tr("Show other chats", "头顶显示别的聊天"), self._toggle_cards, checked=self.show_cards))
        items.append(Item(tr("Answer here", "在这儿回答问题"), self._toggle_question_card,
                          checked=self.show_question_card))
        items.append(Item(tr("Assistant", "跟随的助手"), None, submenu=[
            Item(tr("Auto (whoever is working)", "自动（谁在干活跟谁）"), lambda: self._set_source("auto"),
                 checked=self.settings.get("source") == "auto"),
            Item(tr("Claude Code", "Claude Code"), lambda: self._set_source("claude"),
                 checked=self.settings.get("source") == "claude"),
            Item(tr("DeepSeek (Deep Code)", "DeepSeek（Deep Code）"), lambda: self._set_source("deepcode"),
                 checked=self.settings.get("source") == "deepcode"),
            Item(tr("GPT (Codex)", "GPT（Codex）"), lambda: self._set_source("gpt"),
                 checked=self.settings.get("source") == "gpt"),
        ]))
        # 界面语言：默认英文，选择存在 settings.json 的 language 里。
        items.append(Item(tr("Language", "语言"), None, submenu=[
            Item("English", lambda: self._set_language("en"), checked=self.settings.get("language") != "zh"),
            Item("中文", lambda: self._set_language("zh"), checked=self.settings.get("language") == "zh"),
        ]))
        if not self.demo:
            # 标题顺带报数：有几条在等你，没人等你时报有几条在跑。
            live = sum(1 for c in chats if c.live)
            wants = sum(1 for c in chats if c.wants_you)
            if wants:
                title = tr("Chat to follow (%d waiting for you)", "跟随的聊天（%d 条等你）") % wants
            elif live > 1:
                title = tr("Chat to follow (%d running)", "跟随的聊天（%d 条在跑）") % live
            else:
                title = tr("Chat to follow", "跟随的聊天")
            items.append(Item(title, None, submenu=self._chat_picker(chats)))
        items.append(Item(tr("Size", "大小"), None, submenu=self._scale_menu()))
        items.append(Item(tr("Back to the bottom-right corner", "回到屏幕右下角"), self._reset_position))
        items.append(SEP)
        items.append(Item(tr("Quit Yukio", "退出雪绪"), self.quit))
        w.show_menu(self.control.hwnd, items)

    def _toggle_follow(self) -> None:
        self.settings.set("follow", not self.follow)

    def _toggle_bubble(self) -> None:
        self.settings.set("showBubble", not self.show_bubble)
        self._update_bubble(now_ms())
        self._update_cards(now_ms(), immediate=True)

    def _toggle_cards(self) -> None:
        self.settings.set("showCards", not self.show_cards)
        self._update_cards(now_ms(), immediate=True)

    def _toggle_question_card(self) -> None:
        self.settings.set("showQuestionCard", not self.show_question_card)
        self._update_question(now_ms(), immediate=True)

    def _drop_sign(self) -> None:
        self.router.dismiss_completion(now_ms())

    #: 大小的可选范围与步长。macOS 版这里是一条 50%–200% 的滑条；
    #: Win32 的托盘菜单是系统原生弹出菜单，塞不进滑条，所以改成几个整档
    #: 加上「放大／缩小一点」各 ±5%，覆盖同样的范围与步进。
    SCALE_MIN, SCALE_MAX, SCALE_STEP = 0.5, 2.0, 0.05
    SCALE_STOPS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)

    @classmethod
    def snap_scale(cls, value: float) -> float:
        """夹回范围并吸到整 5%（设置坏掉也不会出现 0 或大得离谱的雪绪）。"""
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 1.0
        value = min(max(value, cls.SCALE_MIN), cls.SCALE_MAX)
        return round(round(value / cls.SCALE_STEP) * cls.SCALE_STEP, 2)

    def _scale_menu(self) -> List:
        Item = self.win32.MenuItem
        current = self.user_scale
        rows = [Item("%d%%" % int(round(s * 100)), lambda s=s: self._set_scale(s),
                     checked=abs(current - s) < 0.001) for s in self.SCALE_STOPS]
        rows.append(self.win32.SEPARATOR)
        rows.append(Item(tr("Bigger (+5%)", "放大一点（+5%）"), lambda: self._nudge_scale(self.SCALE_STEP),
                         enabled=current < self.SCALE_MAX - 1e-6))
        rows.append(Item(tr("Smaller (−5%)", "缩小一点（−5%）"), lambda: self._nudge_scale(-self.SCALE_STEP),
                         enabled=current > self.SCALE_MIN + 1e-6))
        rows.append(Item(tr("Current %d%%", "当前 %d%%") % int(round(current * 100)), None))
        return rows

    def _nudge_scale(self, delta: float) -> None:
        self._set_scale(self.snap_scale(self.user_scale + delta))

    def _set_source(self, which: str) -> None:
        self.settings.set("source", which)
        now = now_ms()
        # 挑定的聊天、举着的牌子都属于上一家：整个清空，再从新的一家重新回放。
        self.router.reset(now)
        self.sources = default_sources(which)
        for source in self.sources:
            for e in source.poll(now):
                self.router.ingest(e, min(e.ts, now))
        self.router.settle(now)

    def _set_language(self, code: str) -> None:
        self.settings.set("language", code)
        set_language(code)
        self.tray.set_tip(self._tray_tip())   # 气泡与卡上的字在下一轮刷新时跟着换

    def _set_scale(self, scale: float) -> None:
        scale = self.snap_scale(scale)
        if abs(scale - self.user_scale) < 1e-9:
            return
        self._finish_hang()          # 放大的窗口先还原，免得按错的尺寸算锚点
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
        self.cards_hold.value = []
        self.cards_layout = None
        self._cards_image = None
        self._cards_alpha = 0.0
        self.cards.hide()

    def _reset_position(self) -> None:
        self._finish_hang()
        x, y = self._default_origin()
        self.pet.move(x, y)
        self._save_position()
        self._position_bubble()
        self._paint_bubble()
        self._position_cards()
        self._paint_cards()
        self._position_question()
        self._paint_question()

    def start_demo(self) -> None:
        now = now_ms()
        self.demo = (now, demo_steps("demo", now), 0, ActivityRouter(now=now))

    def stop_demo(self) -> None:
        self.demo = None

    @property
    def pet_hidden(self) -> bool:
        return self._assistant_only or not self.settings.get("petVisible", True)

    def set_hidden(self, hidden: bool) -> None:
        self._assistant_only = False
        self.settings.set("petVisible", not hidden)
        self._painted = None
        self._render(now_ms())
        self._paint_bubble()
        self._paint_cards()
        self._paint_question()

    def _ensure_assistant(self):
        if self.assistant is None:
            from .assistant import AssistantWindow
            self.assistant = AssistantWindow(self)
        return self.assistant

    def show_assistant(self) -> None:
        self._ensure_assistant().present()

    def quit(self) -> None:
        if self.assistant is not None:
            self.assistant.destroy()
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
        sys.stderr.write(tr("Yukio failed to start: %s\n", "雪绪启动失败：%s\n") % exc)
        win32.message_box(tr("Yukio could not start:\n\n%s\n\n%s", "雪绪没能启动：\n\n%s\n\n%s") %
                          (exc, (tr("Details were written to ", "详细报错写在 ") + log_path) if log_path
                           else tr("Run python run.py from a command line to see the full error",
                                   "从命令行跑 python run.py 可以看到完整报错")))
        return 1
    return app.run()
