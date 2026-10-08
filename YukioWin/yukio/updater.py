"""Opt-out background discovery; installation always requires an explicit click.

All network work runs on one daemon worker. Only the Tk/main thread touches UI
or settings. Velopack owns verified downloads, process handoff and replacement.
"""
from __future__ import annotations
import math
import queue
import sys
import threading
import time
from pathlib import Path
from .l10n import tr

REPOSITORY = 'https://github.com/leozhang8654/yukio-desktop-pet'
CHECK_INTERVAL = 6 * 60 * 60
REMIND_INTERVAL = 24 * 60 * 60


def timestamp(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else 0
    except (TypeError, ValueError):
        return 0


def automatic_check_due(settings, now):
    last = timestamp(settings.get('updateLastCheck', 0))
    return settings.get('automaticUpdates', True) and (now < last or now - last >= CHECK_INTERVAL)


def should_notify(settings, version, now):
    return version != settings.get('updateDeferredVersion', '') or now >= timestamp(settings.get('updateDeferredUntil', 0))


def make_manager():
    import velopack
    # Explicit stable source. Never follow prereleases or downgrade an install.
    return velopack.UpdateManager(velopack.GithubSource(REPOSITORY, prerelease=False))


class UpdateController:
    def __init__(self, app, manager_factory=make_manager):
        self.app = app
        self.root = app.assistant.root
        self.settings = app.settings
        self.manager_factory = manager_factory
        self.manager = None
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.window = None
        self.pending = None
        self.manual = False
        self.root.after(100, self._poll)
        self.root.after(15000, self._automatic)

    def _automatic(self):
        if self.closed:
            return
        if getattr(sys, 'frozen', False) and automatic_check_due(self.settings, time.time()):
            self.check(manual=False)
        self.root.after(60 * 1000, self._automatic)

    def _worker(self, action):
        def run():
            try:
                action()
            except Exception as error:
                self.events.put(('error', str(error)))
        threading.Thread(target=run, name='Yukio updates', daemon=True).start()

    def check(self, manual=True):
        if self.closed:
            return
        if self.busy:
            if manual:
                self.manual = True
                self._show(tr('Checking or downloading update…', '正在检查或下载更新…'))
            return
        self.manual = manual
        self.busy = True
        self.settings.set('updateLastCheck', time.time())
        if manual:
            self._show(tr('Checking for updates…', '正在检查更新…'))
        def check():
            if self.manager is None:
                self.manager = self.manager_factory()
            self.events.put(('checked', self.manager.check_for_updates()))
        self._worker(check)

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                event, value = self.events.get_nowait()
                self._handle(event, value)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _handle(self, event, value):
        if event == 'progress':
            if self.window is not None:
                self.status.configure(text=tr('Downloading: %d%%', '正在下载：%d%%') % value)
            return
        self.busy = False
        if event == 'error':
            if self.manual or self.window is not None:
                self._show(tr('Update could not complete. Your current version is unchanged.\n',
                              '未能完成更新，当前版本仍可使用。\n') + value, retry=True)
            return
        if event == 'downloaded':
            # Run the restart handoff only on the main thread, after download validation.
            try:
                self.manager.wait_exit_then_apply_updates(value, silent=False, restart=True)
                self.closed = True
                self.app.quit()
            except Exception as error:
                self._show(tr('Could not restart: ', '未能重启：') + str(error), retry=True)
            return
        self.pending = value
        if value is None:
            if self.manual:
                from . import __version__
                self._show(tr('You are up to date. Version ', '已经是最新版本：') + __version__)
            return
        if value.IsDowngrade:
            self.pending = None
            if self.manual:
                self._show(tr('No newer stable version is available.', '暂无更新的正式版本。'))
            return
        release = value.TargetFullRelease
        if self.manual or (self.settings.get('automaticUpdates', True) and should_notify(self.settings, release.Version, time.time())):
            self._show(tr('Yukio %s is available', '发现新版本 Yukio %s') % release.Version,
                       notes=release.NotesMarkdown or tr('Improvements and fixes.', '体验改进与问题修复。'), install=True)

    def _show(self, text, notes='', install=False, retry=False):
        import tkinter as tk
        from tkinter import ttk
        if self.window is None:
            self.window = tk.Toplevel(self.root)
            self.window.title(tr('Yukio · Software update', '雪绪 · 软件更新'))
            self.window.geometry('500x410')
            self.window.attributes('-topmost', True)
            self.window.protocol('WM_DELETE_WINDOW', self._later)
        for child in self.window.winfo_children():
            child.destroy()
        body = ttk.Frame(self.window, padding=20)
        body.pack(fill='both', expand=True)
        self.status = ttk.Label(body, text=text, wraplength=455)
        self.status.pack(anchor='w', pady=(0, 12))
        if notes:
            from tkinter.scrolledtext import ScrolledText
            details = ScrolledText(body, wrap='word', height=12)
            details.insert('1.0', notes)
            details.configure(state='disabled')
            details.pack(fill='both', expand=True)
        buttons = ttk.Frame(body)
        buttons.pack(fill='x', side='bottom', pady=(12, 0))
        ttk.Button(buttons, text=tr('Later', '稍后再说') if install else tr('Close', '关闭'),
                   command=self._later).pack(side='left')
        if install:
            ttk.Button(buttons, text=tr('Update and restart', '更新并重启'), command=self._install).pack(side='right')
        elif retry:
            ttk.Button(buttons, text=tr('Retry', '重试'), command=self.check).pack(side='right')
        self.window.deiconify()
        self.window.lift()

    def _later(self):
        if self.pending is not None:
            self.settings.set('updateDeferredVersion', self.pending.TargetFullRelease.Version)
            self.settings.set('updateDeferredUntil', time.time() + REMIND_INTERVAL)
        if self.window is not None:
            self.window.destroy()
            self.window = None

    def _install(self):
        if self.busy or self.pending is None:
            return
        self.busy = True
        self.manual = True
        update = self.pending
        self._show(tr('Downloading update…', '正在下载更新…'))
        def download():
            self.manager.download_updates(update, lambda n: self.events.put(('progress', n)))
            self.events.put(('downloaded', update))
        self._worker(download)
