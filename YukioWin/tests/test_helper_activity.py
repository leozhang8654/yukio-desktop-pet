import json
import tempfile
import time
import unittest
from pathlib import Path
from yukio.events import Kind, PetEvent, PetState
from yukio.parsers_codex import CodexRolloutParser
from yukio.router import ActivityRouter
from yukio.sources import CodexSessionsSource

PARENT = '11111111-1111-4111-8111-111111111111'
CHILD = '22222222-2222-4222-8222-222222222222'
HEADER = {'type': 'session_meta', 'payload': {'id': CHILD, 'session_id': PARENT,
    'source': {'subagent': {'thread_spawn': {'parent_thread_id': PARENT}}}}}

class HelperActivityTests(unittest.TestCase):
    def parser(self):
        parser = CodexRolloutParser(CHILD)
        parser.events(HEADER)
        return parser

    def test_identity_and_explicit_start(self):
        parser = self.parser()
        self.assertEqual((parser.session, parser.parent_session), (CHILD, PARENT))
        events = parser.events({'payload': {'type': 'task_started'}}, 10)
        self.assertEqual([(e.session, e.kind) for e in events], [(CHILD, Kind.task_start)])

    def test_helper_finish_preserves_parent_work_without_a_sign(self):
        parser = self.parser()
        router = ActivityRouter(now=0)
        router.ingest(PetEvent(0, 'codex', PARENT, Kind.task_start), 0)
        payloads = [
            {'type': 'task_started'},
            {'type': 'message', 'role': 'assistant', 'phase': 'final_answer', 'content': [{'type': 'output_text', 'text': 'done'}]},
            {'type': 'item_completed', 'item': {'type': 'AgentMessage', 'phase': 'final_answer'}},
            {'type': 'task_complete', 'last_agent_message': 'done'}]
        for payload in payloads:
            for event in parser.events({'payload': payload}, 100):
                router.ingest(event, 100)
        router.settle(5000)
        self.assertEqual(router.focused_session, PARENT)
        self.assertEqual(router.displayed, PetState.thinking)
        self.assertTrue(all(not row.raised_sign for row in router.session_summaries(5000)))

    def test_normal_chat_keeps_completion(self):
        events = CodexRolloutParser(PARENT).events({'payload': {'type': 'task_complete', 'last_agent_message': 'done'}})
        self.assertEqual([e.kind for e in events], [Kind.final_answer, Kind.task_end])

    def test_large_file_bootstrap_preserves_header_and_parent_title(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); sessions = root / 'sessions'; sessions.mkdir()
            file = sessions / ('rollout-2026-10-11-' + CHILD + '.jsonl')
            rows = [HEADER, {'type': 'padding', 'text': 'x' * (2 << 20)}, {'payload': {'type': 'task_started'}}]
            file.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            (root / 'session_index.jsonl').write_text(json.dumps({'id': PARENT, 'thread_name': 'Animation task'}) + '\n')
            now = time.time() * 1000
            source = CodexSessionsSource(str(sessions)); events = source.poll(now)
            self.assertTrue(any(e.kind == Kind.task_start for e in events))
            self.assertTrue(all(e.session == CHILD for e in events))
            self.assertTrue(any(e.kind == Kind.session_title and e.detail.startswith('Animation task') for e in events))
            with file.open('a') as stream:
                stream.write(json.dumps({'payload': {'type': 'task_complete', 'last_agent_message': 'done'}}) + '\n')
            self.assertEqual([e.kind for e in source.poll(now + 100)], [Kind.task_end])
