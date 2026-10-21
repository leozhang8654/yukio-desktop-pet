"""Selected Codex view from local diagnostics; unknown/stale data keeps reminders."""
from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID
from .events import parse_timestamp


class CodexOpenChatState:
    def __init__(self):
        self.selected = {}
        self.selected_at = {}
        self.focused_window = None
        self.focus_at = float('-inf')

    def ingest(self, line):
        marker = ' [electron-message-handler] '
        if marker not in line:
            return
        at = parse_timestamp(line.split(' ', 1)[0])
        if at is None:
            return
        body = line.split(marker, 1)[1]
        fields = dict(token.split('=', 1) for token in body.split() if '=' in token)
        window = fields.get('rendererWindowId', '')
        focus = fields.get('rendererWindowFocused')
        visible = fields.get('rendererWindowVisible')
        if (fields.get('rendererWindowAppearance') != 'primary' or not window.isdigit()
                or focus not in ('true', 'false') or visible not in ('true', 'false')):
            return
        if at >= self.focus_at:
            if focus == visible == 'true':
                self.focused_window, self.focus_at = window, at
            elif self.focused_window == window:
                self.focused_window, self.focus_at = None, at
        if not body.startswith('thread_stream_view_activity_changed '):
            return
        session = fields.get('conversationId', '')
        try:
            UUID(session)
        except (ValueError, AttributeError):
            return
        if at < self.selected_at.get(window, float('-inf')):
            return
        if fields.get('active') == 'true':
            self.selected[window] = session
            self.selected_at[window] = at
        elif fields.get('active') == 'false':
            self.selected_at[window] = at
            if self.selected.get(window) == session:
                self.selected.pop(window, None)

    def session(self, now):
        if not 0 <= now - self.focus_at <= 10_000:
            return None
        return self.selected.get(self.focused_window)


class CodexOpenChat:
    def __init__(self, logs_directory=None):
        # Codex desktop's Windows file logger: LOCALAPPDATA/Codex/Logs/YYYY/MM/DD.
        self.logs_directory = Path(logs_directory) if logs_directory is not None else (
            Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'Codex' / 'Logs')
        self.process_id = None
        self.state = CodexOpenChatState()
        self.offsets = {}
        self.partial = {}

    def focused_session(self, process_id, now):
        if process_id != self.process_id:
            self.process_id = process_id
            self.state = CodexOpenChatState()
            self.offsets.clear()
            self.partial.clear()
        try:
            files = sorted(self.logs_directory.rglob(f'codex-desktop-*-{process_id}-t0-*.log'))[-8:]
            if not files:
                return None
            for path in files:
                end = path.stat().st_size
                start = self.offsets.get(path, 0)
                if start > end:
                    self.state = CodexOpenChatState()
                    self.partial.pop(path, None)
                    start = 0
                if start == end:
                    continue
                skipped = end - start > 4 << 20
                if skipped:
                    start = end - (4 << 20)
                    self.partial.pop(path, None)
                with path.open('rb') as stream:
                    stream.seek(start)
                    data = self.partial.get(path, b'') + stream.read(end - start)
                    self.offsets[path] = stream.tell()
                if skipped:
                    data = data.partition(b'\n')[2]
                lines = data.split(b'\n')
                self.partial[path] = lines.pop()
                for line in lines:
                    self.state.ingest(line.decode('utf-8', errors='replace'))
            return self.state.session(now)
        except OSError:
            return None
