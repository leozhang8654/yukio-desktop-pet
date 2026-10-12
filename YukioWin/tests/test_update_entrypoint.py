import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

class UpdateEntrypointTests(unittest.TestCase):
    def run_entry(self, report, fail=False):
        calls = []
        updater = types.ModuleType('yukio.update_smoke')
        def run(args):
            calls.append(args)
            if fail:
                raise ValueError('upgrade verification failed')
            return 0
        updater.run = run
        cli = types.ModuleType('yukio.cli')
        cli.main = lambda: self.fail('Update check incorrectly reached normal startup')
        entry = Path(__file__).resolve().parents[1] / 'run.py'
        args = [str(entry), '--update-smoke', 'feed', str(report), '0.4.3']
        with patch.object(sys, 'argv', args), patch.object(sys, 'path', list(sys.path)), \
             patch.dict(sys.modules, {'yukio.cli': cli, 'yukio.update_smoke': updater}):
            with self.assertRaises(SystemExit) as exit:
                runpy.run_path(str(entry), run_name='__main__')
        return exit.exception.code, calls

    def test_expected_version_reaches_upgrade_check(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'result.json'
            code, calls = self.run_entry(report)
            self.assertEqual(code, 0)
            self.assertEqual(calls, [['--update-smoke', 'feed', str(report), '0.4.3']])

    def test_failure_writes_report_instead_of_hanging(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'result.json'
            code, _ = self.run_entry(report, True)
            self.assertEqual(code, 1)
            self.assertIn('upgrade verification failed', report.with_suffix('.error.txt').read_text())
