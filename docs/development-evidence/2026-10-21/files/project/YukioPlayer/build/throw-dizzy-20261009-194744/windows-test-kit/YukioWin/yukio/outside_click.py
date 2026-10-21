"""Dismiss compact settings on an outside click without intercepting that click."""
import ctypes
import os
from collections import deque
from ctypes import wintypes


class OutsideClickDismissal:
    def __init__(self, window):
        self.window = window
        self.hook = None
        self.callback = None
        self.timer = None
        self.pending = deque()
        self.api = None
        window.bind('<Map>', self._mapped, add='+')
        window.bind('<Unmap>', self._unmapped, add='+')
        window.bind('<Destroy>', self._unmapped, add='+')

    def _mapped(self, event):
        if event.widget != self.window or os.name != 'nt' or self.hook:
            return
        self._install()

    def _unmapped(self, event):
        if event.widget == self.window:
            self.stop()

    def _install(self):
        api = self.api = ctypes.WinDLL('user32', use_last_error=True)
        hook_proc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                                      ctypes.c_size_t, ctypes.c_ssize_t)

        class MouseData(ctypes.Structure):
            _fields_ = [('pt', wintypes.POINT), ('mouseData', wintypes.DWORD),
                        ('flags', wintypes.DWORD), ('time', wintypes.DWORD),
                        ('extra', ctypes.c_size_t)]

        api.SetWindowsHookExW.argtypes = [ctypes.c_int, hook_proc, wintypes.HINSTANCE, wintypes.DWORD]
        api.SetWindowsHookExW.restype = wintypes.HANDLE
        api.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
        api.CallNextHookEx.restype = ctypes.c_ssize_t
        api.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        api.GetAncestor.restype = wintypes.HWND
        api.WindowFromPoint.argtypes = [wintypes.POINT]
        api.WindowFromPoint.restype = wintypes.HWND
        api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        hwnd = api.GetAncestor(self.window.winfo_id(), 2)  # GA_ROOT includes title bar.
        api.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        api.GetWindow.restype = wintypes.HWND

        def mouse_event(code, message, data):
            # Do no Tk work here: the hook runs inside the native message loop.
            if code >= 0 and message in (0x0201, 0x0204, 0x0207, 0x020B):
                point = ctypes.cast(data, ctypes.POINTER(MouseData)).contents.pt
                rect = wintypes.RECT()
                hit = api.GetAncestor(api.WindowFromPoint(point), 2)
                owned = False
                while hit:
                    if hit == hwnd:
                        owned = True
                        break
                    hit = api.GetWindow(hit, 4)  # GW_OWNER: only settings-owned popups.
                if api.GetWindowRect(hwnd, ctypes.byref(rect)):
                    inside = rect.left <= point.x < rect.right and rect.top <= point.y < rect.bottom
                    if not inside and not owned:
                        self.pending.append(True)
            return api.CallNextHookEx(None, code, message, data)

        self.callback = hook_proc(mouse_event)
        self.hook = api.SetWindowsHookExW(14, self.callback, None, 0)  # WH_MOUSE_LL
        if not self.hook:
            self.callback = None
            raise ctypes.WinError(ctypes.get_last_error())
        self.timer = self.window.after(20, self._drain)

    def _drain(self):
        self.timer = None
        outside = bool(self.pending)
        self.pending.clear()
        # A combobox or modal dialog owns the grab while interacting with it.
        # Tcl returns raw widget paths even for internal ttk popdown windows.
        grabbed = bool(self.window.tk.call('grab', 'current', self.window._w))
        if outside and not grabbed:
            self.window.withdraw()
            self.stop()
        elif self.hook:
            self.timer = self.window.after(20, self._drain)

    def stop(self):
        if self.timer is not None:
            self.window.after_cancel(self.timer)
            self.timer = None
        if self.hook:
            self.api.UnhookWindowsHookEx(self.hook)
            self.hook = None
        self.callback = None
        self.pending.clear()
