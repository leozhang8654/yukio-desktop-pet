"""假的 Windows 窗口层：在 macOS／Linux 上跑 app.py 的全部逻辑。

真正的 win32.py 只有在 Windows 上才能导入（ctypes.WinDLL）。这里把它换成一份
记录调用的替身，于是主循环、拖动、气泡摆位、菜单、设置这些逻辑都能在本机测到；
剩下没测到的只有系统调用本身（分层窗口、托盘、弹菜单）。
"""

from __future__ import annotations

import ctypes
from typing import Callable, List, Optional, Tuple

# 与 win32.py 一致的消息号
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_SETCURSOR = 0x0020
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_RBUTTONDOWN = 0x0204
WM_LBUTTONDBLCLK = 0x0203
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
TASKBAR_CREATED = 0xC001
IDC_SIZEALL = 32646
c_void_p = ctypes.c_void_p

CURSOR = [0, 0]
WORK_AREA = (0, 0, 1920, 1080)
DPI = 1.0
QUIT = []


def set_dpi_aware():
    pass


def already_running() -> bool:
    return False


def ask_running_instance_to_show_menu():
    pass


def dpi_scale(hwnd=None) -> float:
    return DPI


def work_area(x=None, y=None) -> Tuple[int, int, int, int]:
    return WORK_AREA


def cursor_pos() -> Tuple[int, int]:
    return (CURSOR[0], CURSOR[1])


def loword(value: int) -> int:
    return value & 0xFFFF


def quit_loop():
    QUIT.append(True)


def run_message_loop() -> int:
    return 0


class _FakeUser32:
    def __init__(self):
        self.captured = False

    def SetCapture(self, hwnd):
        self.captured = True

    def ReleaseCapture(self):
        self.captured = False

    def SetCursor(self, cursor):
        return None

    def LoadCursorW(self, a, b):
        return None

    def DefWindowProcW(self, hwnd, msg, wparam, lparam):
        return 0


user32 = _FakeUser32()


class LayeredWindow:
    def __init__(self, class_name: str, click_through: bool = False, wnd_proc=None):
        self.class_name = class_name
        self.click_through = click_through
        self.wnd_proc = wnd_proc
        self.hwnd = 1000 + len(class_name)
        self.x = self.y = 0
        self.width = self.height = 0
        self.images: List[Tuple[int, int, Tuple[int, int]]] = []
        self.last_image = None
        self.hidden = True
        self.destroyed = False

    def show_image(self, image, x=None, y=None):
        if x is not None:
            self.x = int(x)
        if y is not None:
            self.y = int(y)
        self.width, self.height = image.size
        self.last_image = image
        self.images.append((self.x, self.y, image.size))
        self.hidden = False

    def move(self, x, y):
        self.x, self.y = int(x), int(y)

    def hide(self):
        self.hidden = True

    def raise_above_others(self):
        pass

    @property
    def visible(self):
        return not self.hidden

    def destroy(self):
        self.destroyed = True


class TrayIcon:
    def __init__(self, hwnd, icon_path, tip="雪绪"):
        self.hwnd = hwnd
        self.icon_path = icon_path
        self.tip = tip
        self.added = True

    def re_add(self):
        self.added = True

    def set_tip(self, tip):
        self.tip = tip

    def remove(self):
        self.added = False


class MenuItem:
    __slots__ = ("text", "action", "checked", "enabled", "submenu")

    def __init__(self, text, action=None, checked=None, enabled=True, submenu=None):
        self.text = text
        self.action = action
        self.checked = checked
        self.enabled = enabled
        self.submenu = submenu


SEPARATOR = MenuItem("-")
LAST_MENU: List[MenuItem] = []


def show_menu(hwnd, items, x=None, y=None):
    LAST_MENU[:] = items


#: 点击举着的牌子时“打开”的链接，测试里对着看。
OPENED_URLS: List[str] = []


def open_url(url: str) -> bool:
    OPENED_URLS.append(url)
    return True


class ControlWindow:
    def __init__(self, on_message: Callable):
        self.on_message = on_message
        self.hwnd = 999
        self.show_menu_message = 0xC123
        self.timer_ms: Optional[int] = None
        self.destroyed = False

    def start_timer(self, interval_ms=33):
        self.timer_ms = interval_ms

    def stop_timer(self):
        self.timer_ms = None

    def destroy(self):
        self.destroyed = True


# MARK: 在雪绪这边回答（见 yukio/answer.py 与 yukio/win32.py 的同名东西）

#: 此刻"最前面"的那个可执行文件，测试里直接改。
FOREGROUND = [None]
#: 替你按键都按了什么。
TYPED: List[str] = []
RETURNS = [0]
CLIPBOARD = [None]


def foreground_process_name() -> Optional[str]:
    return FOREGROUND[0]


def send_text(text: str) -> bool:
    TYPED.append(text)
    return True


def send_return() -> bool:
    RETURNS[0] += 1
    return True


def set_clipboard_text(text: str) -> bool:
    CLIPBOARD[0] = text
    return True


class TextInput:
    """假的输入框：记下摆在哪儿、写了什么。"""

    def __init__(self, on_commit, on_cancel, font_height: int = 15):
        self.on_commit = on_commit
        self.on_cancel = on_cancel
        self.font_height = font_height
        self.rect = None
        self.visible = False
        self.value = ""
        self.focused = False
        self.destroyed = False

    def show(self, x, y, width, height):
        self.rect = (int(x), int(y), int(width), int(height))
        self.visible = True

    def move(self, x, y, width, height):
        if self.visible:
            self.show(x, y, width, height)

    def hide(self):
        self.visible = False

    def focus(self):
        self.focused = True

    @property
    def text(self) -> str:
        return self.value

    def clear(self):
        self.value = ""

    def handle_message(self, msg) -> bool:
        return False

    def destroy(self):
        self.destroyed = True


def foreground_process_id():
    return None
