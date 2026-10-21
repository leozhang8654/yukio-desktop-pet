"""Bounded, fair local Codex discovery. No desktop loop or network dependencies."""
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time



def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Entry:
    revision: object = None
    seen: object = None
    pending: bool = True
    failures: int = 0
    retry_at: float = 0


class ActivityCollector:
    def __init__(self, store, sessions_dir, *, max_bytes=256 << 20, max_files=512,
                 max_entries=50000, files_per_poll=8, records_per_file=500, recent_seconds=86400, source_format="codex"):
        if not (1 <= max_files <= 512 and 1 <= max_entries <= 50000 and
                1 <= files_per_poll <= 8 and 1 <= records_per_file <= 500 and recent_seconds > 0):
            raise ValueError('Invalid collector limits')
        if source_format not in ("codex", "claude"):
            raise ValueError("Unsupported activity source format")
        self.source_format = source_format
        self.store = store
        self.root = Path(os.path.realpath(sessions_dir))
        self.max_bytes, self.max_files, self.max_entries = max_bytes, max_files, max_entries
        self.files_per_poll, self.records_per_file, self.recent_seconds = files_per_poll, records_per_file, recent_seconds
        self.entries, self.queue = {}, deque()
        self.paused = not store.set_maximum_size(max_bytes)
        self.total = 0
        self.started_at = utc_now()
        self.last = self._status('starting', False, True, 0, None)

    def _scan(self, now):
        found, stack, count, complete = {}, [(self.root, 0)], 0, True
        # A selected symlink root is resolved once, but children are never followed.
        if self.root.is_symlink() or not self.root.is_dir():
            return found, False, False
        while stack:
            directory, depth = stack.pop()
            try:
                if directory.is_symlink() or not directory.resolve().is_relative_to(self.root):
                    complete = False
                    continue
                with os.scandir(directory) as iterator:
                    for child in iterator:
                        count += 1
                        if count > self.max_entries:
                            return found, True, False
                        if child.is_symlink():
                            continue
                        if child.is_dir(follow_symlinks=False):
                            if depth < 5:
                                stack.append((Path(child.path), depth + 1))
                            else:
                                complete = False
                        elif child.name.endswith('.jsonl') and child.is_file(follow_symlinks=False):
                            info = child.stat(follow_symlinks=False)
                            path = child.path
                            revision = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                            old = self.entries.get(path)
                            if info.st_mtime >= now - self.recent_seconds or (old and (old.pending or old.failures or old.seen != revision)):
                                found[path] = (info.st_mtime, revision)
            except OSError:
                complete = False
        return found, True, complete

    def poll(self, *, now=None, monotonic=None):
        now = time.time() if now is None else now
        clock = time.monotonic() if monotonic is None else monotonic
        found, available, complete = self._scan(now)
        discovered = len(found)
        # Keep unfinished work when discovery is temporarily incomplete. No saved history is removed.
        for path in list(self.entries):
            if path not in found and complete:
                del self.entries[path]
        candidates = sorted(found, key=lambda p: (-found[p][0], p))
        for path in candidates:
            if path not in self.entries:
                if len(self.entries) >= self.max_files:
                    complete = False
                    continue
                self.entries[path] = Entry()
                self.queue.append(path)
            entry = self.entries[path]
            revision = found[path][1]
            if entry.revision != revision:
                entry.retry_at = 0
            entry.revision = revision
        self.queue = deque(p for p in self.queue if p in self.entries)
        if self.store.database_bytes() > self.max_bytes:
            self.paused = True
        attempted, saved = 0, 0
        if available and not self.paused:
            for _ in range(len(self.queue)):
                if attempted >= self.files_per_poll:
                    break
                path = self.queue.popleft(); self.queue.append(path)
                entry = self.entries[path]
                if path not in found or clock < entry.retry_at or (not entry.pending and not entry.failures and entry.seen == entry.revision):
                    continue
                attempted += 1
                try:
                    result = self.store.ingest(path, max_records=self.records_per_file, source_root=self.root, source_format=self.source_format)
                    saved += result['events_saved']
                    entry.pending = result['batch_full']
                    entry.seen = entry.revision
                    entry.failures = 0
                    entry.retry_at = 0
                except sqlite3.Error as exc:
                    code = getattr(exc, 'sqlite_errorcode', None)
                    if code == 13 or str(exc) == 'database or disk is full':
                        self.paused = True
                        break
                    if code not in (5, 6) and 'locked' not in str(exc):
                        raise  # Corrupt / unusable DB is not a per-source error.
                    entry.failures += 1
                    entry.retry_at = clock + min(60, 2 ** min(entry.failures, 6))
                except (OSError, ValueError, KeyError, TypeError, OverflowError):
                    entry.failures += 1
                    entry.retry_at = clock + min(60, 2 ** min(entry.failures, 6))
        self.total += saved
        errors = sum(e.failures > 0 for e in self.entries.values())
        issue = 'storage_full' if self.paused else 'source_unavailable' if not available else 'scan_incomplete' if not complete else 'source_errors' if errors else None
        state = 'paused_capacity' if self.paused else 'source_unavailable' if not available else 'degraded' if issue else 'active' if saved or any(e.pending or e.seen != e.revision for e in self.entries.values()) else 'waiting'
        self.last = self._status(state, available, complete, discovered, issue)
        return self.last

    def _status(self, state, available, complete, discovered, issue):
        return dict(collector_schema=1, state=state, updated_at=utc_now(), started_at=self.started_at,
                    discovered_files=discovered, tracked_files=len(self.entries),
                    pending_files=sum(e.pending or e.failures > 0 or e.seen != e.revision for e in self.entries.values()),
                    error_files=sum(e.failures > 0 for e in self.entries.values()),
                    events_saved_this_run=self.total, database_bytes=self.store.database_bytes(),
                    max_database_bytes=self.max_bytes, scan_complete=complete, last_scan_at=utc_now(),
                    source_available=available, issue=issue, source_format=self.source_format, mode='live', backend='python')

    def stopped(self):
        self.last = dict(self.last, state='stopped', updated_at=utc_now())
        return self.last


def validate_status_path(path, database, sessions_dir):
    path = Path(path).absolute()
    root = Path(os.path.realpath(sessions_dir))
    resolved = Path(os.path.realpath(path))
    db = os.path.realpath(database)
    if resolved.is_relative_to(root) or str(resolved) in (db, db+'-journal', db+'-wal', db+'-shm', db+'.collector.lock') or path.is_symlink():
        raise ValueError('Status must be separate from the source directory and database')
    if path.exists():
        if path.stat().st_size > 65536:
            raise ValueError('Refusing to replace an unrelated status file')
        try:
            value = json.loads(path.read_text())
            if not isinstance(value, dict) or value.get('collector_schema') != 1:
                raise ValueError()
        except (ValueError, UnicodeError):
            raise ValueError('Refusing to replace an unrelated status file') from None
    return path


def write_status(path, status):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            tmp = stream.name
            json.dump(status, stream, sort_keys=True, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
