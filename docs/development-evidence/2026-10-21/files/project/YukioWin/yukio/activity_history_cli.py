"""Explicit local history import/follow/query commands; no desktop UI startup."""
import json
import math
import sys
import sqlite3
import time

from .activity_history import ActivityHistory, source_revision


def run_activity_history(argv):
    store = None
    try:
        command = next(flag for flag in ('--activity-import', '--activity-follow', '--activity-history') if flag in argv)
        i = argv.index(command)
        needed = 1 if command == '--activity-history' else 2
        if len(argv) <= i + needed or any(v.startswith('--') for v in argv[i+1:i+needed+1]):
            raise ValueError('Usage: --activity-import DB SOURCE | --activity-follow DB SOURCE [--seconds N] | --activity-history DB [--after N] [--limit N] [--session ID]')
        def option(key, default):
            if key not in argv:
                return default
            j = argv.index(key)
            if j + 1 >= len(argv) or argv[j+1].startswith('--'):
                raise ValueError('Missing value for ' + key)
            return argv[j+1]
        source_format = option('--source-format', 'codex')
        if source_format not in ('codex', 'claude'):
            raise ValueError('Unsupported activity source format')
        seconds = float(option('--seconds', '0'))
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Seconds must be finite and nonnegative')
        store = ActivityHistory(argv[i+1], readonly=command == '--activity-history')
        if command == '--activity-history':
            for row in store.rows(after=int(option('--after', '0')), limit=int(option('--limit', '500')), session=option('--session', None)):
                print(json.dumps(row, ensure_ascii=False, sort_keys=True))
            return 0
        start = time.monotonic()
        revision, batch_full = None, True
        while True:
            current = source_revision(argv[i+2])
            if current != revision or batch_full:
                result = store.ingest(argv[i+2], source_format=source_format)
                print(json.dumps(result, sort_keys=True), flush=True)
                batch_full = result['batch_full']
                if not batch_full:
                    revision = current
            elapsed = time.monotonic() - start
            if command == '--activity-follow' and seconds and elapsed >= seconds:
                return 0
            if batch_full:
                continue
            if command == '--activity-import':
                return 0
            time.sleep(min(2, max(0, seconds - elapsed)) if seconds else 2)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError, sqlite3.Error) as exc:
        print('Activity history failed: %s' % exc, file=sys.stderr)
        return 1
    finally:
        if store:
            store.close()
