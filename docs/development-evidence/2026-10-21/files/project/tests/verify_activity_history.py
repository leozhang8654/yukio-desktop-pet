"""Exercise both real history CLIs with synthetic data and shared databases.

Run after swift build. No real transcripts or network. Native Windows is not tested.
"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time


def main():
    root = Path(__file__).resolve().parents[1]
    commands = [[str(root / 'YukioPlayer/.build/debug/YukioPlayer')], [sys.executable, '-m', 'yukio']]
    def run(which, args, ok=True):
        result = subprocess.run(commands[which] + [str(a) for a in args], cwd=root / 'YukioWin',
                                capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == ok, (which, result.returncode, result.stderr)
        return [json.loads(s) for s in result.stdout.splitlines()] if ok else result
    cases = json.loads((root / 'tests/fixtures/codex-results-v1.json').read_text())['cases']
    with tempfile.TemporaryDirectory(prefix='yukio-history-integration-') as directory:
        d = Path(directory)
        dbs = [d / 'swift.db', d / 'python.db']
        for case in cases:
            source = d / (case['name'] + '.jsonl')
            source.write_text(json.dumps(dict(type='session_meta', id='synthetic-session')) + '\n'
                              + ''.join(json.dumps(step['record']) + '\n' for step in case['steps']))
            for i in range(2):
                run(i, ['--activity-import', dbs[i], source])
                assert run(i, ['--activity-import', dbs[i], source])[-1]['events_saved'] == 0
        rows = [run(i, ['--activity-history', dbs[i], '--limit', 10000]) for i in range(2)]
        assert rows[0] == rows[1], 'History evidence differs between implementations'
        assert run(0, ['--activity-history', dbs[1], '--limit', 10000]) == rows[1]
        assert run(1, ['--activity-history', dbs[0], '--limit', 10000]) == rows[0]
        result_count = sum('result' in row for row in rows[0])

        # Sanitizing must not turn an unsupported nested string into a machine result.
        outputs = [({'result': '{"isError": true}'}, 'unknown'),
                   ({'metadata': '{"exit_code": 1}'}, 'unknown'),
                   ({'exit_code': 2**63-1}, 'failed'),
                   ({'exit_code': True}, 'unknown'),
                   ({'exit_code': 1.5}, 'unknown'),
                   ('[' * 2000 + ']' * 2000, 'unknown')]
        edge_source = d / 'edge.jsonl'
        edge_source.write_text(''.join(json.dumps(dict(type='function_call_output', call_id=str(n), output=out)) + '\n'
                                       for n, (out, _) in enumerate(outputs)))
        edge_rows = []
        for i in range(2):
            edge_db = d / ('edge%d.db' % i)
            run(i, ['--activity-import', edge_db, edge_source])
            edge_rows.append(run(i, ['--activity-history', edge_db]))
            assert [row['result']['outcome'] for row in edge_rows[-1]] == [outcome for _, outcome in outputs]
        assert edge_rows[0] == edge_rows[1]

        # Both implementations must resume the other's checkpoint, even mid-call.
        for first in range(2):
            db, source = d / ('mixed%d.db' % first), d / ('mixed%d.jsonl' % first)
            source.write_text('{"type":"session_meta","id":"s"}\n{"type":"task_started","turn_id":"t"}\n{"type":"function_call","name":"shell","call_id":"a"}\n')
            run(first, ['--activity-import', db, source])
            with source.open('a') as stream:
                stream.write('{"type":"item_completed","item":{"type":"CommandExecution","id":"a","exit_code":1}}\n')
            run(1-first, ['--activity-import', db, source])
            with source.open('a') as stream:
                stream.write('{"type":"function_call_output","call_id":"a","output":{"success":true}}\n')
            run(first, ['--activity-import', db, source])
            mixed = run(1-first, ['--activity-history', db])
            assert mixed[-2]['result']['association'] == 'matching_item_id'
            assert mixed[-1]['result']['conflicting_results']
            assert mixed[-1]['result']['turn_id'] == 't'

        for i in range(2):
            db, source = d / ('follow%d.db' % i), d / ('follow%d.jsonl' % i)
            source.write_text('{"type":"session_meta","id":"follow"}\n')
            run(i, ['--activity-import', db, source])
            proc = subprocess.Popen(commands[i] + ['--activity-follow', str(db), str(source), '--seconds', '0.6'],
                                    cwd=root / 'YukioWin', stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                time.sleep(0.15)
                with source.open('a') as stream:
                    stream.write('{"type":"function_call","name":"shell","call_id":"later"}\n')
                output, error = proc.communicate(timeout=10)
                assert proc.returncode == 0, error
            finally:
                if proc.poll() is None:
                    proc.kill(); proc.wait()
            history = run(i, ['--activity-history', db])
            assert len(history) == 2 and history[-1]['call_id'] == 'later'
            # Storage errors must return failure, preserve prior rows/cursor, retry once fixed.
            connection = sqlite3.connect(db)
            connection.execute("CREATE TRIGGER fail_cursor BEFORE INSERT ON sources BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
            connection.close()
            with source.open('a') as stream:
                stream.write('{"type":"function_call_output","call_id":"later","output":{"success":true}}\n')
            run(i, ['--activity-import', db, source], ok=False)
            assert run(i, ['--activity-history', db]) == history
            connection = sqlite3.connect(db); connection.execute('DROP TRIGGER fail_cursor'); connection.close()
            assert run(i, ['--activity-import', db, source])[-1]['events_saved'] == 1
            # Query is read-only and cannot create a missing DB. Missing CLI arguments fail.
            missing = d / ('missing%d.db' % i)
            run(i, ['--activity-history', missing], ok=False)
            assert not missing.exists()
            run(i, ['--activity-import', db], ok=False)
            run(i, ['--activity-history', db, '--limit', '-1'], ok=False)
        print(json.dumps(dict(shared_scenarios=len(cases), evidence_rows=len(rows[0]), result_rows=result_count,
                              exact_history_parity=True, metadata_edge_cases=len(outputs), cross_implementation_resume=True, live_follow=True,
                              storage_failure_rollback_and_retry=True, read_only_query=True,
                              native_windows_test=False), indent=2))


if __name__ == '__main__':
    main()
