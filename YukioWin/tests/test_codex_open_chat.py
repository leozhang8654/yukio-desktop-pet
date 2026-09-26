import tempfile
import unittest
from pathlib import Path
from yukio.codex_open_chat import CodexOpenChat, CodexOpenChatState
from yukio.events import parse_timestamp

A = '01a0dc03-539c-71d0-9ef8-65ae7d1c7b6e'
B = '01a0dc0f-ecb5-7800-a509-e972c947d39c'
NOW = parse_timestamp('2026-09-26T06:00:00Z')


def line(session=A, window=1, focused='true', visible='true', active='true',
         event='thread_stream_view_activity_changed', stamp='2026-09-26T06:00:00Z'):
    return (f'{stamp} info [electron-message-handler] {event} active={active} '
            f'conversationId={session} rendererWindowId={window} rendererWindowAppearance=primary '
            f'rendererWindowFocused={focused} rendererWindowVisible={visible}\n')


class CodexOpenChatTests(unittest.TestCase):
    def test_selected_view_expires_and_background_task_cannot_select(self):
        s = CodexOpenChatState()
        s.ingest(line(event='task_complete'))
        self.assertIsNone(s.session(NOW))
        s.ingest(line())
        self.assertEqual(s.session(NOW), A)
        s.ingest(line(B, event='task_complete'))
        self.assertEqual(s.session(NOW), A)
        self.assertIsNone(s.session(NOW + 10001))
        self.assertIsNone(s.session(NOW - 1))

    def test_switch_view_then_old_deactivation_keeps_new_view(self):
        s = CodexOpenChatState()
        s.ingest(line())
        s.ingest(line(B))
        s.ingest(line(active='false'))
        self.assertEqual(s.session(NOW), B)
        s.ingest(line(B, active='false'))
        self.assertIsNone(s.session(NOW))

    def test_multiwindow_focus_and_hidden_window(self):
        s = CodexOpenChatState()
        s.ingest(line())
        s.ingest(line(B, window=2, focused='false'))
        self.assertEqual(s.session(NOW), A)
        s.ingest(line(B, window=2))
        self.assertEqual(s.session(NOW), B)
        s.ingest(line(window=1, focused='false'))
        self.assertEqual(s.session(NOW), B)
        s.ingest(line(B, window=2, visible='false'))
        self.assertIsNone(s.session(NOW))

    def test_malformed_metadata_and_old_events_are_ignored(self):
        s = CodexOpenChatState()
        s.ingest(line().replace('rendererWindowAppearance=primary', 'rendererWindowAppearance=overlay'))
        s.ingest(line(session='not-a-uuid'))
        self.assertIsNone(s.session(NOW))
        s.ingest(line(B))
        s.ingest(line(stamp='2026-09-26T05:59:59Z'))
        self.assertEqual(s.session(NOW), B)

    def test_incremental_partial_line_pid_restart_and_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'codex-desktop-session-42-t0-i0-060000.log'
            r = CodexOpenChat(d)
            p.write_text(line()[:-5])
            self.assertIsNone(r.focused_session(42, NOW))
            with p.open('a') as f: f.write(line()[-5:])
            self.assertEqual(r.focused_session(42, NOW), A)
            self.assertEqual(r.focused_session(42, NOW + 100), A)
            self.assertIsNone(r.focused_session(43, NOW))
            self.assertEqual(r.focused_session(42, NOW), A)
            p.write_text('')
            self.assertIsNone(r.focused_session(42, NOW))

    def test_missing_logs_do_not_suppress(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(CodexOpenChat(d).focused_session(42, NOW))

    def test_background_worker_logs_do_not_select(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'codex-desktop-session-42-t1-i0-060000.log').write_text(line())
            self.assertIsNone(CodexOpenChat(d).focused_session(42, NOW))
