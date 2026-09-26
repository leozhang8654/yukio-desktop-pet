import unittest
from unittest.mock import patch
from yukio.startup import LaunchAtLogin, launch_command


class FakeRegistry:
    def __init__(self): self.command=None;self.allowed=True;self.writes=0;self.failure=False
    def read(self): return self.command
    def approval(self): return self.allowed
    def write(self, command):
        if self.failure: raise PermissionError('denied')
        self.command=command;self.writes+=1
    def remove(self):
        if self.failure: raise PermissionError('denied')
        self.command=None


class StartupTests(unittest.TestCase):
    def test_read_never_registers_and_reflects_external_changes(self):
        b=FakeRegistry();s=LaunchAtLogin(b,'"C:\\Pets\\Yukio.exe"')
        self.assertEqual(s.status,'disabled');self.assertEqual(b.writes,0)
        b.command=s.command;self.assertEqual(s.status,'enabled')
        b.allowed=False;self.assertEqual(s.status,'requires_approval')
        b.allowed=None;self.assertEqual(s.status,'requires_approval')
        b.command=None;self.assertEqual(s.status,'disabled')

    def test_enable_disable_and_repeat(self):
        b=FakeRegistry();s=LaunchAtLogin(b,'Yukio.exe')
        s.set_enabled(True);s.set_enabled(True)
        self.assertEqual(s.status,'enabled');self.assertEqual(b.writes,1)
        s.set_enabled(False);s.set_enabled(False);self.assertEqual(s.status,'disabled')

    def test_move_or_upgrade_updates_command_only_when_requested(self):
        b=FakeRegistry();b.command='old.exe';s=LaunchAtLogin(b,'new.exe')
        self.assertEqual(s.status,'different_location');self.assertEqual(b.command,'old.exe')
        s.set_enabled(True);self.assertEqual(b.command,'new.exe')

    def test_failure_preserves_system_state(self):
        b=FakeRegistry();b.failure=True;s=LaunchAtLogin(b,'Yukio.exe')
        with self.assertRaises(PermissionError):s.set_enabled(True)
        self.assertEqual(s.status,'disabled')
        b.command=s.command
        with self.assertRaises(PermissionError):s.set_enabled(False)
        self.assertEqual(s.status,'enabled')

    def test_command_quotes_spaces_and_non_ascii_paths(self):
        with patch('sys.executable',r'C:\Users\雪 绪\Yukio.exe'),patch('sys.frozen',True,create=True):
            self.assertEqual(launch_command(),'"C:\\Users\\雪 绪\\Yukio.exe"')

    def test_too_long_command_is_not_registered(self):
        b=FakeRegistry();s=LaunchAtLogin(b,'X'*261)
        with self.assertRaises(ValueError):s.set_enabled(True)
        self.assertIsNone(b.command)
