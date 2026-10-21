"""Local metadata journal for explicitly selected Codex JSONL files.

Each batch commits evidence, correlation state and complete-line cursor together.
No transcript bodies are retained. One connection is used by one caller/thread.
"""
import hashlib
import json
import os
import sqlite3
import stat

from .codex_results import structured
from .claude_history import ClaudeHistoryParser
from .events import parse_timestamp
from .parsers_codex import CodexRolloutParser

APPLICATION_ID = 1498762063
MAX_LINE = 8 << 20
MAX_BATCH = 500


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def metadata_record(obj):
    """Allowlist parser inputs; never pass text, arguments or scripts to history."""
    def fields(value, keys):
        return {k: value[k] for k in keys if isinstance(value.get(k), str) and len(value[k]) <= 1024}

    def outcome_fields(value):
        out = fields(value, ('status',))
        for key in ('success', 'isError'):
            if type(value.get(key)) is bool:
                out[key] = value[key]
        metadata = value.get('metadata') if isinstance(value.get('metadata'), dict) else {}
        code = value.get('exit_code', metadata.get('exit_code'))
        if type(code) in (int, float) and -(2**63) <= code < 2**63 and int(code) == code:
            out['exit_code'] = int(code)
        result = value.get('result') if isinstance(value.get('result'), dict) else {}
        if type(result.get('isError')) is bool:
            out['result'] = {'isError': result['isError']}
        return out

    out = fields(obj, ('type', 'timestamp'))
    payload = obj.get('payload') if isinstance(obj.get('payload'), dict) else obj
    p = fields(payload, ('type', 'timestamp', 'session_id', 'thread_id', 'id', 'turn_id',
                         'call_id', 'name', 'namespace', 'role'))
    if 'output' in payload:
        try:
            output = structured(payload['output'])
        except RecursionError:
            output = {}
        p['output'] = outcome_fields(output)
    item = payload.get('item')
    if isinstance(item, dict):
        p['item'] = fields(item, ('type', 'id', 'call_id'))
        p['item'].update(outcome_fields(item))
    out['payload'] = p
    return out


KINDS = {
    'function_call': 'tool_requested', 'custom_tool_call': 'tool_requested', 'local_shell_call': 'tool_requested',
    'function_call_output': 'tool_result', 'custom_tool_call_output': 'tool_result', 'local_shell_call_output': 'tool_result',
    'task_started': 'turn_started', 'turn_context': 'turn_context', 'task_complete': 'turn_ended',
    'turn_aborted': 'turn_cancelled', 'error': 'source_error', 'stream_error': 'source_error',
    'session_meta': 'session_observed', 'message': 'message_observed', 'reasoning': 'reasoning_record_observed',
    'item_started': 'item_started', 'item_updated': 'item_updated', 'item_completed': 'item_completed',
    'web_search_call': 'web_search_observed',
}


def observation(raw, parser):
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError()
    except (ValueError, UnicodeError, RecursionError):
        # A missing record may contain a turn boundary. Forget correlation across this gap.
        return dict(kind='invalid_record', evidence_class='observed', timestamp_available=False, session_id=parser.session), CodexRolloutParser(parser.session)
    obj = metadata_record(obj)
    p = obj['payload']
    source_kind = p.get('type', obj.get('type', ''))
    parser.events(obj)
    row = dict(kind=KINDS.get(source_kind, 'unrecognized_record'), source_kind=source_kind,
               evidence_class='observed', session_id=parser.session,
               timestamp_available=False)
    timestamp = parse_timestamp(obj.get('timestamp'))
    if timestamp is None:
        timestamp = parse_timestamp(p.get('timestamp'))
    if timestamp is not None:
        row.update(timestamp_ms=timestamp, timestamp_available=True)
    # This is the identity reported by this record, not an invented causal link.
    for key in ('thread_id', 'turn_id', 'call_id', 'id', 'name'):
        if key in p:
            row[{'thread_id': 'reported_thread_id', 'id': 'reported_id', 'name': 'tool_name'}.get(key, key)] = p[key]
    if parser._results.turn_id is not None:
        row['context_turn_id'] = parser._results.turn_id
    if isinstance(p.get('item'), dict):
        for key in ('id', 'type'):
            if key in p['item']:
                row['item_' + key] = p['item'][key]
    if parser.last_tool_results:
        row['kind'] = 'tool_result'
        row['result'] = parser.last_tool_results[0].to_dict()
    if p.get('thread_id') and p['thread_id'] != parser.session:
        row['kind'] = 'foreign_session_record'
        row['source_session_id'] = parser.session
        row['session_id'] = p['thread_id']
        row.pop('context_turn_id', None)
    return row, parser


