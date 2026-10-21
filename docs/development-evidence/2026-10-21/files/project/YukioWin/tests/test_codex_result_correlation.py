"""Constructed regression cases: these are not captured client conversations."""
import unittest
import json
from pathlib import Path

from yukio.events import Kind
from yukio.parsers_codex import CodexRolloutParser
from yukio.codex_results import CodexResultTracker


class CodexResultCorrelationRegressionTests(unittest.TestCase):
    def test_bounded_correlation_evicts_without_guessing(self):
        tracker = CodexResultTracker(capacity=2)
        for call in ('a', 'b', 'c'):
            tracker.start(call)
        old = tracker.record(session='s', payload={}, item={'id': 'a', 'status': 'failed'},
                             source_kind='item_completed', timestamp=0)
        self.assertEqual(old.association, 'unlinked')
        self.assertEqual(old.outcome, 'failed')

    def test_malformed_line_clears_last_result(self):
        parser = CodexRolloutParser('s')
        parser.events(dict(type='function_call_output', call_id='a', output={'success': False}))
        self.assertEqual(len(parser.last_tool_results), 1)
        parser.events_from_line(b'{broken')
        self.assertEqual(parser.last_tool_results, [])

    def test_failure_does_not_attach_to_next_unrelated_output(self):
        parser = CodexRolloutParser('synthetic-session')
        for call in ('a', 'b'):
            parser.events(dict(type='function_call', name='shell', call_id=call, arguments='{}'))
        parser.events(dict(type='item_completed', item=dict(
            type='CommandExecution', call_id='a', status='failed', exit_code=1)))
        b = parser.events(dict(type='function_call_output', call_id='b', output='plain output'))
        a = parser.events(dict(type='function_call_output', call_id='a', output='plain output'))
        self.assertEqual([e.kind for e in b], [Kind.activity_end])
        self.assertEqual([e.kind for e in a], [Kind.activity_failed])

    def test_starting_another_call_does_not_erase_failure(self):
        parser = CodexRolloutParser('synthetic-session')
        parser.events(dict(type='function_call', name='shell', call_id='a', arguments='{}'))
        parser.events(dict(type='item_completed', item=dict(
            type='CommandExecution', call_id='a', status='failed', exit_code=1)))
        parser.events(dict(type='function_call', name='shell', call_id='b', arguments='{}'))
        a = parser.events(dict(type='function_call_output', call_id='a', output='plain output'))
        self.assertEqual([e.kind for e in a], [Kind.activity_failed])


class SharedCodexResultContractTests(unittest.TestCase):
    pass


def contract_test(case):
    def test(self):
        parser = CodexRolloutParser('synthetic-session')
        for step in case['steps']:
            events = parser.events_from_line(json.dumps(step['record']).encode(), fallback_ts=1234)
            self.assertEqual([e.kind.value for e in events], step['kinds'])
            if step['result'] is not None:
                self.assertEqual(len(parser.last_tool_results), 1)
                result = parser.last_tool_results[0]
                actual = result.to_dict()
                for key, value in step['result'].items():
                    self.assertEqual(actual.get(key), value, key)
                if result.association == 'unlinked':
                    self.assertIsNone(result.call_id)
    return test


fixtures = Path(__file__).resolve().parents[2] / 'tests/fixtures/codex-results-v1.json'
for _case in json.loads(fixtures.read_text())['cases']:
    setattr(SharedCodexResultContractTests, 'test_' + _case['name'], contract_test(_case))

