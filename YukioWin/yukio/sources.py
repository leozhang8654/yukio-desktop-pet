"""事件来源：只读跟随本机的会话记录，不修改任何工具的文件或设置。

  * DeepCodeSource       DeepSeek 的 Deep Code CLI：~/.deepcode/projects/<项目码>/
  * ClaudeTranscriptSource  Claude Code：~/.claude/projects/<项目>/（把 Claude Code 指向
                            DeepSeek 的 Anthropic 兼容端点时也是这一份）
  * BridgeInboxSource    通用收件箱：notify 脚本或任何别的工具写进来的事件

启动时回放最近活跃会话的末尾，恢复“此刻在做什么”，之后只读新增内容。
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

from .bridge import BridgeParser
from .events import Kind, PetEvent
from .parsers_claude import ClaudeTranscriptParser
from .parsers_deepcode import DeepCodeIndexParser, DeepCodeMessageParser
from .tailer import TailedFile

MB = 1 << 20


def home() -> str:
    return os.path.expanduser("~")


def deepcode_projects_dir() -> str:
    """Deep Code 的会话目录。可用 DEEPCODE_CONFIG_DIR 指定别处（默认 ~/.deepcode）。"""
    base = os.environ.get("DEEPCODE_CONFIG_DIR") or os.path.join(home(), ".deepcode")
    return os.path.join(base, "projects")


def claude_projects_dir() -> str:
    """Claude Code 的转录目录（尊重 CLAUDE_CONFIG_DIR）。"""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(home(), ".claude")
    return os.path.join(base, "projects")


def app_data_dir() -> str:
    """播放器自己的数据目录：Windows 用 %LOCALAPPDATA%\\Yukio，其余平台用 ~/.yukio。"""
    override = os.environ.get("YUKIO_HOME")
    if override:
        return override
    local = os.environ.get("LOCALAPPDATA")
    if local and os.name == "nt":
        return os.path.join(local, "Yukio")
    if os.name == "nt":
        return os.path.join(home(), "AppData", "Local", "Yukio")
    return os.path.join(home(), ".yukio")


def bridge_inbox_path() -> str:
    return os.path.join(app_data_dir(), "inbox.jsonl")


class Status:
    __slots__ = ("directory_found", "tracked_files", "last_event_at", "events_received")

    def __init__(self):
        self.directory_found = False
        self.tracked_files = 0
        self.last_event_at: Optional[float] = None
        self.events_received = 0


class JsonlProjectsSource:
    """跟随 <projects>/<项目>/<会话>.jsonl 这种目录结构。

    Deep Code 与 Claude Code 的会话记录都是这个形状，只有解析器不同。
    """

    #: 启动时，这么久内修改过的会话会回放末尾以恢复状态。
    bootstrap_window_ms = 15 * 60 * 1000.0
    #: 回放时最多读取的末尾字节数。
    bootstrap_tail_bytes = 1 * MB
    #: 超过这么久没修改的会话文件不追踪（被重新写入时会再次发现）。
    track_window_ms = 24 * 3600 * 1000.0
    rescan_interval_ms = 2000.0

    def __init__(self, projects_dir: str, parser, source: str):
        self.projects_dir = projects_dir
        self.parser = parser
        self.source = source
        self.status = Status()
        self._files: Dict[str, TailedFile] = {}
        self._project_dirs: List[str] = []
        self._started = False
        self._last_scan = float("-inf")

    @property
    def available(self) -> bool:
        return os.path.isdir(self.projects_dir)

    def poll(self, now: float) -> List[PetEvent]:
        out: List[PetEvent] = []
        if now - self._last_scan >= self.rescan_interval_ms:
            self._last_scan = now
            self._scan(now, out)
        for path in list(self._files):
            file = self._files[path]
            objects = file.read_new()
            if objects is None:
                del self._files[path]
                # 会话文件被删除：该会话不可能再有后续事件。
                session = os.path.splitext(os.path.basename(path))[0]
                out.append(PetEvent(now, self.source, session, Kind.task_abort))
                self._forget(session)
                continue
            for obj in objects:
                out += self.parser.events_from_line(
                    obj, fallback_session=os.path.splitext(os.path.basename(path))[0], fallback_ts=now)
        # 每次都看一眼各项目的索引（一次 stat，很便宜）：“等你批准”只写在索引里，
        # 要是等到两秒一次的重新扫描才发现，问号卡就慢半拍。
        for project_dir in self._project_dirs:
            self._poll_project(project_dir, now, out)
        self.status.tracked_files = len(self._files)
        if out:
            self.status.events_received += len(out)
            self.status.last_event_at = max(e.ts for e in out)
        return out

    def _forget(self, session: str) -> None:
        pass

    def _scan(self, now: float, out: List[PetEvent]) -> None:
        try:
            entries = os.listdir(self.projects_dir)
        except OSError:
            self.status.directory_found = False
            return
        self.status.directory_found = True
        for name in entries:
            project_dir = os.path.join(self.projects_dir, name)
            if not os.path.isdir(project_dir):
                continue
            try:
                files = os.listdir(project_dir)
            except OSError:
                continue
            for file_name in files:
                if not file_name.endswith(".jsonl"):
                    continue
                path = os.path.join(project_dir, file_name)
                if path in self._files:
                    continue
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                age = now - st.st_mtime * 1000.0
                if age > self.track_window_ms:
                    continue
                # 启动时只回放最近活跃的会话；运行中新发现的文件也只回放末尾，
                # 历史事件带旧时间戳，不会被当成实时活动。
                recent = age <= self.bootstrap_window_ms if not self._started else True
                size = st.st_size
                tail = (size - self.bootstrap_tail_bytes if size > self.bootstrap_tail_bytes else 0) if recent else size
                file = TailedFile(path, offset=tail, skip_partial_line=bool(recent and tail > 0))
                self._files[path] = file
                if recent:
                    objects = file.read_new()
                    for obj in objects or []:
                        out += self.parser.events_from_line(
                            obj, fallback_session=os.path.splitext(file_name)[0], fallback_ts=now)
            if project_dir not in self._project_dirs:
                self._project_dirs.append(project_dir)
                self._poll_project(project_dir, now, out)
        self._started = True

    def _poll_project(self, project_dir: str, now: float, out: List[PetEvent]) -> None:
        """项目目录里除消息文件以外的东西（Deep Code 的会话索引）。"""
        pass


class DeepCodeSource(JsonlProjectsSource):
    """DeepSeek 的 Deep Code CLI。

    除了消息文件，还读每个项目的 sessions-index.json：标题、以及“等你批准 / 已中断 /
    本轮失败”这些只写在索引里的状态。
    """

    label = "Deep Code（DeepSeek）"

    def __init__(self, projects_dir: Optional[str] = None):
        super().__init__(projects_dir or deepcode_projects_dir(), DeepCodeMessageParser(), "deepcode")
        self._index = DeepCodeIndexParser()
        self._index_mtime: Dict[str, float] = {}

    def _forget(self, session: str) -> None:
        self._index.forget(session)

    def _poll_project(self, project_dir: str, now: float, out: List[PetEvent]) -> None:
        path = os.path.join(project_dir, "sessions-index.json")
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return
        if self._index_mtime.get(path) == mtime:
            return
        first_look = path not in self._index_mtime
        self._index_mtime[path] = mtime
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            events = self._index.events(entry, now)
            if first_look:
                # 首次读取只记住当前状态与标题，不把历史状态当成刚发生的事，
                # 但标题要留下（气泡的大任务）。
                events = [e for e in events if e.kind is Kind.session_title]
            out += events


class ClaudeTranscriptSource(JsonlProjectsSource):
    label = "Claude Code"

    def __init__(self, projects_dir: Optional[str] = None):
        super().__init__(projects_dir or claude_projects_dir(), ClaudeTranscriptParser(), "claude-transcript")


class BridgeInboxSource:
    """通用收件箱文件。文件不存在时什么也不做；只读取启动之后新增的记录。"""

    label = "通用收件箱"
    rotate_bytes = 5 * MB

    def __init__(self, path: Optional[str] = None):
        self.path = path or bridge_inbox_path()
        self.status = Status()
        self._tail: Optional[TailedFile] = None
        self._parser = BridgeParser()

    @property
    def available(self) -> bool:
        return os.path.exists(self.path)

    @property
    def is_present(self) -> bool:
        return self.available

    def poll(self, now: float) -> List[PetEvent]:
        if self._tail is None:
            try:
                size = os.path.getsize(self.path)
            except OSError:
                return []
            self.status.directory_found = True
            self._tail = TailedFile(self.path, offset=size)
            return []
        objects = self._tail.read_new()
        if objects is None:
            self._tail = None
            return []
        out: List[PetEvent] = []
        for data in objects:
            out += self._parser.events_from_line(data, fallback_ts=now)
        self.status.events_received += len(out)
        if out:
            self.status.last_event_at = max(e.ts for e in out)
        # 收件箱只是管道：读完且过大时清空，避免无限增长。
        if self._tail.offset > self.rotate_bytes:
            try:
                with open(self.path, "r+b") as fh:
                    fh.truncate(0)
                self._tail.reset_to(0)
            except OSError:
                pass
        return out


def default_sources(which: str = "auto") -> List[object]:
    """按需要建立来源列表。

    which：auto（两个会话目录都跟，哪个有动静听哪个）、deepcode、claude、bridge。
    收件箱始终挂着，文件不存在时不产生任何开销。
    """
    which = (which or "auto").lower()
    if which not in ("auto", "deepcode", "deepseek", "claude"):
        which = "auto"
    out: List[object] = []
    if which in ("auto", "deepcode", "deepseek"):
        out.append(DeepCodeSource())
    if which in ("auto", "claude"):
        out.append(ClaudeTranscriptSource())
    out.append(BridgeInboxSource())
    return out
