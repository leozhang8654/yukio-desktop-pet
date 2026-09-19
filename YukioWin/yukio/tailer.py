"""按字节跟踪文件新增内容，并从中切出完整的顶层 JSON 对象。

兼容 JSONL（一行一个）与多行 JSON 直接拼接；读到半行时会等下一次读取补齐，
所以正在写入的会话记录不会解析出半截对象。
"""

from __future__ import annotations

import os
from typing import List, Optional

MAX_BUFFER_BYTES = 16 * 1024 * 1024


class JSONObjectStream:
    """从字节流中切出完整的顶层 JSON 对象。"""

    def __init__(self):
        self._buffer = bytearray()
        self._scan = 0
        self._depth = 0
        self._in_string = False
        self._escape = False
        self._object_start: Optional[int] = None

    def append(self, data: bytes) -> List[bytes]:
        self._buffer.extend(data)
        out: List[bytes] = []
        buf = self._buffer
        i = self._scan
        n = len(buf)
        while i < n:
            b = buf[i]
            if self._object_start is None:
                if b == 0x7B:  # {
                    self._object_start = i
                    self._depth = 1
                    self._in_string = False
                    self._escape = False
            elif self._in_string:
                if self._escape:
                    self._escape = False
                elif b == 0x5C:  # backslash
                    self._escape = True
                elif b == 0x22:  # "
                    self._in_string = False
            else:
                if b == 0x22:
                    self._in_string = True
                elif b in (0x7B, 0x5B):  # { [
                    self._depth += 1
                elif b in (0x7D, 0x5D):  # } ]
                    self._depth -= 1
                    if self._depth == 0 and self._object_start is not None:
                        out.append(bytes(buf[self._object_start:i + 1]))
                        self._object_start = None
            i += 1
        self._scan = i
        keep_from = self._object_start if self._object_start is not None else self._scan
        if keep_from > 0:
            del buf[:keep_from]
            self._scan -= keep_from
            if self._object_start is not None:
                self._object_start = 0
        if len(buf) > MAX_BUFFER_BYTES:
            del buf[:]
            self._scan = 0
            self._object_start = None
            self._depth = 0
            self._in_string = False
        return out


class TailedFile:
    """追踪单个文件新增的字节，切出完整 JSON 对象。"""

    def __init__(self, path: str, offset: int = 0, skip_partial_line: bool = False):
        self.path = path
        self.offset = offset
        self._stream = JSONObjectStream()
        #: 从文件中间（而非行首或文件末尾）开始读时为 True，丢弃到第一个换行为止。
        self._skip_partial_line = skip_partial_line

    def read_new(self, max_bytes: int = 8 << 20) -> Optional[List[bytes]]:
        """返回新增的 JSON 对象；文件已不存在时返回 None。"""
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return None
        if size < self.offset:
            # 文件被截断或重写：从头开始。
            self.offset = 0
            self._stream = JSONObjectStream()
            self._skip_partial_line = False
        if size <= self.offset:
            return []
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                data = fh.read(max_bytes)
        except OSError:
            return []
        if not data:
            return []
        self.offset += len(data)
        if self._skip_partial_line:
            nl = data.find(b"\n")
            if nl < 0:
                return []
            data = data[nl + 1:]
            self._skip_partial_line = False
        return self._stream.append(data)

    def reset_to(self, offset: int) -> None:
        self.offset = offset
        self._stream = JSONObjectStream()
        self._skip_partial_line = False
