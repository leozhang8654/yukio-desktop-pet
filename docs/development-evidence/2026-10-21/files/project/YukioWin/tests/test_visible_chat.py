import unittest
from types import SimpleNamespace
from yukio.visible_chat import VisibleChat
from yukio.browser_open_chat import collect_documents
from yukio.events import Kind
from test_router import Harness

A = '75f6b686-7df9-2166-5c45-437f32b2703d'
B = '0ff5afbf-2794-8a70-8df1-96e3be2aefd9'


class Node:
    def __init__(self, role='PaneControl', url='', children=(), hidden=False):
        self.ControlTypeName, self.url, self.children, self.IsOffscreen = role, url, children, hidden
    def GetValuePattern(self):
        return SimpleNamespace(Value=self.url)
    def GetLegacyIAccessiblePattern(self):
        return None
    def GetChildren(self):
        return self.children


class VisibleChatTests(unittest.TestCase):
    def test_web_app_and_extension_documents(self):
        for path, provider in [(f'https://claude.ai/chat/{A}', 'claude'),
                               (f'https://claude.ai/code/{A}', 'claude'),
                               ('https://claude.ai/cic/task/cse_0123456789', 'claude'),
                               (f'https://chatgpt.com/c/{A}', 'gpt'),
                               (f'https://chat.openai.com/c/{A}', 'gpt'),
                               (f'https://chatgpt.com/g/g-project/c/{A}', 'gpt'),
                               (f'codex://threads/{A}', 'gpt'),
                               ('https://chatgpt.com/codex/tasks/task_0123456789', 'gpt')]:
            self.assertEqual(VisibleChat.from_url(path).provider, provider)

    def test_only_exact_provider_scoped_id_or_explicit_alias(self):
        chat = VisibleChat.from_url(f'https://claude.ai/chat/{A}')
        self.assertTrue(chat.matches(A, 'claude'))
        self.assertFalse(chat.matches(A, 'gpt'))
        self.assertFalse(chat.matches(B, 'claude'))
        local = VisibleChat.from_url(f'claude://code/continue?session=local_{A}')
        self.assertFalse(local.matches(A, 'claude'))
        self.assertTrue(local.matches(A, 'claude', {f'local_{A}': A}))

    def test_unknown_shared_and_spoofed_pages_keep_reminders(self):
        for url in ['https://claude.ai/', 'https://claude.ai/recents', 'https://chatgpt.com/',
                    f'https://claude.ai.evil.test/chat/{A}', f'https://claude.ai@evil.test/chat/{A}',
                    f'http://claude.ai/chat/{A}', 'https://claude.ai/chat/no-id',
                    f'https://chatgpt.com/share/{A}', f'https://chatgpt.com/c/{A}/extra',
                    f'chrome-extension://test/sidepanel.html?session={A}']:
            self.assertIsNone(VisibleChat.from_url(url), url)

    def test_reader_includes_side_panel_but_excludes_history_and_hidden_pages(self):
        page = Node('DocumentControl', f'https://chatgpt.com/c/{A}', [
            Node('HyperlinkControl', f'https://claude.ai/chat/{B}')])
        panel = Node('DocumentControl', 'chrome-extension://test/panel.html', [
            Node('DocumentControl', f'https://claude.ai/chat/{B}')])
        hidden = Node('DocumentControl', f'https://chatgpt.com/c/{B}', hidden=True)
        history = Node('TabControl', children=[Node('DocumentControl', f'https://chatgpt.com/c/{B}')])
        self.assertEqual(collect_documents(Node(children=[page, panel, hidden, history])),
                         [VisibleChat('gpt', A), VisibleChat('claude', B)])
        self.assertEqual(collect_documents(Node(children=[Node() for _ in range(513)])), [])

    def test_reading_during_response_hold_acknowledges_only_that_turn(self):
        h = Harness(session=A)
        h.send(Kind.task_start); h.run(3000)
        h.send(Kind.final_answer); h.send(Kind.task_end)
        h.router.visible_chat_sessions = {A}
        h.run(3500)
        h.router.visible_chat_sessions = set()
        h.run(15000)
        self.assertIsNone(h.router.completed_session)
        h.send(Kind.task_start); h.run(18000)
        h.send(Kind.final_answer); h.send(Kind.task_end); h.run(24000)
        self.assertEqual(h.router.completed_session, A)

    def test_page_and_panel_clear_raised_signs_while_pinned_elsewhere(self):
        h = Harness(session=A)
        h.send(Kind.task_start, session='working')
        h.router.pin_session('working', h.now)
        for session in [A, B, 'unseen']:
            h.send(Kind.task_start, session=session)
            h.send(Kind.final_answer, session=session); h.send(Kind.task_end, session=session)
        h.run(12000)
        self.assertEqual(sum(row.raised_sign for row in h.router.session_summaries(h.now)), 3)
        h.router.visible_chat_sessions = {A, B}
        h.run(13000)
        self.assertEqual([row.id for row in h.router.session_summaries(h.now) if row.raised_sign], ['unseen'])
        h.router.visible_chat_sessions = set()
        h.run(14000)
        self.assertEqual([row.id for row in h.router.session_summaries(h.now) if row.raised_sign], ['unseen'])