def hash_prefix(stream, size):
    stream.seek(0)
    digest = hashlib.sha256()
    left = size
    while left:
        data = stream.read(min(left, 1 << 20))
        if not data:
            raise ValueError('Source changed while reading; no batch was saved')
        digest.update(data)
        left -= len(data)
    return digest


def source_revision(path):
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('History sources must be regular files')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def open_source(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('History sources must be regular files')
        return os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise


class ActivityHistory:
    def __init__(self, path, *, readonly=False):
        self.path = os.path.abspath(path)
        self.readonly = readonly
        if readonly:
            from pathlib import Path
            self.db = sqlite3.connect(Path(self.path).as_uri() + '?mode=ro', uri=True, isolation_level=None, timeout=1)
        else:
            os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                pass
            self.db = sqlite3.connect(self.path, isolation_level=None, timeout=1)
        try:
            if not readonly:
                self.db.execute('PRAGMA synchronous=FULL')
                self.db.execute('BEGIN IMMEDIATE')
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            app = self.db.execute('PRAGMA application_id').fetchone()[0]
            tables = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if not readonly and version == 0 and app == 0 and not tables:
                self.db.execute('CREATE TABLE sources (source_id TEXT PRIMARY KEY, state TEXT NOT NULL)')
                self.db.execute('CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, session_id TEXT, record TEXT NOT NULL)')
                self.db.execute('CREATE INDEX events_session ON events(session_id, sequence)')
                self.db.execute('PRAGMA application_id=%d' % APPLICATION_ID)
                self.db.execute('PRAGMA user_version=1')
            elif version != 1 or app != APPLICATION_ID:
                raise ValueError('Not a supported Yukio activity database; existing data was not replaced')
            if not readonly:
                self.db.execute('COMMIT')
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def set_maximum_size(self, byte_limit):
        """Connection-local DB growth cap. Never shrink or delete existing history."""
        if self.readonly or type(byte_limit) is not int or byte_limit <= 0:
            raise ValueError('Invalid database size limit')
        page_size = self.db.execute('PRAGMA page_size').fetchone()[0]
        pages = max(1, byte_limit // page_size)
        actual = self.db.execute('PRAGMA max_page_count=%d' % pages).fetchone()[0]
        return actual * page_size <= byte_limit

    def database_bytes(self):
        return self.db.execute('PRAGMA page_count').fetchone()[0] * self.db.execute('PRAGMA page_size').fetchone()[0]

    def rows(self, *, after=0, limit=500, session=None):
        if after < 0 or not 1 <= limit <= 10000:
            raise ValueError('Invalid history page')
        query = 'SELECT sequence, record FROM events WHERE sequence > ?'
        args = [after]
        if session is not None:
            query += ' AND session_id = ?'
            args.append(session)
        query += ' ORDER BY sequence LIMIT ?'
        args.append(limit)
        return [dict(json.loads(row), sequence=sequence) for sequence, row in self.db.execute(query, args)]

    def _insert(self, row):
        self.db.execute('INSERT INTO events(event_id, session_id, record) VALUES (?, ?, ?)',
                        (row['event_id'], row.get('session_id'), compact(row)))

    def ingest(self, source, *, max_records=MAX_BATCH, source_root=None, source_format="codex"):
        if source_format not in ('codex', 'claude'):
            raise ValueError('Unsupported activity source format')
        if self.readonly or not 1 <= max_records <= MAX_BATCH:
            raise ValueError('Invalid history write request')
        path = os.path.realpath(os.path.abspath(source))
        if source_root is not None and (os.path.islink(source) or os.path.commonpath((path, os.path.realpath(source_root))) != os.path.realpath(source_root)):
            raise ValueError('Source is outside the selected session directory')
        if path in (os.path.realpath(self.path), os.path.realpath(self.path) + '-journal',
                    os.path.realpath(self.path) + '-wal', os.path.realpath(self.path) + '-shm'):
            raise ValueError('The activity database cannot be its own source')
        if os.path.samefile(path, self.path):
            raise ValueError('The activity database cannot be its own source')
        source_id = hashlib.sha256(path.encode('utf-8')).hexdigest()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            saved = self.db.execute('SELECT state FROM sources WHERE source_id=?', (source_id,)).fetchone()
            old = json.loads(saved[0]) if saved else None
            if old and old.get('source_format', 'codex') != source_format:
                raise ValueError('Source format differs from saved history; no data was changed')
            with open_source(path) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError('History sources must be regular files')
                identity = '%s:%s' % (info.st_dev, info.st_ino)
                offset, line, generation = (old['offset'], old['line'], old['generation']) if old else (0, 0, 1)
                reason = None
                if old:
                    if old['file_identity'] != identity:
                        reason = 'file_replaced'
                    elif info.st_size < offset:
                        reason = 'file_truncated'
                    elif hash_prefix(stream, offset).hexdigest() != old['prefix_sha256']:
                        reason = 'prefix_changed'
                if reason:
                    offset, line, generation = 0, 0, generation + 1
                parser_type = ClaudeHistoryParser if source_format == 'claude' else CodexRolloutParser
                parser = (parser_type.from_history_checkpoint(json.loads(old['checkpoint']))
                          if old and not reason else parser_type('source-' + source_id))
                digest = hash_prefix(stream, offset)
                count, inserted = 0, 0
                if reason:
                    self._insert(dict(event_id='%s:%d:reset' % (source_id, generation), source_id=source_id,
                                      generation=generation, kind='source_reset', reason=reason, evidence_class='observed',
                                      schema_version=1, source=source_format, timestamp_available=False))
                    inserted += 1
                while count < max_records:
                    raw = stream.readline(MAX_LINE + 2)
                    data = raw[:-1] if raw.endswith(b'\n') else raw
                    if len(data) > MAX_LINE:
                        raise ValueError('Source record exceeds 8 MiB; no batch was saved')
                    if not raw.endswith(b'\n'):
                        break  # Do not acknowledge a partially written record, even valid JSON.
                    next_offset = offset + len(raw)
                    line += 1
                    count += 1
                    digest.update(raw)
                    if data.strip():
                        evidence_id = '%s:%d:%d' % (source_id, generation, offset)
                        if source_format == 'claude':
                            row = parser.observe(data, evidence_id)
                        else:
                            row, parser = observation(data, parser)
                        row.update(event_id='%s:%d:%d' % (source_id, generation, offset),
                                   schema_version=1, source=source_format, source_id=source_id, generation=generation,
                                   source_line=line, source_offset=offset, next_offset=next_offset,
                                   source_record_sha256=hashlib.sha256(data).hexdigest())
                        self._insert(row)
                        inserted += 1
                    offset = next_offset
                # Validate the bytes actually consumed, including in-place edits during this batch.
                if hash_prefix(stream, offset).hexdigest() != digest.hexdigest():
                    raise ValueError('Source changed while reading; no batch was saved')
                current = os.stat(path)
                if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError('Source replaced while reading; no batch was saved')
                state = dict(source_format=source_format, generation=generation, file_identity=identity, offset=offset, line=line,
                             prefix_sha256=digest.hexdigest(), checkpoint=compact(parser.history_checkpoint()))
                self.db.execute('INSERT INTO sources VALUES (?, ?) ON CONFLICT(source_id) DO UPDATE SET state=excluded.state',
                                (source_id, compact(state)))
            self.db.execute('COMMIT')
            return dict(records_read=count, events_saved=inserted, offset=offset, generation=generation,
                        batch_full=count == max_records)
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise
