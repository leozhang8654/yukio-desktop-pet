import unittest
from types import SimpleNamespace
from unittest.mock import patch
from yukio import browser_open_chat as browser
from yukio.parsers_codex import CodexRolloutParser
from test_visible_chat import Node, A, B
from test_app_logic import make_app

class PluginDestinationTests(unittest.TestCase):
    def test_exact_header_does_not_confuse_duplicates_or_truncation(self):
        titles = [(A, 'Summarize missed class content'), (B, 'Other chat')]
        self.assertEqual(browser.session_for_header('Summarize missed class content No chats in progress', titles), A)
        self.assertIsNone(browser.session_for_header('Summarize missed...', titles))
        self.assertIsNone(browser.session_for_header('Other chat', titles + [(A, 'Other chat')]))

    def test_panel_next_to_unrelated_page_is_recognized(self):
        def button(label):
            n = Node('ButtonControl'); n.Name = label; return n
        panel = Node('DocumentControl', browser.SIDE_PANEL, [Node(children=[button('New chat'), button('Lesson summary No chats in progress'), button('More actions')])])
        root = Node(children=[Node('DocumentControl', 'https://classroom.google.com/assignment'), panel])
        self.assertEqual(browser.collect_documents(root, titles=[(A, 'Lesson summary')]), [browser.VisibleChat('gpt', A)])
        panel.IsOffscreen = True
        self.assertEqual(browser.collect_documents(root, titles=[(A, 'Lesson summary')]), [])

    def test_plugin_route_never_opens_desktop_app_even_without_saved_tab(self):
        app = make_app()
        app.sources = [SimpleNamespace(is_browser_session=lambda session: session == A)]
        with patch.object(browser, 'open_session', return_value=False) as open_tab, patch.object(app.win32, 'open_url') as open_url:
            app._open_chat(A)
            open_tab.assert_called_once_with(A)
            open_url.assert_not_called()
            self.assertIsNone(app._chat_url(A))

    def test_origin_from_metadata(self):
        parser = CodexRolloutParser(A)
        parser.events({'type': 'session_meta', 'payload': {'id': A, 'originator': 'codex-chrome-extension-sidepanel'}})
        self.assertEqual(parser.originator, 'codex-chrome-extension-sidepanel')

    def test_old_plugin_keeps_identity_without_replaying_completion(self):
        import tempfile, json, os, time
        from pathlib import Path
        from yukio.sources import CodexSessionsSource
        from yukio.events import Kind
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sessions = root / 'sessions'
            sessions.mkdir()
            rollout = sessions / ('rollout-' + A + '.jsonl')
            rollout.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': A, 'originator': 'codex-chrome-extension-sidepanel'}}) + '\n', encoding='utf-8')
            os.utime(rollout, (time.time() - 3600, time.time() - 3600))
            (root / 'session_index.jsonl').write_text(json.dumps({'id': A, 'thread_name': 'Old lesson'}) + '\n', encoding='utf-8')
            source = CodexSessionsSource(str(sessions))
            events = source.poll(time.time() * 1000)
            self.assertTrue(source.is_browser_session(A))
            self.assertEqual([(e.session, e.detail) for e in events if e.kind == Kind.session_title], [(A, 'Old lesson')])
            self.assertFalse(any(e.kind in (Kind.final_answer, Kind.task_end) for e in events))
