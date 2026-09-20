"""把转录里的会话 ID 对应到桌面版 Claude 里的那一条聊天，并给出打开它的深链。

桌面版把每条 Claude Code 会话记在一份 JSON 里，文件开头的 `cliSessionId`
就是 `~/.claude/projects/*/<会话>.jsonl` 的会话 ID：

```
{"sessionId":"local_3987aafa-…","cliSessionId":"c0a80650-…","cwd":"C:\\\\Users\\\\…", …}
```

放在哪：

  * Windows：`%APPDATA%\\Claude\\claude-code-sessions\\<账号>\\<组织>\\local_<id>.json`
  * macOS：  `~/Library/Application Support/Claude/claude-code-sessions/…`（原版所在）

只读这些文件，不写入。这是桌面版的内部记录、不是公开接口，字段与位置都可能随版本变化；
认不出会话时返回 None，调用方只把牌子放下、不乱跳。

**Deep Code（DeepSeek）的聊天跑在终端里，没有这样的深链**：那种会话点了只放下牌子。

移植自 YukioPlayer/Sources/YukioCore/ClaudeSessionLinks.swift；macOS 上实测能跳到指定聊天，
Windows 上的路径与协议是照桌面版的同一套写的，没有在 Windows 上实测过。
"""

from __future__ import annotations

import os
from typing import List, Optional

#: 每份记录只读开头这么多字节：要找的两个字段都在最前面，后面是几百 KB 的快照。
HEAD_BYTES = 64 << 10
#: 最多翻这么多份记录（按最近修改排序，刚结束的那条通常是第一份）。
MAX_FILES = 400
#: 判断"此刻开着哪条聊天"时只翻这么多份（见 ChatLinks.focused_session）。
MAX_FOCUS_SCAN = 24
#: 判断焦点时每份只读这么多字节：lastFocusedAt 和 cliSessionId 都在记录最前面。
FOCUS_HEAD_BYTES = 4 << 10

_HEX = set("0123456789abcdefABCDEF")
_ID_EXTRA = set("-")


def default_sessions_dir() -> str:
    """桌面版 Claude 的会话记录目录。可用 YUKIO_CLAUDE_SESSIONS 指定别处（测试与排查用）。"""
    override = os.environ.get("YUKIO_CLAUDE_SESSIONS")
    if override:
        return override
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"),
                                                         "AppData", "Roaming")
        return os.path.join(base, "Claude", "claude-code-sessions")
    return os.path.join(os.path.expanduser("~"), "Library", "Application Support",
                        "Claude", "claude-code-sessions")


def is_transcript_session_id(s: str) -> bool:
    """转录会话 ID：Claude Code 写的是 UUID。限定字符，免得把任意文本拼进查找与链接。"""
    return bool(s) and 8 <= len(s) <= 64 and all(c in _HEX or c in _ID_EXTRA for c in s)


def is_desktop_session_id(s: str) -> bool:
    """桌面版会话 ID：`local_` 加限定字符，与桌面版对深链的校验一致。"""
    if not s.startswith("local_"):
        return False
    rest = s[len("local_"):]
    return bool(rest) and len(rest) <= 64 and all(c.isascii() and (c.isalnum() or c == "-")
                                                  for c in rest)


def value_of(key: str, data: bytes) -> Optional[str]:
    """取出 JSON 顶层 `"键":"值"` 里的值。

    整份记录有几百 KB，只为两个字段解析全部内容不值得；这两个键在记录里各只出现一次，就地找。
    """
    needle = ('"%s"' % key).encode("utf-8")
    at = data.find(needle)
    if at < 0:
        return None
    i = at + len(needle)
    n = len(data)

    def skip_spaces(i: int) -> int:
        while i < n and data[i:i + 1] in (b" ", b"\t", b"\n", b"\r"):
            i += 1
        return i

    i = skip_spaces(i)
    if i >= n or data[i:i + 1] != b":":
        return None
    i = skip_spaces(i + 1)
    if i >= n or data[i:i + 1] != b'"':
        return None
    i += 1
    out = bytearray()
    while i < n:
        b = data[i:i + 1]
        if b == b"\\":
            return None            # 这两个字段是 ID，不含转义
        if b == b'"':
            return out.decode("utf-8", "replace")
        out += b
        i += 1
    return None


