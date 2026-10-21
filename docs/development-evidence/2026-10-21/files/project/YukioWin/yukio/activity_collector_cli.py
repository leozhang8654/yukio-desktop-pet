"""Explicit, headless multi-session collection. No cloud or desktop app startup."""
import argparse
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time
import math

from .activity_history import ActivityHistory
from .activity_collector import ActivityCollector, validate_status_path, write_status, utc_now
from .sources import codex_sessions_dir, claude_projects_dir


class CollectorLease:
    """One collector per canonical DB; readers and manual import remain possible."""
    def __init__(self, database):
        path = Path(os.path.realpath(database) + '.collector.lock')
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError('Collector lock cannot be a symbolic link')
        fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        self.stream = os.fdopen(fd, 'r+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    self.stream.write(b'0'); self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise ValueError('Another collector already owns this activity database') from None

    def close(self):
        self.stream.close()  # Closing releases the OS lock; do not unlink a lock others may hold.


def run_activity_collector(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--activity-collect', required=True, metavar='DB')
    parser.add_argument('--source-format', choices=('codex', 'claude'), default='codex')
    parser.add_argument('--sessions-dir')
    parser.add_argument('--status-file')
    parser.add_argument('--seconds', type=float, default=0)
    parser.add_argument('--max-database-mb', type=int, default=256)
    args = parser.parse_args(argv)
    if args.sessions_dir is None:
        args.sessions_dir = claude_projects_dir() if args.source_format == 'claude' else codex_sessions_dir()
    store = collector = status = None
    leases = []
    previous = {}
    failure = False
    try:
        if not math.isfinite(args.seconds) or args.seconds < 0 or not 1 <= args.max_database_mb <= 4096:
            raise ValueError('Seconds must be finite/nonnegative; database limit must be 1..4096 MiB')
        if args.status_file:
            status = validate_status_path(args.status_file, args.activity_collect, args.sessions_dir)
        leases.append(CollectorLease(args.activity_collect))
        if status:
            leases.append(CollectorLease(status))
        store = ActivityHistory(args.activity_collect)
        collector = ActivityCollector(store, args.sessions_dir, max_bytes=args.max_database_mb << 20, source_format=args.source_format)
        def stop(*_):
            raise KeyboardInterrupt
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, stop)
        start = time.monotonic()
        while True:
            snapshot = collector.poll()
            if status:
                write_status(status, snapshot)
            elapsed = time.monotonic() - start
            if args.seconds and elapsed >= args.seconds:
                break
            time.sleep(min(2, max(0, args.seconds - elapsed)) if args.seconds else 2)
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, OverflowError):
        failure = True
        # No file paths, transcript content or raw database errors in routine logs.
        print('Activity collector could not continue; check local paths, database ownership and storage.', file=sys.stderr)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if collector:
            snapshot = dict(collector.last, state='failed', issue='collector_error', updated_at=utc_now()) if failure else collector.stopped()
            if status:
                try:
                    write_status(status, snapshot)
                except (OSError, ValueError):
                    failure = True
            print(json.dumps(snapshot, sort_keys=True), flush=True)
        if store:
            store.close()
        for lease in reversed(leases):
            lease.close()
    return 1 if failure else 0
