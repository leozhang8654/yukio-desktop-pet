import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
from yukio.settings import Settings
from yukio.updater import UpdateController, automatic_check_due, should_notify, CHECK_INTERVAL


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = Settings(str(Path(self.tmp.name) / 'settings.json'))
        self.controller = UpdateController.__new__(UpdateController)
        c = self.controller
        c.settings = self.settings
        c.app = NS(quit=Mock())
        c.root = NS(after=Mock())
        c.busy = False
        c.closed = False
        c.window = None
        c.pending = None
        c.manual = False
        c.events = queue.Queue()
        c.manager = Mock()
        c._show = Mock()
        c._worker = lambda work: work()
        self.update = NS(IsDowngrade=False, TargetFullRelease=NS(Version='0.4.1', NotesMarkdown='Fixed animation'))

    def test_check_interval_opt_out_and_clock_rollback(self):
        self.assertTrue(automatic_check_due(self.settings, CHECK_INTERVAL + 1))
        self.settings.set('updateLastCheck', 100)
        self.assertFalse(automatic_check_due(self.settings, 101))
        self.assertTrue(automatic_check_due(self.settings, 50))
        self.settings.set('automaticUpdates', False)
        self.assertFalse(automatic_check_due(self.settings, CHECK_INTERVAL * 2))

    def test_corrupted_timestamp_does_not_disable_future_checks(self):
        for value in ('invalid', None, float('nan')):
            self.settings.set('updateLastCheck', value)
            self.assertTrue(automatic_check_due(self.settings, CHECK_INTERVAL + 1))

    def test_opt_out_while_checking_suppresses_background_prompt(self):
        self.settings.set('automaticUpdates', False)
        self.controller._handle('checked', self.update)
        self.controller._show.assert_not_called()

    def test_defer_persists_but_a_new_version_is_announced(self):
        c = self.controller
        c.pending = self.update
        c._later()
        reloaded = Settings(self.settings.path)
        self.assertFalse(should_notify(reloaded, '0.4.1', 0))
        self.assertTrue(should_notify(reloaded, '0.4.2', 0))
        self.assertTrue(should_notify(reloaded, '0.4.1', reloaded.get('updateDeferredUntil')))

    def test_automatic_discovery_shows_notes_without_installing(self):
        c = self.controller
        c._handle('checked', self.update)
        self.assertEqual(c._show.call_args.kwargs['notes'], 'Fixed animation')
        self.assertTrue(c._show.call_args.kwargs['install'])
        c.manager.download_updates.assert_not_called()
        c.app.quit.assert_not_called()

    def test_no_update_and_network_failure_are_quiet_in_background(self):
        c = self.controller
        c._handle('checked', None)
        c._handle('error', 'offline')
        c._show.assert_not_called()
        c.app.quit.assert_not_called()
        c.manual = True
        c._handle('error', 'offline')
        self.assertTrue(c._show.call_args.kwargs['retry'])

    def test_manual_check_ignores_disabled_automatic_preference_and_defer(self):
        c = self.controller
        self.settings.set('automaticUpdates', False)
        c.pending = self.update
        c._later()
        c.manager.check_for_updates.return_value = self.update
        c.check()
        c._poll()
        self.assertTrue(c._show.call_args.kwargs['install'])

    def test_repeated_click_does_not_start_parallel_network_requests(self):
        c = self.controller
        c._worker = Mock()
        c.check(); c.check()
        c._worker.assert_called_once()

    def test_downgrade_is_never_offered(self):
        c = self.controller
        self.update.IsDowngrade = True
        c._handle('checked', self.update)
        self.assertIsNone(c.pending)
        c._show.assert_not_called()

    def test_explicit_install_downloads_before_restart(self):
        c = self.controller
        c.pending = self.update
        c._install()
        c.manager.download_updates.assert_called_once()
        c.app.quit.assert_not_called()
        c._poll()
        c.manager.wait_exit_then_apply_updates.assert_called_once_with(self.update, silent=False, restart=True)
        c.app.quit.assert_called_once()

    def test_failed_handoff_does_not_exit_current_app(self):
        c = self.controller
        c.manager.wait_exit_then_apply_updates.side_effect = OSError('locked')
        c._handle('downloaded', self.update)
        c.app.quit.assert_not_called()
        self.assertTrue(c._show.call_args.kwargs['retry'])

    def test_download_error_keeps_settings_and_running_version(self):
        c = self.controller
        self.settings.set('scale', 1.5)
        self.settings.set('language', 'zh')
        c.manual = True
        c._handle('error', 'checksum mismatch')
        c.manager.wait_exit_then_apply_updates.assert_not_called()
        c.app.quit.assert_not_called()
        self.assertEqual(Settings(self.settings.path).get('scale'), 1.5)
        self.assertEqual(Settings(self.settings.path).get('language'), 'zh')
