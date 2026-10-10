"""Explicit Windows release qualification commands; never called by normal startup."""
import json
from pathlib import Path
import sys
from .settings import Settings


def run(args):
    import velopack
    from . import __version__
    mode, source, report = args
    report = Path(report).resolve()
    settings = Settings()
    manager = velopack.UpdateManager(source)
    if mode == '--update-smoke-verify':
        assert manager.get_current_version() == '0.4.2'
        assert __version__ == '0.4.2'
        assert manager.check_for_updates() is None
        assert settings.get('scale') == 1.35 and settings.get('language') == 'zh'
        report.write_text(json.dumps({'installed_version': manager.get_current_version(),
            'source_version': __version__, 'settings_preserved': True, 'no_update_after_upgrade': True,
            'executable': sys.executable, 'restarted': True}, indent=2), encoding='utf-8')
        return 0
    assert manager.get_current_version() == '0.3.99'
    assert __version__ == '0.3.99'
    settings.set('scale', 1.35)
    settings.set('language', 'zh')
    update = manager.check_for_updates()
    assert update and update.TargetFullRelease.Version == '0.4.2'
    assert update.TargetFullRelease.NotesMarkdown.strip()
    # A missing feed must fail without changing the installed version.
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory() as empty:
        try:
            velopack.UpdateManager(empty).check_for_updates()
        except Exception:
            pass
        else:
            raise AssertionError('Missing feed unexpectedly succeeded')
    # Use the real updater to reject a corrupted package before installation.
    with tempfile.TemporaryDirectory() as damaged:
        for file in Path(source).iterdir():
            if file.suffix in ('.json', '.nupkg'):
                shutil.copyfile(file, Path(damaged) / file.name)
        payload = Path(damaged) / update.TargetFullRelease.FileName
        with payload.open('r+b') as fh:
            fh.seek(-1, 2)
            value = fh.read(1)
            fh.seek(-1, 2)
            fh.write(bytes([value[0] ^ 0xff]))
        bad_manager = velopack.UpdateManager(damaged)
        bad_update = bad_manager.check_for_updates()
        try:
            bad_manager.download_updates(bad_update)
        except Exception:
            pass
        else:
            raise AssertionError('Corrupt package was accepted')
    assert manager.get_current_version() == '0.3.99'
    assert Settings().get('scale') == 1.35
    manager.download_updates(update)
    manager.wait_exit_then_apply_updates(update, silent=True, restart=True,
        restart_args=['--update-smoke-verify', source, str(report)])
    return 0
