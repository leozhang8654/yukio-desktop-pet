"""Windows 窗口层：分层窗口（逐像素透明）、托盘图标、右键菜单、拖动。

只用 ctypes 调系统 API，没有第三方界面库。

为什么用 UpdateLayeredWindow 而不是 Tk 之类：雪绪的边缘是半透明的抗锯齿像素，
用“指定一种颜色当透明色”的办法会在头发和裙边留下一圈杂色；分层窗口支持逐像素 alpha，
边缘干净，而且完全透明的地方鼠标会自动穿透到后面的窗口，不用自己做命中测试。

这个模块只在 Windows 上可用（其余平台用 --snapshot / --bubble / --replay 检查）。
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import POINTER, Structure, byref, c_int, c_size_t, c_ssize_t, c_uint, c_ulong, c_void_p, c_wchar, sizeof
from ctypes import wintypes
from typing import Callable, Dict, List, Optional, Tuple

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

def foreground_process_name() -> Optional[str]:
    """最前面那个窗口属于哪个可执行文件（只要文件名，如 "Claude.exe"）。取不到时 None。

    判断"那条聊天是不是正开在眼前"要用：桌面版 Claude 得真在最前面，人才看得见。
    拿不到就当没在看，照常举牌——宁可多举一块牌，也别把该提醒的吞掉。

    这个函数只在 Windows 上有意义；别的平台上调用方不会走到这里（app 里先判 os.name）。
    """
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = c_ulong(0)
        user32.GetWindowThreadProcessId(c_void_p(hwnd), byref(pid))
        if not pid.value:
            return None
        # PROCESS_QUERY_LIMITED_INFORMATION：只问名字，不要更大的权限，免得被拒。
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return None
        try:
            size = c_ulong(260)
            buf = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(c_void_p(handle), 0, buf, byref(size)):
                return None
            return os.path.basename(buf.value) or None
        finally:
            kernel32.CloseHandle(c_void_p(handle))
    except Exception:
        return None

shell32 = ctypes.WinDLL("shell32", use_last_error=True)

# MARK: 常量

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUIT = 0x0012
WM_SETCURSOR = 0x0020
WM_TIMER = 0x0113
WM_COMMAND = 0x0111
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_DISPLAYCHANGE = 0x007E
WM_DPICHANGED = 0x02E0
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_SHOW_MENU = WM_APP + 2

TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
MF_CHECKED = 0x0008
MF_UNCHECKED = 0x0000
MF_GRAYED = 0x0001
MF_POPUP = 0x0010

NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

SM_CXSMICON = 49
SM_CYSMICON = 50

MB_OK = 0x0000
MB_ICONERROR = 0x0010
MB_SETFOREGROUND = 0x00010000

CS_DBLCLKS = 0x0008

IDC_ARROW = 32512
IDC_SIZEALL = 32646

SPI_GETWORKAREA = 0x0030
MONITOR_DEFAULTTONEAREST = 2

BI_RGB = 0
DIB_RGB_COLORS = 0

ERROR_ALREADY_EXISTS = 183

SINGLETON_MUTEX = "Yukio-Desktop-Pet-Singleton"
SHOW_MENU_MESSAGE = "YukioShowMenu"


# MARK: 结构体

class POINT(Structure):
    _fields_ = [("x", c_int), ("y", c_int)]


class SIZE(Structure):
    _fields_ = [("cx", c_int), ("cy", c_int)]


class RECT(Structure):
    _fields_ = [("left", c_int), ("top", c_int), ("right", c_int), ("bottom", c_int)]


class BLENDFUNCTION(Structure):
    _fields_ = [("BlendOp", ctypes.c_byte), ("BlendFlags", ctypes.c_byte),
                ("SourceConstantAlpha", ctypes.c_byte), ("AlphaFormat", ctypes.c_byte)]


class BITMAPINFOHEADER(Structure):
    _fields_ = [("biSize", c_ulong), ("biWidth", c_int), ("biHeight", c_int),
                ("biPlanes", ctypes.c_ushort), ("biBitCount", ctypes.c_ushort),
                ("biCompression", c_ulong), ("biSizeImage", c_ulong),
                ("biXPelsPerMeter", c_int), ("biYPelsPerMeter", c_int),
                ("biClrUsed", c_ulong), ("biClrImportant", c_ulong)]


class BITMAPINFO(Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", c_ulong * 3)]


WNDPROC = ctypes.WINFUNCTYPE(c_ssize_t, c_void_p, c_uint, c_size_t, c_ssize_t)


class WNDCLASSEXW(Structure):
    _fields_ = [("cbSize", c_uint), ("style", c_uint), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", c_int), ("cbWndExtra", c_int), ("hInstance", c_void_p),
                ("hIcon", c_void_p), ("hCursor", c_void_p), ("hbrBackground", c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p),
                ("hIconSm", c_void_p)]


class MSG(Structure):
    _fields_ = [("hwnd", c_void_p), ("message", c_uint), ("wParam", c_size_t),
                ("lParam", c_ssize_t), ("time", c_ulong), ("pt", POINT)]


class NOTIFYICONDATAW(Structure):
    _fields_ = [("cbSize", c_ulong), ("hWnd", c_void_p), ("uID", c_uint), ("uFlags", c_uint),
                ("uCallbackMessage", c_uint), ("hIcon", c_void_p), ("szTip", c_wchar * 128),
                ("dwState", c_ulong), ("dwStateMask", c_ulong), ("szInfo", c_wchar * 256),
                ("uVersion", c_uint), ("szInfoTitle", c_wchar * 64), ("dwInfoFlags", c_ulong)]


class MONITORINFO(Structure):
    _fields_ = [("cbSize", c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", c_ulong)]


# MARK: 函数签名（64 位下必须声明，否则句柄会被截断成 32 位）

user32.CreateWindowExW.restype = c_void_p
user32.CreateWindowExW.argtypes = [c_ulong, ctypes.c_wchar_p, ctypes.c_wchar_p, c_ulong,
                                   c_int, c_int, c_int, c_int, c_void_p, c_void_p, c_void_p, c_void_p]
user32.DefWindowProcW.restype = c_ssize_t
user32.DefWindowProcW.argtypes = [c_void_p, c_uint, c_size_t, c_ssize_t]
user32.RegisterClassExW.restype = ctypes.c_ushort
user32.RegisterClassExW.argtypes = [POINTER(WNDCLASSEXW)]
user32.GetDC.restype = c_void_p
user32.GetDC.argtypes = [c_void_p]
user32.ReleaseDC.restype = c_int
user32.ReleaseDC.argtypes = [c_void_p, c_void_p]
user32.UpdateLayeredWindow.restype = wintypes.BOOL
user32.UpdateLayeredWindow.argtypes = [c_void_p, c_void_p, POINTER(POINT), POINTER(SIZE),
                                       c_void_p, POINTER(POINT), c_ulong,
                                       POINTER(BLENDFUNCTION), c_ulong]
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [c_void_p, c_ssize_t, c_int, c_int, c_int, c_int, c_uint]
user32.ShowWindow.argtypes = [c_void_p, c_int]
user32.DestroyWindow.argtypes = [c_void_p]
user32.SetTimer.restype = c_size_t
user32.SetTimer.argtypes = [c_void_p, c_size_t, c_uint, c_void_p]
user32.KillTimer.argtypes = [c_void_p, c_size_t]
user32.GetMessageW.argtypes = [POINTER(MSG), c_void_p, c_uint, c_uint]
user32.TranslateMessage.argtypes = [POINTER(MSG)]
user32.DispatchMessageW.argtypes = [POINTER(MSG)]
user32.SetCapture.restype = c_void_p
user32.SetCapture.argtypes = [c_void_p]
user32.GetCursorPos.argtypes = [POINTER(POINT)]
user32.CreatePopupMenu.restype = c_void_p
user32.AppendMenuW.argtypes = [c_void_p, c_uint, c_void_p, ctypes.c_wchar_p]
user32.TrackPopupMenu.restype = c_int
user32.TrackPopupMenu.argtypes = [c_void_p, c_uint, c_int, c_int, c_int, c_void_p, c_void_p]
user32.DestroyMenu.argtypes = [c_void_p]
user32.SetForegroundWindow.argtypes = [c_void_p]
user32.PostMessageW.argtypes = [c_void_p, c_uint, c_size_t, c_ssize_t]
user32.LoadCursorW.restype = c_void_p
user32.LoadCursorW.argtypes = [c_void_p, c_void_p]
user32.SetCursor.restype = c_void_p
user32.SetCursor.argtypes = [c_void_p]
user32.LoadImageW.restype = c_void_p
user32.LoadImageW.argtypes = [c_void_p, ctypes.c_wchar_p, c_uint, c_int, c_int, c_uint]
user32.DestroyIcon.argtypes = [c_void_p]
user32.MonitorFromPoint.restype = c_void_p
user32.MonitorFromPoint.argtypes = [POINT, c_ulong]
user32.GetMonitorInfoW.argtypes = [c_void_p, POINTER(MONITORINFO)]
user32.SystemParametersInfoW.argtypes = [c_uint, c_uint, c_void_p, c_uint]
user32.RegisterWindowMessageW.restype = c_uint
user32.RegisterWindowMessageW.argtypes = [ctypes.c_wchar_p]
user32.PostThreadMessageW.argtypes = [c_ulong, c_uint, c_size_t, c_ssize_t]
user32.GetSystemMetrics.restype = c_int
user32.GetSystemMetrics.argtypes = [c_int]
user32.MessageBoxW.restype = c_int
user32.MessageBoxW.argtypes = [c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, c_uint]

gdi32.CreateCompatibleDC.restype = c_void_p
gdi32.CreateCompatibleDC.argtypes = [c_void_p]
gdi32.CreateDIBSection.restype = c_void_p
gdi32.CreateDIBSection.argtypes = [c_void_p, POINTER(BITMAPINFO), c_uint,
                                   POINTER(c_void_p), c_void_p, c_ulong]
gdi32.SelectObject.restype = c_void_p
gdi32.SelectObject.argtypes = [c_void_p, c_void_p]
gdi32.DeleteObject.argtypes = [c_void_p]
gdi32.DeleteDC.argtypes = [c_void_p]

kernel32.GetModuleHandleW.restype = c_void_p
kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
kernel32.CreateMutexW.restype = c_void_p
kernel32.CreateMutexW.argtypes = [c_void_p, wintypes.BOOL, ctypes.c_wchar_p]

shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconW.argtypes = [c_ulong, POINTER(NOTIFYICONDATAW)]


def set_dpi_aware() -> None:
    """告诉系统我们自己按 DPI 缩放，否则高分屏上系统会把窗口拉糊。"""
    try:
        # Windows 10 1703 及以后：每显示器 DPI 感知 V2（-4）。
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        user32.SetProcessDpiAwarenessContext.argtypes = [c_void_p]
        if user32.SetProcessDpiAwarenessContext(c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def dpi_scale(hwnd: Optional[int] = None) -> float:
    """窗口所在屏幕的缩放（125% 返回 1.25）。取不到时按 100%。"""
    try:
        user32.GetDpiForWindow.restype = c_uint
        user32.GetDpiForWindow.argtypes = [c_void_p]
        if hwnd:
            dpi = user32.GetDpiForWindow(c_void_p(hwnd))
            if dpi:
                return dpi / 96.0
    except (AttributeError, OSError):
        pass
    try:
        user32.GetDpiForSystem.restype = c_uint
        dpi = user32.GetDpiForSystem()
        if dpi:
            return dpi / 96.0
    except (AttributeError, OSError):
        pass
    return 1.0


def work_area(x: int = None, y: int = None) -> Tuple[int, int, int, int]:
    """包含该点的显示器的可用区域（不含任务栏），返回 (left, top, right, bottom)。"""
    if x is not None and y is not None:
        monitor = user32.MonitorFromPoint(POINT(int(x), int(y)), MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = sizeof(MONITORINFO)
        if monitor and user32.GetMonitorInfoW(monitor, byref(info)):
            r = info.rcWork
            return (r.left, r.top, r.right, r.bottom)
    r = RECT()
    if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, byref(r), 0):
        return (r.left, r.top, r.right, r.bottom)
    return (0, 0, 1920, 1080)


def cursor_pos() -> Tuple[int, int]:
    p = POINT()
    user32.GetCursorPos(byref(p))
    return (p.x, p.y)


def already_running() -> bool:
    """同一时间只允许一只雪绪。"""
    kernel32.CreateMutexW(None, True, SINGLETON_MUTEX)
    return ctypes.get_last_error() == ERROR_ALREADY_EXISTS


def ask_running_instance_to_show_menu() -> None:
    """再次双击 Yukio.exe 时，让已经在跑的那只弹出菜单（HWND_BROADCAST = 0xFFFF）。"""
    message = user32.RegisterWindowMessageW(SHOW_MENU_MESSAGE)
    if message:
        user32.PostMessageW(c_void_p(0xFFFF), message, 0, 0)


# MARK: 分层窗口

def premultiplied_bgra(image) -> bytes:
    """Pillow 的 RGBA 图 → 分层窗口要的 BGRA、预乘 alpha 的字节。"""
    from PIL import Image
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    pm = image.convert("RGBa")  # 预乘
    r, g, b, a = pm.split()
    return Image.merge("RGBa", (b, g, r, a)).tobytes()


class LayeredWindow:
    """一个逐像素透明、置顶、不抢焦点的窗口。内容由 Pillow 的图直接贴上去。"""

    _classes_registered: Dict[str, bool] = {}

    def __init__(self, class_name: str, click_through: bool = False,
                 wnd_proc: Optional[Callable] = None):
        self.class_name = class_name
        self._proc_ref = WNDPROC(wnd_proc or self._default_proc)
        instance = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = sizeof(WNDCLASSEXW)
        wc.style = CS_DBLCLKS          # 不加这个收不到双击，只有两次单击
        wc.lpfnWndProc = self._proc_ref
        wc.hInstance = instance
        wc.hCursor = user32.LoadCursorW(None, c_void_p(IDC_ARROW))
        wc.lpszClassName = class_name
        user32.RegisterClassExW(byref(wc))
        ex_style = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_NOACTIVATE
        if click_through:
            ex_style |= WS_EX_TRANSPARENT
        self.hwnd = user32.CreateWindowExW(ex_style, class_name, class_name, WS_POPUP,
                                           0, 0, 1, 1, None, None, instance, None)
        if not self.hwnd:
            raise OSError("创建窗口失败（%s）：%d" % (class_name, ctypes.get_last_error()))
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self._dc = None
        self._bitmap = None
        self._old_bitmap = None
        self._bits = None
        self._dib_size = (0, 0)
        self._visible = False
        self._update_failures = 0

    @staticmethod
    def _default_proc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _ensure_dib(self, width: int, height: int) -> None:
        if self._dib_size == (width, height) and self._bitmap:
            return
        self._release_dib()
        screen_dc = user32.GetDC(None)
        self._dc = gdi32.CreateCompatibleDC(screen_dc)
        user32.ReleaseDC(None, screen_dc)
        info = BITMAPINFO()
        info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # 负数 = 自上而下，和 Pillow 的行序一致
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB
        bits = c_void_p()
        self._bitmap = gdi32.CreateDIBSection(self._dc, byref(info), DIB_RGB_COLORS,
                                              byref(bits), None, 0)
        if not self._bitmap:
            raise OSError("创建位图失败：%d" % ctypes.get_last_error())
        self._bits = bits
        self._old_bitmap = gdi32.SelectObject(self._dc, self._bitmap)
        self._dib_size = (width, height)

    def _release_dib(self) -> None:
        if self._dc and self._old_bitmap:
            gdi32.SelectObject(self._dc, self._old_bitmap)
        if self._bitmap:
            gdi32.DeleteObject(self._bitmap)
        if self._dc:
            gdi32.DeleteDC(self._dc)
        self._dc = self._bitmap = self._old_bitmap = self._bits = None
        self._dib_size = (0, 0)

    def show_image(self, image, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """贴上一张 Pillow RGBA 图，并（可选）移动到屏幕坐标 (x, y)。"""
        width, height = image.size
        if width <= 0 or height <= 0:
            return
        self._ensure_dib(width, height)
        data = premultiplied_bgra(image)
        ctypes.memmove(self._bits, data, len(data))
        if x is not None:
            self.x = int(x)
        if y is not None:
            self.y = int(y)
        self.width, self.height = width, height
        position = POINT(self.x, self.y)
        size = SIZE(width, height)
        source = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        screen_dc = user32.GetDC(None)
        try:
            ok = user32.UpdateLayeredWindow(c_void_p(self.hwnd), screen_dc, byref(position),
                                            byref(size), self._dc, byref(source), 0,
                                            byref(blend), ULW_ALPHA)
        finally:
            user32.ReleaseDC(None, screen_dc)
        if not ok:
            # 第一次失败要吼一声（否则窗口一片空白，什么线索都没有）；之后闷声重试。
            self._update_failures += 1
            if self._update_failures == 1:
                raise OSError("UpdateLayeredWindow 失败（%s）：%d"
                              % (self.class_name, ctypes.get_last_error()))
            return
        if not self._visible:
            user32.SetWindowPos(c_void_p(self.hwnd), HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
            self._visible = True

    def move(self, x: int, y: int) -> None:
        self.x, self.y = int(x), int(y)
        user32.SetWindowPos(c_void_p(self.hwnd), HWND_TOPMOST, self.x, self.y, 0, 0,
                            SWP_NOSIZE | SWP_NOACTIVATE)

    def hide(self) -> None:
        if self._visible:
            user32.ShowWindow(c_void_p(self.hwnd), SW_HIDE)
            self._visible = False

    def raise_above_others(self) -> None:
        user32.SetWindowPos(c_void_p(self.hwnd), HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    @property
    def visible(self) -> bool:
        return self._visible

    def destroy(self) -> None:
        self._release_dib()
        if self.hwnd:
            user32.DestroyWindow(c_void_p(self.hwnd))
            self.hwnd = None


# MARK: 托盘图标与菜单

class TrayIcon:
    def __init__(self, hwnd: int, icon_path: Optional[str], tip: str = "Yukio"):
        self.hwnd = hwnd
        self.icon = None
        if icon_path and os.path.exists(icon_path):
            # 按托盘图标的实际大小取（高分屏上是 20、24…，.ico 里各尺寸都有）。
            cx = user32.GetSystemMetrics(SM_CXSMICON) or 16
            cy = user32.GetSystemMetrics(SM_CYSMICON) or 16
            self.icon = user32.LoadImageW(None, icon_path, IMAGE_ICON, cx, cy, LR_LOADFROMFILE)
            if not self.icon:
                self.icon = user32.LoadImageW(None, icon_path, IMAGE_ICON, 0, 0,
                                              LR_LOADFROMFILE | LR_DEFAULTSIZE)
        self.data = NOTIFYICONDATAW()
        self.data.cbSize = sizeof(NOTIFYICONDATAW)
        self.data.hWnd = c_void_p(hwnd)
        self.data.uID = 1
        self.data.uFlags = NIF_MESSAGE | NIF_TIP | (NIF_ICON if self.icon else 0)
        self.data.uCallbackMessage = WM_TRAY
        self.data.hIcon = self.icon
        self.data.szTip = tip[:127]
        self.added = bool(shell32.Shell_NotifyIconW(NIM_ADD, byref(self.data)))

    def re_add(self) -> None:
        """资源管理器重启后重新挂上托盘图标。"""
        self.added = bool(shell32.Shell_NotifyIconW(NIM_ADD, byref(self.data)))

    def set_tip(self, tip: str) -> None:
        if not self.added:
            return
        self.data.szTip = tip[:127]
        self.data.uFlags = NIF_MESSAGE | NIF_TIP | (NIF_ICON if self.icon else 0)
        shell32.Shell_NotifyIconW(NIM_MODIFY, byref(self.data))

    def remove(self) -> None:
        if self.added:
            shell32.Shell_NotifyIconW(NIM_DELETE, byref(self.data))
            self.added = False
        if self.icon:
            user32.DestroyIcon(self.icon)
            self.icon = None


class MenuItem:
    __slots__ = ("text", "action", "checked", "enabled", "submenu")

    def __init__(self, text: str, action: Optional[Callable] = None,
                 checked: Optional[bool] = None, enabled: bool = True,
                 submenu: Optional[List["MenuItem"]] = None):
        self.text = text
        self.action = action
        self.checked = checked
        self.enabled = enabled
        self.submenu = submenu


SEPARATOR = MenuItem("-")


def show_menu(hwnd: int, items: List[MenuItem], x: Optional[int] = None,
              y: Optional[int] = None) -> None:
    """在鼠标位置弹出右键菜单，选中的项直接执行。"""
    if x is None or y is None:
        x, y = cursor_pos()
    actions: Dict[int, Callable] = {}
    menus: List[int] = []
    next_command = [1]

    def build(entries: List[MenuItem]) -> int:
        handle = user32.CreatePopupMenu()
        menus.append(handle)
        for item in entries:
            if item is SEPARATOR or item.text == "-":
                user32.AppendMenuW(handle, MF_SEPARATOR, 0, None)
                continue
            if item.submenu:
                user32.AppendMenuW(handle, MF_STRING | MF_POPUP, build(item.submenu), item.text)
                continue
            flags = MF_STRING
            if item.checked is True:
                flags |= MF_CHECKED
            if not item.enabled or item.action is None:
                flags |= MF_GRAYED
            command = next_command[0]
            next_command[0] += 1
            if item.action is not None:
                actions[command] = item.action
            user32.AppendMenuW(handle, flags, command, item.text)
        return handle

    root = build(items)
    # 菜单要能在点到别处时自己收起来，必须先把宿主窗口拉到前台。
    user32.SetForegroundWindow(c_void_p(hwnd))
    chosen = user32.TrackPopupMenu(root, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                                   int(x), int(y), 0, c_void_p(hwnd), None)
    user32.PostMessageW(c_void_p(hwnd), 0, 0, 0)  # WM_NULL：菜单收起后的老毛病
    for handle in menus:
        user32.DestroyMenu(handle)
    action = actions.get(chosen)
    if action:
        action()


# MARK: 宿主窗口（托盘、菜单、定时器都挂在它上面）

class ControlWindow:
    """隐藏的普通窗口：托盘回调、菜单宿主、30 Hz 定时器。

    雪绪本体是 WS_EX_NOACTIVATE 的分层窗口，不能拿前台焦点，弹菜单会收不起来，
    所以另开这一个可以被激活的隐藏窗口当宿主。
    """

    def __init__(self, on_message: Callable[[int, int, int], Optional[int]]):
        self.on_message = on_message
        self._proc_ref = WNDPROC(self._proc)
        instance = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._proc_ref
        wc.hInstance = instance
        wc.hCursor = user32.LoadCursorW(None, c_void_p(IDC_ARROW))
        wc.lpszClassName = "YukioControl"
        user32.RegisterClassExW(byref(wc))
        self.hwnd = user32.CreateWindowExW(WS_EX_TOOLWINDOW, "YukioControl", "Yukio", WS_POPUP,
                                           0, 0, 0, 0, None, None, instance, None)
        if not self.hwnd:
            raise OSError("创建宿主窗口失败：%d" % ctypes.get_last_error())
        self.show_menu_message = user32.RegisterWindowMessageW(SHOW_MENU_MESSAGE)

    def _proc(self, hwnd, msg, wparam, lparam):
        try:
            handled = self.on_message(msg, wparam, lparam)
        except Exception:  # 界面线程里出错也不能把雪绪整个弄没
            import traceback
            traceback.print_exc()
            handled = None
        if handled is not None:
            return handled
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def start_timer(self, interval_ms: int = 33) -> None:
        user32.SetTimer(c_void_p(self.hwnd), 1, interval_ms, None)

    def stop_timer(self) -> None:
        user32.KillTimer(c_void_p(self.hwnd), 1)

    def destroy(self) -> None:
        if self.hwnd:
            user32.DestroyWindow(c_void_p(self.hwnd))
            self.hwnd = None


def run_message_loop(pre_dispatch: Optional[Callable[["MSG"], bool]] = None) -> int:
    """跑消息循环。

    pre_dispatch 在派发之前先看一眼每条消息，返回 True 表示这条自己处理了、不再往下派发。
    输入框里的回车和 Esc 要在这里拦（见 TextInput）：EDIT 控件自己不会把这两个键报给别人。
    """
    msg = MSG()
    while True:
        result = user32.GetMessageW(byref(msg), None, 0, 0)
        if result == 0:
            return int(msg.wParam)
        if result == -1:
            return 1
        if pre_dispatch is not None:
            try:
                if pre_dispatch(msg):
                    continue
            except Exception:
                pass
        user32.TranslateMessage(byref(msg))
        user32.DispatchMessageW(byref(msg))


def quit_loop() -> None:
    user32.PostQuitMessage(0)


#: 资源管理器重启后系统广播这条消息，收到要把托盘图标重新加回去。
TASKBAR_CREATED = user32.RegisterWindowMessageW("TaskbarCreated")


def message_box(text: str, title: str = "Yukio") -> None:
    """出大问题时弹个框说一声——打包成 exe 后没有终端，不然用户什么都看不到。"""
    try:
        user32.MessageBoxW(None, text[:1500], title, MB_OK | MB_ICONERROR | MB_SETFOREGROUND)
    except Exception:
        pass


def open_url(url: str) -> bool:
    """交给系统按协议打开（`claude://…` 由桌面版 Claude 自己注册）。

    只接受这几种协议，免得把任意字符串交给 ShellExecute 去执行。
    """
    if not any(url.startswith(p) for p in ("claude://", "https://", "http://")):
        return False
    try:
        # SW_SHOWNORMAL = 1；返回值 > 32 才算成功。
        return shell32.ShellExecuteW(None, "open", url, None, None, 1) > 32
    except Exception:
        return False


def loword(value: int) -> int:
    return value & 0xFFFF


def signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def mouse_position_from_lparam(lparam: int) -> Tuple[int, int]:
    """WM_MOUSEMOVE 等消息里的坐标（窗口内，可能是负数）。"""
    return (signed16(lparam & 0xFFFF), signed16((lparam >> 16) & 0xFFFF))


# MARK: 在雪绪这边回答：一个真正的输入框，和替你按键把答案送过去

WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_BORDER = 0x00800000
ES_AUTOHSCROLL = 0x0080
WM_SETFONT = 0x0030
WM_GETTEXTLENGTH = 0x000E
WM_KEYDOWN = 0x0100
EM_SETSEL = 0x00B1
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
#: 这一下键归输入法处理（正在选词）：别当成“按了回车要送出”。
VK_PROCESSKEY = 0xE5
DEFAULT_CHARSET = 1
CLEARTYPE_QUALITY = 5
COLOR_WINDOW = 5

# 句柄是指针：返回值按 int 截断在 64 位上会丢高位，先把这几个的返回类型说清楚。
gdi32.CreateFontW.restype = c_void_p
kernel32.GlobalAlloc.restype = c_void_p
kernel32.GlobalLock.restype = c_void_p
user32.SendMessageW.restype = c_ssize_t

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


class MOUSEINPUT(Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", c_ssize_t)]


class KEYBDINPUT(Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", c_ssize_t)]


class HARDWAREINPUT(Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _key_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return item


def _send(items: List[INPUT]) -> bool:
    if not items:
        return True
    array = (INPUT * len(items))(*items)
    sent = user32.SendInput(len(items), byref(array), sizeof(INPUT))
    return sent == len(items)


def send_text(text: str) -> bool:
    """把这段字打进最前面那个窗口（按 UTF-16 一个码元一个码元地送，中文和表情都认）。

    用 KEYEVENTF_UNICODE 而不是模拟具体按键：不依赖当前键盘布局，也不经过输入法。
    """
    if not text:
        return True
    units = text.encode("utf-16-le")
    items: List[INPUT] = []
    for i in range(0, len(units), 2):
        code = units[i] | (units[i + 1] << 8)
        items.append(_key_input(scan=code, flags=KEYEVENTF_UNICODE))
        items.append(_key_input(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        # 一次送太多会被有些应用吞掉，分批走。
        if len(items) >= 200:
            if not _send(items):
                return False
            items = []
    return _send(items)


def send_return() -> bool:
    """按一下回车。"""
    return _send([_key_input(vk=VK_RETURN), _key_input(vk=VK_RETURN, flags=KEYEVENTF_KEYUP)])


def set_clipboard_text(text: str) -> bool:
    """把答案放进粘贴板（送不过去时的退路：你自己 Ctrl+V）。"""
    try:
        if not user32.OpenClipboard(None):
            return False
        try:
            user32.EmptyClipboard()
            data = text.encode("utf-16-le") + b"\x00\x00"
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not handle:
                return False
            pointer = kernel32.GlobalLock(c_void_p(handle))
            if not pointer:
                return False
            ctypes.memmove(pointer, data, len(data))
            kernel32.GlobalUnlock(c_void_p(handle))
            return bool(user32.SetClipboardData(CF_UNICODETEXT, c_void_p(handle)))
        finally:
            user32.CloseClipboard()
    except Exception:
        return False


class TextInput:
    """卡片上那个输入框：一个系统自带的 EDIT 控件，摆在画出来的框上。

    为什么不自己画光标、自己收按键：中文要输入法（选词、候选框、拼音串），
    自己做一套既难又容易出岔子；EDIT 控件天生就会。

    分层窗口里塞不下子控件（UpdateLayeredWindow 只认整块位图），所以它是一扇
    单独的小窗口，跟着卡片摆位置。
    """

    _registered = False

    def __init__(self, on_commit: Callable[[str], None], on_cancel: Callable[[], None],
                 font_height: int = 15):
        self.on_commit = on_commit
        self.on_cancel = on_cancel
        instance = kernel32.GetModuleHandleW(None)
        if not TextInput._registered:
            wc = WNDCLASSEXW()
            wc.cbSize = sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = WNDPROC(lambda h, m, w_, l: user32.DefWindowProcW(h, m, w_, l))
            wc.hInstance = instance
            wc.hCursor = user32.LoadCursorW(None, c_void_p(IDC_ARROW))
            wc.hbrBackground = c_void_p(COLOR_WINDOW + 1)
            wc.lpszClassName = "YukioAnswerBox"
            self._class_proc = wc.lpfnWndProc          # 别让它被回收
            user32.RegisterClassExW(byref(wc))
            TextInput._registered = True
        self.hwnd = user32.CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW, "YukioAnswerBox", "",
                                           WS_POPUP, 0, 0, 10, 10, None, None, instance, None)
        if not self.hwnd:
            raise OSError("创建输入框窗口失败：%d" % ctypes.get_last_error())
        self.edit = user32.CreateWindowExW(0, "EDIT", "",
                                           WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
                                           0, 0, 10, 10, c_void_p(self.hwnd), None, instance, None)
        if not self.edit:
            raise OSError("创建输入框失败：%d" % ctypes.get_last_error())
        self._font = gdi32.CreateFontW(-abs(int(font_height)), 0, 0, 0, 400, 0, 0, 0,
                                       DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, "Microsoft YaHei UI")
        if self._font:
            user32.SendMessageW(c_void_p(self.edit), WM_SETFONT, c_void_p(self._font), 1)
        self._visible = False

    @property
    def visible(self) -> bool:
        return self._visible

    def show(self, x: int, y: int, width: int, height: int) -> None:
        user32.SetWindowPos(c_void_p(self.hwnd), HWND_TOPMOST, int(x), int(y),
                            int(width), int(height), SWP_SHOWWINDOW | SWP_NOACTIVATE)
        user32.SetWindowPos(c_void_p(self.edit), 0, 2, 2, int(width) - 4, int(height) - 4,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self._visible = True

    def move(self, x: int, y: int, width: int, height: int) -> None:
        if self._visible:
            self.show(x, y, width, height)

    def hide(self) -> None:
        if not self._visible:
            return
        user32.ShowWindow(c_void_p(self.hwnd), SW_HIDE)
        self._visible = False

    def focus(self) -> None:
        """把键盘交给它（点了输入框才调；卡片立起来的那一刻不抢焦点）。"""
        user32.SetForegroundWindow(c_void_p(self.hwnd))
        user32.SetFocus(c_void_p(self.edit))
        length = user32.SendMessageW(c_void_p(self.edit), WM_GETTEXTLENGTH, 0, 0)
        user32.SendMessageW(c_void_p(self.edit), EM_SETSEL, length, length)

    @property
    def text(self) -> str:
        length = int(user32.SendMessageW(c_void_p(self.edit), WM_GETTEXTLENGTH, 0, 0))
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(c_void_p(self.edit), buf, length + 1)
        return buf.value

    def clear(self) -> None:
        user32.SetWindowTextW(c_void_p(self.edit), "")

    def handle_message(self, msg) -> bool:
        """消息循环里先过一遍：输入框里的回车＝送出，Esc＝收起。

        正在用输入法选词时这一下键是 VK_PROCESSKEY，交回给输入法，不当成送出。
        """
        if not self._visible or msg.message != WM_KEYDOWN or msg.hwnd != self.edit:
            return False
        key = int(msg.wParam)
        if key == VK_PROCESSKEY:
            return False
        if key == VK_RETURN:
            self.on_commit(self.text.strip())
            return True
        if key == VK_ESCAPE:
            self.on_cancel()
            return True
        return False

    def destroy(self) -> None:
        if self.hwnd:
            user32.DestroyWindow(c_void_p(self.hwnd))
            self.hwnd = None
            self.edit = None
        if self._font:
            gdi32.DeleteObject(c_void_p(self._font))
            self._font = None


def clipboard_sequence() -> int:
    """Changes for any clipboard format, including non-text content."""
    return int(user32.GetClipboardSequenceNumber())
