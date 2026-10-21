import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from yukio.codex_results_replay import run_codex_results


class CodexResultsReplayTests(unittest.TestCase):
    def replay(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.jsonl'
            path.write_bytes(data)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = run_codex_results(str(path))
            return code, out.getvalue(), err.getvalue()

    def test_evidence_location_and_body_omission(self):
        line = json.dumps({'type': 'function_call_output', 'call_id': 'a', 'output': {
            'success': False, 'output': 'PRIVATE_BODY_SENTINEL'}}).encode()
        code, out, err = self.replay(b'\n' + line + b'\n' + line)
        self.assertEqual(code, 0)
        self.assertEqual(err, '')
        self.assertNotIn('PRIVATE_BODY_SENTINEL', out)
        rows = [json.loads(row) for row in out.splitlines()]
        self.assertEqual([r['source_line'] for r in rows], [2, 3])
        self.assertEqual(rows[0]['source_record_sha256'], hashlib.sha256(line).hexdigest())
        self.assertFalse(rows[0]['timestamp_available'])
        self.assertEqual(rows[0]['outcome'], 'failed')

    def test_invalid_json_reports_line_and_failure(self):
        code, out, err = self.replay(b'\n{broken\n')
        self.assertEqual(code, 1)
        self.assertEqual(out, '')
        self.assertIn('line 2', err)

    def test_oversized_record_is_not_silently_truncated(self):
        code, out, err = self.replay(b' ' * ((8 << 20) + 1))
        self.assertEqual(code, 1)
        self.assertEqual(out, '')
        self.assertIn('8 MiB', err)
