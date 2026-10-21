"""Synthetic multi-session discovery, recovery and resource boundaries."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from yukio.activity_history import ActivityHistory, MAX_LINE
from yukio.activity_collector import ActivityCollector, validate_status_path, write_status
from yukio.activity_collector_cli import CollectorLease


def record(**value):
    return json.dumps(value).encode() + b'\n'


class ActivityCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yukio-collector-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sessions = self.root / 'sessions'; self.sessions.mkdir()
        self.db = ActivityHistory(self.root / 'history.db')
        self.addCleanup(self.db.close)

    def file(self, name, data):
        p = self.sessions / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data); return p

    def collector(self, **kw):
        return ActivityCollector(self.db, self.sessions, **kw)

    def test_discovers_new_and_reactivated_old_files_without_duplicates(self):
        old = self.file('old.jsonl', record(type='session_meta', id='old'))
        os.utime(old, (time.time()-90000, time.time()-90000))
        c = self.collector(); self.assertEqual(c.poll()['discovered_files'], 0)
        self.file('2026/10/20/new.jsonl', record(type='session_meta', id='new'))
        self.assertEqual(c.poll()['events_saved_this_run'], 1)
        self.assertEqual(c.poll()['events_saved_this_run'], 1)
        os.utime(old, None)
        self.assertEqual(c.poll()['events_saved_this_run'], 2)
        self.assertEqual(len(self.db.rows()), 2)

    def test_round_robin_prevents_large_file_starvation(self):
        self.file('a.jsonl', record(type='message') * 9)
        self.file('b.jsonl', record(type='session_meta', id='short'))
        for p in self.sessions.iterdir(): os.utime(p, (100,100))
        c = self.collector(files_per_poll=1, records_per_file=2)
        c.poll(now=100); c.poll(now=100)
        self.assertEqual(len(self.db.rows(session='short')), 1)
        self.assertLess(len(self.db.rows()), 10)

    def test_restart_preserves_partial_call_and_session_isolation(self):
        a = self.file('a.jsonl', record(type='session_meta', id='a') + record(type='function_call', call_id='same', name='shell'))
        self.file('b.jsonl', record(type='session_meta', id='b') + record(type='item_completed', item={'type':'CommandExecution','id':'same','exit_code':1}))
        self.collector().poll()
        result = record(type='function_call_output', call_id='same', output={'success':True})
        with a.open('ab') as f: f.write(result[:-1])
        c = self.collector(); c.poll()
        self.assertEqual(len(self.db.rows()), 4)
        with a.open('ab') as f: f.write(b'\n')
        c.poll(); self.assertEqual(c.poll()['events_saved_this_run'], 1)
        self.assertEqual(self.db.rows(session='a')[-1]['result']['call_outcome'], 'succeeded')
        self.assertEqual(self.db.rows(session='b')[-1]['result']['association'], 'unlinked')

    def test_bad_file_isolated_backoff_then_changed_file_retries(self):
        bad = self.file('bad.jsonl', b'x' * (MAX_LINE+1) + b'\n')
        self.file('good.jsonl', record(type='session_meta', id='ok'))
        c = self.collector()
        self.assertEqual(c.poll(monotonic=10)['state'], 'degraded')
        self.assertEqual(len(self.db.rows()), 1)
        with patch.object(self.db, 'ingest', wraps=self.db.ingest) as ingest:
            c.poll(monotonic=11); ingest.assert_not_called()
        bad.write_bytes(record(type='session_meta', id='fixed'))
        status = c.poll(monotonic=11)
        self.assertEqual(status['error_files'], 0); self.assertEqual(len(self.db.rows()), 2)

    def test_missing_root_waits_then_recovers_and_deleted_history_survives(self):
        self.sessions.rmdir(); c = self.collector()
        self.assertEqual(c.poll()['state'], 'source_unavailable')
        p = self.file('a.jsonl', record(type='session_meta', id='a'))
        self.assertEqual(c.poll()['events_saved_this_run'], 1)
        p.unlink(); self.assertEqual(c.poll()['discovered_files'], 0)
        self.assertEqual(len(self.db.rows()), 1)

    def test_links_do_not_escape_directory_and_limits_are_reported(self):
        outside = self.root / 'private.jsonl'; outside.write_bytes(record(type='session_meta',id='private'))
        (self.sessions/'link.jsonl').symlink_to(outside)
        (self.sessions/'loop').symlink_to(self.sessions,target_is_directory=True)
        c = self.collector(); self.assertEqual(c.poll()['discovered_files'],0)
        with self.assertRaises(ValueError): self.db.ingest(outside,source_root=self.sessions)
        self.file('one.jsonl',record(type='message'));self.file('two.jsonl',record(type='message'))
        status=self.collector(max_files=1).poll()
        self.assertFalse(status['scan_complete']);self.assertEqual(status['state'],'degraded')
        self.assertEqual(status['discovered_files'],2);self.assertEqual(status['tracked_files'],1)
        self.assertFalse(self.collector(max_entries=1).poll()['scan_complete'])

    def test_capacity_full_pauses_without_acknowledging_failed_batch(self):
        self.file('full.jsonl',record(type='message')*100)
        before=self.db.database_bytes()
        c=self.collector(max_bytes=before)
        self.assertEqual(c.poll()['state'],'paused_capacity')
        self.assertEqual(self.db.rows(),[])
        self.assertEqual(self.db.database_bytes(),before)
        self.assertEqual(c.poll()['events_saved_this_run'],0)
        self.assertEqual(self.collector().poll()['events_saved_this_run'],100)

    def test_existing_over_budget_db_is_preserved(self):
        self.file('one.jsonl',record(type='message'));self.collector().poll()
        before=self.db.rows()
        self.assertEqual(self.collector(max_bytes=1).poll()['state'],'paused_capacity')
        self.assertEqual(self.db.rows(),before)

    def test_database_lock_retries_and_recovers(self):
        self.file('one.jsonl',record(type='message'));c=self.collector()
        other=sqlite3.connect(self.db.path,isolation_level=None);other.execute('BEGIN IMMEDIATE')
        try:self.assertEqual(c.poll(monotonic=1)['error_files'],1)
        finally:other.rollback();other.close()
        self.assertEqual(c.poll(monotonic=5)['events_saved_this_run'],1)

    def test_status_metadata_atomic_and_unrelated_file_not_overwritten(self):
        p=self.root/'status.json';p.write_text('important')
        with self.assertRaises(ValueError):validate_status_path(p,self.db.path,self.sessions)
        self.assertEqual(p.read_text(),'important')
        with self.assertRaises(ValueError):validate_status_path(self.sessions/'status.json',self.db.path,self.sessions)
        with self.assertRaises(ValueError):validate_status_path(self.db.path,self.db.path,self.sessions)
        p=self.root/'collector.json';validate_status_path(p,self.db.path,self.sessions)
        c=self.collector();write_status(p,c.poll());write_status(p,c.stopped())
        value=json.loads(p.read_text());self.assertEqual(value['state'],'stopped')
        self.assertNotIn(str(self.root),p.read_text());self.assertNotIn('session_id',value)
        validate_status_path(p,self.db.path,self.sessions)
        if os.name!='nt':self.assertEqual(p.stat().st_mode&0o777,0o600)

    def test_single_collector_lease_releases_on_close(self):
        a=CollectorLease(self.db.path)
        try:
            with self.assertRaises(ValueError):CollectorLease(self.db.path)
        finally:a.close()
        CollectorLease(self.db.path).close()
