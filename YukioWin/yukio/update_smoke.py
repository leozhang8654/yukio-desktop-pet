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
    settings = Settings(str(report.parent / 'upgrade-settings.json'))
    manager = velopack.UpdateManager(source)
    if mode == '--update-smoke-verify':
        assert manager.get_current_version() == '0.4.0'
        assert __version__ == '0.4.0'
        assert settings.get('scale') == 1.35 and settings.get('language') == 'zh'
        report.write_text(json.dumps({'installed_version': manager.get_current_version(),
            'source_version': __version__, 'settings_preserved': True,
            'executable': sys.executable, 'restarted': True}, indent=2), encoding='utf-8')
        return 0
    assert manager.get_current_version() == '0.3.99'
    assert __version__ == '0.3.99'
    settings.set('scale', 1.35)
    settings.set('language', 'zh')
    update = manager.check_for_updates()
    assert update and update.TargetFullRelease.Version == '0.4.0'
    assert update.TargetFullRelease.NotesMarkdown.strip()
    manager.download_updates(update)
    manager.wait_exit_then_apply_updates(update, silent=True, restart=True,
        restart_args=['--update-smoke-verify', source, str(report)])
    return 0
