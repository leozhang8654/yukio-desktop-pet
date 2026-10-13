"""Real windowed-exe redirected I/O and Claude PermissionRequest receipt, no AI actions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from yukio.answer_bridge import AnswerBridge
from yukio.approvals import ALLOW, DENY

exe = str(Path(sys.argv[1]).resolve())
for answer in (ALLOW, DENY):
    with tempfile.TemporaryDirectory() as tmp:
        bridge = AnswerBridge(tmp)
        bridge.poll(time.time()*1000)
        payload = dict(hook_event_name='PermissionRequest', session_id='packaged-hook-test', tool_name='Bash',
                       cwd=tmp, tool_input={'command':'echo 中文 — fixture only'})
        child = subprocess.Popen([exe, '--claude-answer-hook'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env=dict(os.environ, YUKIO_ANSWER_BRIDGE_DIR=tmp))
        try:
            child.stdin.write(json.dumps(payload, ensure_ascii=False).encode()); child.stdin.close(); child.stdin=None
            found=None
            for _ in range(160):
                found=next((e for e in bridge.poll(time.time()*1000) if e.question),None)
                if found: break
                if child.poll() is not None: break
                time.sleep(.05)
            assert found is not None, 'Packaged helper did not receive the request'
            assert '中文' in found.question.text
            bridge.send(found.session, found.event_id, found.question, answer)
            output,error=child.communicate(timeout=8)
            assert child.returncode == 0, error
            result=json.loads(output)
            assert result['hookSpecificOutput']['decision'] == {'behavior':'allow' if answer == ALLOW else 'deny'}
        finally:
            if child.poll() is None: child.kill(); child.wait()
print('Packaged Claude approval allow/deny and UTF-8 input/output passed; no command executed.')
