"""Redirected stdin/stdout also work in a windowed PyInstaller executable."""
import json
import os
import sys

def run():
    from .answer_bridge import run_claude_hook
    if sys.stdin is not None and sys.stdout is not None:
        result = run_claude_hook(sys.stdin.buffer.read(1 << 20))
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
        return 0
    if os.name != 'nt': return 1
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.GetStdHandle.argtypes = [wintypes.DWORD]; api.GetStdHandle.restype = wintypes.HANDLE
    api.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    api.WriteFile.argtypes = api.ReadFile.argtypes
    handle = api.GetStdHandle(-10 & 0xffffffff)
    data = bytearray(); buf = ctypes.create_string_buffer(8192); count = wintypes.DWORD()
    while api.ReadFile(handle, buf, len(buf), ctypes.byref(count), None) and count.value:
        data.extend(buf.raw[:count.value])
        if len(data) > 1 << 20: return 1
    result = json.dumps(run_claude_hook(bytes(data)), ensure_ascii=False).encode('utf-8')
    output = ctypes.create_string_buffer(result)
    return 0 if api.WriteFile(api.GetStdHandle(-11 & 0xffffffff), output, len(result), ctypes.byref(count), None) and count.value == len(result) else 1
