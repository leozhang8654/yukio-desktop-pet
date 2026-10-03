import unittest
from unittest.mock import Mock

from yukio.outside_click import OutsideClickDismissal


class OutsideClickTests(unittest.TestCase):
    def monitor(self, grabbed=False):
        window = Mock()
        window._w = '.settings'
        window.tk.call.return_value = '.settings.dropdown' if grabbed else ''
        monitor = OutsideClickDismissal(window)
        monitor.api = Mock()
        monitor.hook = 12
        return window, monitor

    def test_external_click_hides_and_releases_native_hook(self):
        window, monitor = self.monitor()
        monitor.pending.append(True)
        monitor._drain()
        window.withdraw.assert_called_once()
        monitor.api.UnhookWindowsHookEx.assert_called_once_with(12)
        self.assertIsNone(monitor.hook)
        self.assertFalse(monitor.pending)

    def test_popup_selection_does_not_hide_settings(self):
        window, monitor = self.monitor(grabbed=True)
        monitor.pending.append(True)
        monitor._drain()
        window.withdraw.assert_not_called()
        window.after.assert_called_once()
        self.assertFalse(monitor.pending)

    def test_no_external_click_keeps_settings_open(self):
        window, monitor = self.monitor()
        monitor._drain()
        window.withdraw.assert_not_called()
        window.after.assert_called_once()

    def test_close_cancels_pending_work_and_is_repeatable(self):
        window, monitor = self.monitor()
        monitor.timer = 'timer-id'
        monitor.pending.append(True)
        monitor.stop()
        monitor.stop()
        window.after_cancel.assert_called_once_with('timer-id')
        monitor.api.UnhookWindowsHookEx.assert_called_once_with(12)
        self.assertFalse(monitor.pending)


if __name__ == '__main__':
    unittest.main()
