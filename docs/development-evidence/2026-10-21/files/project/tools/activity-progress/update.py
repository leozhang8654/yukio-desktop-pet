#!/usr/bin/env python3
"""Maintain evidence-backed project status locally; the website itself is read-only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--note', required=True)
parser.add_argument('--work-state')
parser.add_argument('--complete-auto', action='store_true')
parser.add_argument('--checks', type=int, choices=range(4))
args = parser.parse_args()
path = Path(__file__).with_name('progress.json')
p = json.loads(path.read_text())
p['updated_at'] = datetime.now(timezone.utc).isoformat()
p['current_note'] = args.note
p['updates'].append(dict(at=p['updated_at'], text=args.note))
if args.work_state:
    p['work_state'] = args.work_state
stage = next(s for s in p['stages'] if s['id'] == 'auto')
if args.checks is not None:
    for n, check in enumerate(stage['checks']):
        check['done'] = n < args.checks
if args.complete_auto:
    stage['status'] = 'complete'
with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
    json.dump(p, stream, ensure_ascii=False, indent=2); stream.write('\n'); tmp=stream.name
os.replace(tmp, path)
print('Progress updated at', p['updated_at'])
