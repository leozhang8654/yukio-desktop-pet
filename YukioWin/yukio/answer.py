"""把你在雪绪这边写下的回答送进那条聊天里。

做法就是替你按键：先用深链把桌面版带到最前面，确认最前面的确实是它，
再把答案逐字打进输入框、按一下回车（`SendInput` 的 Unicode 模式，不经过输入法、
也不看键盘布局）。Windows 上这件事不需要额外授权。

带不到前面（认不出那条聊天、终端里跑的 Deep Code、人中途切走了）就只把答案放进粘贴板，
让你自己 Ctrl+V——绝不会往别的应用里乱按键：最前面的应用不是预期的那个就立刻收手。

这是一个按帧推进的小状态机（播放器本来就有 30 Hz 的循环），不另外开线程。
"""

from __future__ import annotations

from typing import Callable, NamedTuple, Optional

#: 等那个应用跑到最前面最多等多久。
WAIT_FOR_FRONT_MS = 2500.0
#: 窗口刚到前面，输入框还要一瞬间才接得住键。
SETTLE_MS = 350.0

#: 已经替你按进去了。
TYPED = "typed"
#: 只放进了粘贴板（那个应用没到前面，或本来就没有可跳的窗口）。
COPIED = "copied"
CLIPBOARD_CHANGED = "clipboard_changed"


class Backend(NamedTuple):
    """真正动手的那几个动作，测试里换成假的。"""

    foreground_exe: Callable[[], Optional[str]]
    send_text: Callable[[str], bool]
    send_return: Callable[[], bool]
    set_clipboard: Callable[[str], bool]
    clipboard_sequence: Optional[Callable[[], int]] = None


def system_backend():
    from . import win32
    return Backend(foreground_exe=win32.foreground_process_name,
                   send_text=win32.send_text,
                   send_return=win32.send_return,
                   set_clipboard=win32.set_clipboard_text,
                   clipboard_sequence=getattr(win32, "clipboard_sequence", None))


class AnswerDelivery:
    """一次送出。`start()` 之后每帧调一次 `tick()`，结束时返回 TYPED／COPIED。"""

    def __init__(self, backend: Optional[Backend] = None):
        self.backend = backend or system_backend()
        self._text = ""
        self._expect_exe: Optional[str] = None
        self._deadline = 0.0
        self._ready_at: Optional[float] = None
        self.busy = False

    def start(self, text: str, expect_exe: Optional[str], bring_to_front: Callable[[], None],
              now: float) -> Optional[str]:
        """开始送。expect_exe 是预期会跑到最前面的可执行文件名；None 表示没有可跳的窗口。

        立刻就能定下结果时（没有窗口可跳）直接返回结果，否则返回 None，等 `tick()`。
        """
        if self.busy:
            return None
        self._text = (text or "").strip()
        if not self._text:
            return None
        # 先放一份进粘贴板：送不过去时这就是退路。
        try:
            self.backend.set_clipboard(self._text)
        except Exception:
            pass
        self._clipboard_sequence = self.backend.clipboard_sequence() if self.backend.clipboard_sequence else None
        try:
            bring_to_front()
        except Exception:
            pass
        if not expect_exe:
            self.busy = False
            return COPIED
        self._expect_exe = expect_exe.lower()
        self._deadline = now + WAIT_FOR_FRONT_MS
        self._ready_at = None
        self.busy = True
        return None

    def tick(self, now: float) -> Optional[str]:
        """推进一步；还没完时返回 None。"""
        if not self.busy:
            return None
        if self._clipboard_changed():
            return self._finish(CLIPBOARD_CHANGED)
        front = None
        try:
            front = self.backend.foreground_exe()
        except Exception:
            front = None
        in_front = bool(front) and front.lower() == self._expect_exe
        if self._ready_at is None:
            if not in_front:
                if now >= self._deadline:
                    return self._finish(COPIED)
                return None
            self._ready_at = now + SETTLE_MS
            return None
        if now < self._ready_at:
            return None
        # 这半秒里人可能又切走了，那就不按键。
        if not in_front:
            return self._finish(COPIED)
        try:
            if not self.backend.send_text(self._text):
                return self._finish(COPIED)
            if self._clipboard_changed():
                return self._finish(CLIPBOARD_CHANGED)
            front = self.backend.foreground_exe()
            if not front or front.lower() != self._expect_exe or not self.backend.send_return():
                return self._finish(COPIED)
        except Exception:
            return self._finish(COPIED)
        return self._finish(TYPED)

    def _clipboard_changed(self):
        return self.backend.clipboard_sequence is not None and self.backend.clipboard_sequence() != self._clipboard_sequence

    def cancel(self):
        self._finish(COPIED)

    def _finish(self, outcome: str) -> str:
        self.busy = False
        self._text = ""
        self._expect_exe = None
        self._ready_at = None
        return outcome
