"""Install only Yukio-owned hooks; preserve existing tools and permission rules."""
import base64
import json
import os
from pathlib import Path
import sys
import time
from .sources import app_data_dir
from .answer_bridge import write

def hook_command(executable):
    # PowerShell receives an encoded script; paths never become shell syntax.
    exe = str(executable).replace("'", "''")
    args = '--claude-answer-hook' if getattr(sys, 'frozen', False) else '"' + str(Path(__file__).resolve().parents[1] / 'run.py') + '" --claude-answer-hook'
    script = ("[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false);"
              "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
              f"$p=New-Object System.Diagnostics.Process;$p.StartInfo.FileName='{exe}';"
              f"$p.StartInfo.Arguments='{args.replace(chr(39), chr(39)*2)}';"
              "$p.StartInfo.UseShellExecute=$false;$p.StartInfo.CreateNoWindow=$true;"
              "$p.StartInfo.RedirectStandardInput=$true;$p.StartInfo.RedirectStandardOutput=$true;"
              "$p.StartInfo.StandardOutputEncoding=[System.Text.Encoding]::UTF8;"
              "$null=$p.Start();$bytes=[System.Text.Encoding]::UTF8.GetBytes([Console]::In.ReadToEnd());"
              "$p.StandardInput.BaseStream.Write($bytes,0,$bytes.Length);$p.StandardInput.Close();"
              "[Console]::Out.Write($p.StandardOutput.ReadToEnd());$p.WaitForExit();exit $p.ExitCode")
    return 'powershell.exe -NoProfile -NonInteractive -EncodedCommand ' + base64.b64encode(script.encode('utf-16le')).decode()

def merge_settings(original, command, old_command=None):
    result = json.loads(json.dumps(original))
    hooks = result.setdefault('hooks', {})
    for event, matcher in [('PreToolUse', 'AskUserQuestion'), ('PermissionRequest', '*')]:
        rows = hooks.setdefault(event, [])
        for row in rows:
            row['hooks'] = [h for h in row.get('hooks', []) if h.get('command') not in {command, old_command}]
        rows[:] = [r for r in rows if r.get('hooks')]
        rows.append(dict(matcher=matcher, hooks=[dict(type='command', command=command, timeout=600)]))
    return result

def install_claude():
    support = Path(app_data_dir()); support.mkdir(parents=True, exist_ok=True)
    config = Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home()/'.claude'))) / 'settings.json'
    config.parent.mkdir(parents=True, exist_ok=True)
    original = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
    if config.exists():
        (support / f'claude-settings-before-answers-{time.time_ns()}.json').write_bytes(config.read_bytes())
    command = hook_command(sys.executable)
    saved = support / 'claude-answer-command.txt'
    old = saved.read_text() if saved.exists() else None
    write(config, merge_settings(original, command, old))
    saved.write_text(command)


def install_deepseek():
    import shutil
    import subprocess
    node = shutil.which('node')
    git = shutil.which('git')
    if not node or not git:
        raise RuntimeError('请先安装 Node.js 22 或更新版本和 Git，然后再连接 DeepSeek。')
    resources = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2] / 'YukioPlayer'))
    script = resources / 'integrations' / 'deepseek' / 'setup.mjs'
    if not script.is_file():
        raise RuntimeError('安装包缺少 DeepSeek 连接文件，请重新安装雪绪。')
    log = Path(app_data_dir()) / 'deepseek-setup.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf-8') as output:
        result = subprocess.run([node, str(script)], stdout=output, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=600)
    if result.returncode:
        raise RuntimeError('DeepSeek 连接未完成。请检查网络后重试；详情保存在 ' + str(log))
    return Path(app_data_dir()) / 'deepseek-runtime' / 'yukio-deepseek.cmd'
