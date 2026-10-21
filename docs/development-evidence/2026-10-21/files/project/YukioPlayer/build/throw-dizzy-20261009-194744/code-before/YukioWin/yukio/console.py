"""控制台编码：Windows 的控制台默认是本地代码页（英文机 cp1252、中文机 cp936），
直接 print 中文会抛 UnicodeEncodeError 把程序弄崩；输出被管道接走时也一样。
所有会打中文的入口都先调一次 force_utf8_console()。
"""

from __future__ import annotations

import os
import sys


def force_utf8_console() -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.WinDLL("kernel32").SetConsoleOutputCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        try:
            # 顺带逐行写出：输出重定向到文件时也能一边跑一边看。
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass
