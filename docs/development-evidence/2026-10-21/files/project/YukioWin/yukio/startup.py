"""Opt-in, per-user Windows login launch. No writes occur during construction/read."""
import os
from pathlib import Path
import subprocess
import sys

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APPROVAL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run'


def launch_command():
    args = [sys.executable]
    if not getattr(sys, 'frozen', False):
        args.append(str(Path(__file__).resolve().parent.parent / 'run.py'))
    return subprocess.list2cmdline(args)


class RegistryBackend:
    def __init__(self, name='Yukio'):
        self.name = name

    def _read(self, path):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                return winreg.QueryValueEx(key, self.name)[0]
        except FileNotFoundError:
            return None

    def read(self):
        return self._read(RUN_KEY)

    def approval(self):
        value = self._read(APPROVAL_KEY)
        if value is None:
            return True
        # StartupApproved is internal; unknown data never claims launch is enabled.
        if not isinstance(value, bytes) or len(value) < 4:
            return None
        state = int.from_bytes(value[:4], 'little')
        return True if state in (2, 6) else False if state in (3, 7) else None

    def write(self, command):
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, self.name, 0, winreg.REG_SZ, command)

    def remove(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self.name)
        except FileNotFoundError:
            pass


class LaunchAtLogin:
    def __init__(self, backend=None, command=None):
        self.backend = backend or RegistryBackend()
        self.command = command if command is not None else launch_command()

    @property
    def status(self):
        try:
            registered = self.backend.read()
            if registered is None:
                return 'disabled'
            if registered != self.command:
                return 'different_location'
            return 'enabled' if self.backend.approval() is True else 'requires_approval'
        except (OSError, ImportError):
            return 'unavailable'

    def set_enabled(self, enabled):
        if enabled:
            if len(self.command) > 260:
                raise ValueError('Windows startup command is too long. Move Yukio to a shorter path.')
            if self.backend.read() != self.command:
                self.backend.write(self.command)
        else:
            self.backend.remove()

    @staticmethod
    def open_settings():
        os.startfile('ms-settings:startupapps')
