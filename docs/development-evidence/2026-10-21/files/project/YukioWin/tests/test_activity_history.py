"""Synthetic on-disk recovery tests; no real conversations or cloud calls."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from yukio.activity_history import ActivityHistory, MAX_LINE


def line(**kw):
    return (json.dumps(kw) + '\n').encode()


class ActivityHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yukio-history-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'synthetic.jsonl'
        self.path = self.root / 'history.sqlite'

    def write(self, data, append=False):
        with self.source.open('ab' if append else 'wb') as stream:
            stream.write(data)

    def ingest(self, **kw):
        db = ActivityHistory(self.path)
        try:
            return db.ingest(self.source, **kw)
        finally:
            db.close()

    def rows(self, **kw):
        db = ActivityHistory(self.path, readonly=True)
        try:
            return db.rows(**kw)
        finally:
            db.close()

    def test_restart_recovers_matching_and_conflict(self):
        self.write(line(type='session_meta', id='s') + line(type='task_started', turn_id='t')
                   + line(type='function_call', call_id='a', name='shell'))
        self.ingest()
        self.write(line(type='item_completed', item=dict(type='CommandExecution', id='a', exit_code=1)), True)
        self.ingest()
        self.assertEqual(self.rows()[-1]['result']['association'], 'matching_item_id')
        self.write(line(type='function_call_output', call_id='a', output=dict(success=True)), True)
        self.ingest()
        result = self.rows()[-1]['result']
        self.assertTrue(result['conflicting_results'])
        self.assertEqual(result['call_outcome'], 'unknown')
        self.assertEqual(result['turn_id'], 't')

    def test_duplicate_and_partial_line_across_restart(self):
        first = line(type='function_call', call_id='a', name='shell')
        second = line(type='function_call_output', call_id='a', output=dict(success=True))
        self.write(first + second[:-1])
        self.assertEqual(self.ingest()['offset'], len(first))
        self.assertEqual(self.ingest()['events_saved'], 0)
        self.write(b'\n', True)
        self.assertEqual(self.ingest()['events_saved'], 1)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]['source_offset'], len(first))
        self.assertEqual(rows[-1]['source_record_sha256'], hashlib.sha256(second[:-1]).hexdigest())
        self.assertEqual(rows[-1]['result']['call_outcome'], 'succeeded')

    def test_same_size_rewrite_starts_new_generation(self):
        self.write(line(type='function_call', call_id='a', name='shell')); self.ingest()
        self.write(line(type='function_call', call_id='b', name='shell'))
        self.assertEqual(self.ingest()['generation'], 2)
        rows = self.rows()
        self.assertEqual(rows[1]['reason'], 'prefix_changed')
        self.assertEqual([r.get('call_id') for r in rows], ['a', None, 'b'])

    def test_replacement_and_truncation_keep_old_evidence(self):
        self.write(line(type='function_call', call_id='a', name='shell')); self.ingest()
        replacement = self.root / 'replacement'
        replacement.write_bytes(self.source.read_bytes()); os.replace(replacement, self.source)
        self.assertEqual(self.ingest()['generation'], 2)
        self.assertEqual(self.rows()[1]['reason'], 'file_replaced')
        self.write(b'\n')
        self.assertEqual(self.ingest()['generation'], 3)
        self.assertEqual(self.rows()[-1]['reason'], 'file_truncated')

    def test_session_and_file_isolation(self):
        self.write(line(type='session_meta', id='a') + line(type='function_call', call_id='same', name='shell')
                   + line(type='function_call_output', call_id='same', output={'success': False})); self.ingest()
        self.source = self.root / 'another.jsonl'
        self.write(line(type='session_meta', id='b') + line(type='function_call_output', call_id='same', output='no status')); self.ingest()
        self.assertEqual(self.rows(session='b')[-1]['result']['call_outcome'], 'unknown')
        self.assertEqual(self.rows(session='a')[-1]['result']['call_outcome'], 'failed')

    def test_metadata_only_and_missing_time(self):
        secret = 'PRIVATE_BODY_012345'
        self.write(line(type='message', role='user', content=secret)
                   + line(type='function_call', call_id='a', name='shell', arguments=json.dumps({'command': secret}), input=secret)
                   + line(type='function_call_output', call_id='a', output={'success': True, 'text': secret})); self.ingest()
        self.assertNotIn(secret.encode(), self.path.read_bytes())
        self.assertFalse(self.rows()[0]['timestamp_available'])
        self.assertNotIn('timestamp_ms', self.rows()[0])
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_invalid_line_records_gap_and_drops_old_matching_context(self):
        self.write(line(type='function_call', call_id='a', name='shell') + b'{broken\n'
                   + line(type='item_completed', item={'type': 'CommandExecution', 'id': 'a', 'exit_code': 1})); self.ingest()
        self.assertEqual(self.rows()[1]['kind'], 'invalid_record')
        self.assertEqual(self.rows()[-1]['result']['association'], 'unlinked')

    def test_failed_cursor_write_rolls_back_events_and_retries(self):
        self.write(line(type='function_call', call_id='a', name='shell'))
        db = ActivityHistory(self.path)
        db.db.execute("CREATE TRIGGER fail_cursor BEFORE INSERT ON sources BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END")
        with self.assertRaises(sqlite3.Error):
            db.ingest(self.source)
        self.assertEqual(db.rows(), [])
        self.assertEqual(db.db.execute('SELECT count(*) FROM sources').fetchone()[0], 0)
        db.db.execute('DROP TRIGGER fail_cursor')
        self.assertEqual(db.ingest(self.source)['events_saved'], 1)
        db.close()
        self.assertEqual(self.ingest()['events_saved'], 0)

    def test_interrupted_process_rolls_back_then_recovers(self):
        self.write(line(type='function_call', call_id='a', name='shell')); ActivityHistory(self.path).close()
        code = '''import os, sys
from yukio.activity_history import ActivityHistory
h=ActivityHistory(sys.argv[1]); original=h._insert
def stop(row):
 original(row)
 os._exit(23)
h._insert=stop
h.ingest(sys.argv[2])
'''
        done = subprocess.run([sys.executable, '-c', code, str(self.path), str(self.source)], capture_output=True)
        self.assertEqual(done.returncode, 23, done.stderr)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.ingest()['events_saved'], 1)

    def test_source_changes_during_batch_rolls_back(self):
        self.write(line(type='function_call', call_id='a', name='shell'))
        db = ActivityHistory(self.path); original = db._insert
        def change(row):
            original(row); self.write(line(type='function_call', call_id='b', name='shell'))
        with patch.object(db, '_insert', side_effect=change), self.assertRaisesRegex(ValueError, 'Source changed'):
            db.ingest(self.source)
        self.assertEqual(db.rows(), [])
        db.close(); self.ingest()
        self.assertEqual(self.rows()[0]['call_id'], 'b')

    def test_oversized_line_blocks_without_acknowledging(self):
        self.write(line(type='function_call', call_id='a', name='shell') + b' ' * (MAX_LINE + 1) + b'\n')
        with self.assertRaises(ValueError):
            self.ingest()
        self.assertEqual(self.rows(), [])

    def test_bounded_batches_and_query_pages(self):
        self.write(b''.join(line(type='function_call', call_id=str(i), name='shell') for i in range(5)))
        self.assertTrue(self.ingest(max_records=2)['batch_full'])
        self.ingest(max_records=2); self.ingest(max_records=2)
        rows = self.rows(limit=2); page = self.rows(after=rows[-1]['sequence'], limit=3)
        self.assertEqual([r['call_id'] for r in rows + page], ['0', '1', '2', '3', '4'])
        self.assertEqual(self.ingest()['events_saved'], 0)

    def test_unknown_database_and_future_version_not_overwritten(self):
        db = sqlite3.connect(self.path); db.execute('CREATE TABLE important (content TEXT)'); db.commit(); db.close()
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            ActivityHistory(self.path)
        self.assertEqual(self.path.read_bytes(), before)
        future = self.root / 'future.db'; ActivityHistory(future).close()
        db = sqlite3.connect(future); db.execute('PRAGMA user_version=99'); db.close()
        before = future.read_bytes()
        with self.assertRaises(ValueError):
            ActivityHistory(future)
        self.assertEqual(future.read_bytes(), before)

    def test_database_lock_failure_does_not_advance_cursor(self):
        self.write(line(type='function_call', call_id='a', name='shell'))
        db = ActivityHistory(self.path); other = sqlite3.connect(self.path); other.execute('BEGIN IMMEDIATE')
        with self.assertRaises(sqlite3.OperationalError):
            db.ingest(self.source)
        other.rollback(); other.close()
        self.assertEqual(db.ingest(self.source)['events_saved'], 1); db.close()

    def test_deleted_source_leaves_history_readable(self):
        self.write(line(type='function_call', call_id='a', name='shell')); self.ingest(); self.source.unlink()
        with self.assertRaises(OSError):
            self.ingest()
        self.assertEqual(len(self.rows()), 1)

    def test_database_full_keeps_cursor_and_rows_for_retry(self):
        self.write(b''.join(line(type='function_call', call_id=('x' * 900 + str(i)), name='shell') for i in range(100)))
        db = ActivityHistory(self.path)
        pages = db.db.execute('PRAGMA page_count').fetchone()[0]
        db.db.execute('PRAGMA max_page_count=%d' % pages)
        with self.assertRaises(sqlite3.OperationalError) as failure:
            db.ingest(self.source)
        self.assertIn('full', str(failure.exception))
        self.assertEqual(db.rows(), [])
        self.assertEqual(db.db.execute('SELECT count(*) FROM sources').fetchone()[0], 0)
        db.db.execute('PRAGMA max_page_count=1000000')
        self.assertEqual(db.ingest(self.source)['events_saved'], 100)
        db.close()

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO check is POSIX-specific')
    def test_nonregular_source_rejected_without_waiting(self):
        os.mkfifo(self.source)
        with self.assertRaises(ValueError):
            self.ingest()

    def test_foreign_session_is_not_grouped_under_current_session(self):
        self.write(line(type='session_meta', id='s') + line(type='task_started', turn_id='t')
                   + line(type='function_call', name='shell', call_id='a', thread_id='other'))
        self.ingest()
        row = self.rows(session='other')[0]
        self.assertEqual(row['kind'], 'foreign_session_record')
        self.assertEqual(row['source_session_id'], 's')
        self.assertNotIn('context_turn_id', row)
        self.assertEqual(len(self.rows(session='s')), 2)

    def test_all_shared_result_contracts_survive_each_restart(self):
        fixtures = Path(__file__).resolve().parents[2] / 'tests/fixtures/codex-results-v1.json'
        for case in json.loads(fixtures.read_text())['cases']:
            self.source = self.root / (case['name'] + '.jsonl')
            self.write(line(type='session_meta', id='synthetic-session')); self.ingest()
            for step in case['steps']:
                self.write((json.dumps(step['record']) + '\n').encode(), True); self.ingest()
                if step['result'] is not None:
                    actual = self.rows(limit=10000)[-1]['result']
                    for k, v in step['result'].items():
                        self.assertEqual(actual.get(k), v, (case['name'], k))