def number_of(key: str, data: bytes) -> Optional[float]:
    """取出 JSON 顶层 `"键":数字` 里的值。`value_of` 只认带引号的值，时间戳是裸数字。"""
    needle = ('"%s"' % key).encode("utf-8")
    at = data.find(needle)
    if at < 0:
        return None
    i = at + len(needle)
    n = len(data)
    while i < n and data[i:i + 1] in (b" ", b"\t", b"\n", b"\r"):
        i += 1
    if i >= n or data[i:i + 1] != b":":
        return None
    i += 1
    while i < n and data[i:i + 1] in (b" ", b"\t", b"\n", b"\r"):
        i += 1
    out = bytearray()
    while i < n and (data[i:i + 1] == b"." or b"0" <= data[i:i + 1] <= b"9"):
        out += data[i:i + 1]
        i += 1
    if not out:
        return None
    try:
        return float(out.decode("ascii"))
    except ValueError:
        return None


class ChatLinks:
    def __init__(self, sessions_dir: Optional[str] = None):
        self.sessions_dir = sessions_dir or default_sessions_dir()
        self.head_bytes = HEAD_BYTES
        self.max_files = MAX_FILES
        self.max_focus_scan = MAX_FOCUS_SCAN
        self.focus_head_bytes = FOCUS_HEAD_BYTES

    def desktop_session_id(self, session: str) -> Optional[str]:
        """转录会话 ID → 桌面版会话 ID（`local_…`）。找不到时 None。"""
        if not is_transcript_session_id(session):
            return None
        for path in self._records():
            head = self._read_head(path)
            if head is None or value_of("cliSessionId", head) != session:
                continue
            found = value_of("sessionId", head)
            if found and is_desktop_session_id(found):
                return found
            # 字段缺失时退回文件名：记录就是以会话 ID 命名的。
            stem = os.path.splitext(os.path.basename(path))[0]
            return stem if is_desktop_session_id(stem) else None
        return None

    def focused_session(self) -> Optional[str]:
        """桌面版此刻选中的那条聊天，返回它的转录会话 ID。认不出时 None。

        依据是记录里的 `lastFocusedAt`（桌面版切到某条聊天时更新它），取最大的那条。
        和 `desktop_session_id` 一样，这是桌面版的内部记录、不是公开接口，读不到就当没有。

        只翻最近改动的 `max_focus_scan` 份：刚被切到的那条一定在里面，而全部记录有几十份、
        这个判断要反复做，翻全部太浪费。
        """
        best_session: Optional[str] = None
        best_at = float("-inf")
        for path in self._records()[:self.max_focus_scan]:
            head = self._read_head(path, self.focus_head_bytes)
            if head is None:
                continue
            at = number_of("lastFocusedAt", head)
            session = value_of("cliSessionId", head)
            if at is None or not session or not is_transcript_session_id(session):
                continue
            if at > best_at:
                best_at, best_session = at, session
        return best_session

    def chat_url(self, session: str) -> Optional[str]:
        """点击举着的牌子时要打开的链接。认不出会话时 None。"""
        found = self.desktop_session_id(session)
        return chat_url_for_desktop_session(found) if found else None

    def _records(self) -> List[str]:
        """全部会话记录，最近修改的在前。"""
        found = []
        try:
            for root, _dirs, files in os.walk(self.sessions_dir):
                for name in files:
                    if not (name.startswith("local_") and name.endswith(".json")):
                        continue
                    path = os.path.join(root, name)
                    try:
                        found.append((os.path.getmtime(path), path))
                    except OSError:
                        continue
        except OSError:
            return []
        found.sort(reverse=True)
        return [path for _mtime, path in found[:self.max_files]]

    def _read_head(self, path: str, size: Optional[int] = None) -> Optional[bytes]:
        try:
            with open(path, "rb") as fh:
                return fh.read(self.head_bytes if size is None else size)
        except OSError:
            return None


def chat_url_for_desktop_session(id: str) -> Optional[str]:
    """桌面版 Claude 注册的深链：打开这条聊天，并把 Claude 带到前面。"""
    return ("claude://code/continue?session=%s" % id) if is_desktop_session_id(id) else None
