"""Read-only metadata export; no network, transcript retention or app startup."""
import hashlib
import json
import os
import sys

from .events import parse_timestamp
from .parsers_codex import CodexRolloutParser, session_id_from_file_name


def run_codex_results(path):
    parser = CodexRolloutParser(session_id_from_file_name(os.path.basename(path)))
    try:
        with open(path, 'rb') as source:
            number = 0
            while True:
                raw = source.readline((8 << 20) + 2)
                if not raw:
                    break
                number += 1
                data = raw[:-1] if raw.endswith(b'\n') else raw
                if len(data) > 8 << 20:
                    raise ValueError('A source line exceeds the 8 MiB diagnostic limit')
                if not data.strip():
                    continue
                try:
                    obj = json.loads(data)
                    if not isinstance(obj, dict):
                        raise ValueError()
                except (ValueError, UnicodeError):
                    raise ValueError('Invalid JSON object at line %d' % number) from None
                parser.events(obj)
                payload = obj.get('payload')
                payload = payload if isinstance(payload, dict) else obj
                for result in parser.last_tool_results:
                    row = result.to_dict()
                    row.update(source_line=number, source_record_sha256=hashlib.sha256(data).hexdigest(),
                               timestamp_available=(parse_timestamp(obj.get('timestamp')) is not None
                                                    or parse_timestamp(payload.get('timestamp')) is not None))
                    print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print('Codex results export failed: %s' % exc, file=sys.stderr)
        return 1
