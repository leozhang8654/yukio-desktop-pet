"""Compare both actual diagnostic executables on constructed, shared fixtures.

Run from any directory after `swift build --package-path YukioPlayer`.
Uses no network or real conversations. Output is a compact JSON verification record.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / 'tests/fixtures/codex-results-v1.json').read_text())['cases']
    binary = root / 'YukioPlayer/.build/debug/YukioPlayer'
    if not binary.is_file():
        raise SystemExit('Build YukioPlayer first: swift build --package-path YukioPlayer')
    commands = [[str(binary), '--codex-results'], [sys.executable, '-m', 'yukio', '--codex-results']]
    with tempfile.TemporaryDirectory(prefix='yukio-results-parity-') as directory:
        source = Path(directory) / 'synthetic.jsonl'
        rows = []
        for case in cases:
            rows.append(dict(type='session_meta', id='synthetic-' + case['name']))
            rows.extend(step['record'] for step in case['steps'])
        source.write_text(''.join(json.dumps(row) + '\n' for row in rows))

        def run():
            return [subprocess.run(cmd + [str(source)], cwd=root / 'YukioWin',
                                   capture_output=True, text=True, check=False) for cmd in commands]

        executions = run()
        assert all(e.returncode == 0 for e in executions), [e.stderr for e in executions]
        parsed = [[json.loads(row) for row in e.stdout.splitlines()] for e in executions]
        assert parsed[0] == parsed[1], 'Swift/Python result metadata differs'
        for data in (b'\n{broken\n', b' ' * ((8 << 20) + 1)):
            source.write_bytes(data)
            errors = run()
            assert all(e.returncode == 1 for e in errors), 'Invalid input must fail explicitly'
        print(json.dumps(dict(shared_scenarios=len(cases), result_records=len(parsed[0]),
                              exact_metadata_parity=True, malformed_json_rejected=True,
                              oversized_record_rejected=True, native_windows_test=False), indent=2))


if __name__ == '__main__':
    main()
