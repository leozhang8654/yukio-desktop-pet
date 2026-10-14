"""Local request/receipt transport for connected Claude, Deep Code and browser hosts."""
import json
import os
from pathlib import Path
import time
import uuid
from .events import PetQuestion, QuestionOption, PetEvent, PetState, Kind
from .sources import app_data_dir
from .codex_answer import AnswerError
from .approvals import ALLOW, DENY, question as approval_question

SOURCES = {'claude': 'claude-transcript', 'deepseek': 'deepcode', 'gpt': 'codex'}

def default_root():
    return Path(os.environ.get('YUKIO_ANSWER_BRIDGE_DIR', str(Path(app_data_dir()) / 'answers')))

def write(path, value):
    tmp = path.with_suffix('.' + str(uuid.uuid4()) + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)

def alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.restype = ctypes.c_void_p
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        api.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def load(path):
    data = path.read_bytes()
    if len(data) > 1 << 20:
        raise ValueError('oversized request')
    return json.loads(data)

def decode_question(q):
    return PetQuestion(q['text'], header=q.get('header'), multi_select=q.get('multiSelect', False),
        options=[QuestionOption(o['label'], o.get('detail')) for o in q.get('options', [])], approval=q.get('approval', False))

class AnswerBridge:
    def __init__(self, root=None):
        self.root = Path(root) if root else default_root()
        self.shown = {}
    def request(self, directory, now):
        r = load(directory / 'request.json')
        if (r['id'] != directory.name or r['expiresAt'] <= now or not alive(r['pid'])
            or (directory / 'done').exists()):
            raise ValueError('expired')
        return r
    def poll(self, now, enabled=True, providers=('claude', 'deepseek', 'gpt')):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if enabled:
            for provider in providers:
                name = 'listener' if provider == 'claude' else 'listener-' + provider
                heartbeat = self.root / ('.' + name + '.' + str(uuid.uuid4()))
                heartbeat.write_text(str(os.getpid()), encoding='ascii')
                heartbeat.replace(self.root / name)
        next_shown, events = {}, []
        if enabled:
            for directory in self.root.iterdir():
                try:
                    uuid.UUID(directory.name)
                    r = self.request(directory, now)
                    provider = r.get('provider', 'claude')
                    if provider not in providers or provider not in SOURCES:
                        continue
                    index = next((i for i in range(len(r['questions'])) if not (directory / f'receipt-{i}.json').exists()), None)
                    if index is None:
                        continue
                    key = f'yukio-{provider}:{r["id"]}:{index}'
                    q = decode_question(r['questions'][index])
                    next_shown[key] = r
                    if key not in self.shown:
                        events.append(PetEvent(ts=now, source=SOURCES[provider], session=r['session'], kind=Kind.activity_start,
                            event_id=key, activity=PetState.question_for_user, tool='Approval' if q.approval else 'AskUserQuestion', question=q, detail=q.short_label))
                except (OSError, ValueError, KeyError, TypeError, StopIteration):
                    continue
        for key, r in self.shown.items():
            if key not in next_shown:
                events.append(PetEvent(ts=now, source=SOURCES[r.get('provider', 'claude')], session=r['session'], kind=Kind.activity_end, event_id=key))
        self.shown = next_shown
        return events
    def send(self, session, call_id, displayed, answer):
        try:
            prefix, ident, raw_index = call_id.split(':')
            uuid.UUID(ident); index = int(raw_index)
            directory = self.root / ident
            r = load(directory / 'request.json')
            provider = r.get('provider', 'claude')
            if (prefix != 'yukio-' + provider or r['id'] != ident or r['session'] != session or index < 0
                or not answer.strip() or len(answer.encode()) >= 65536 or decode_question(r['questions'][index]) != displayed):
                raise AnswerError('expired')
            if displayed.approval and answer not in [o.label for o in displayed.options]:
                raise AnswerError('expired')
            receipt = directory / f'receipt-{index}.json'
            if receipt.exists():
                if load(receipt) == answer:
                    return
                raise AnswerError('expired')
            self.request(directory, time.time()*1000)
            target = directory / f'answer-{index}.json'
            if target.exists() and load(target) != answer:
                raise AnswerError('rejected')
            write(target, answer)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if receipt.exists() and load(receipt) == answer:
                    return
                time.sleep(.05)
            raise AnswerError('rejected')
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            raise AnswerError('expired') from None

def run_claude_hook(payload, root=None, timeout=570):
    root = Path(root) if root else default_root()
    try:
        obj = json.loads(payload)
        approval = obj.get('hook_event_name') == 'PermissionRequest'
        if not approval and not (obj.get('hook_event_name') == 'PreToolUse' and obj.get('tool_name') == 'AskUserQuestion'):
            return {}
        listener = root / 'listener'
        listener_pid = int(listener.read_text())
        if time.time() - listener.stat().st_mtime > 4 or not alive(listener_pid):
            return {}
        tool_input = obj['tool_input']
        if approval:
            text = f'Claude 申请使用：{obj["tool_name"]}\n工作位置：{obj.get("cwd", "未提供")}\n\n' + json.dumps(tool_input, ensure_ascii=False, indent=2, sort_keys=True)
            questions = [approval_question('Claude', text)]
            raw = [dict(question=text)]
        else:
            raw = tool_input['questions']
            questions = [PetQuestion.parse(q) for q in raw]
        if not raw or not all(questions) or len({q['question'] for q in raw}) != len(raw):
            return {}
        ident = str(uuid.uuid4()); directory = root / ident
        directory.mkdir(mode=0o700)
        now = time.time()*1000
        encoded = [dict(text=q.text, header=q.header, multiSelect=q.multi_select, approval=q.approval,
                        options=[dict(label=o.label, detail=o.detail) for o in q.options]) for q in questions]
        write(directory / 'request.json', dict(id=ident, session=obj['session_id'], callID=obj.get('tool_use_id', ident),
              pid=os.getpid(), createdAt=now, expiresAt=now+timeout*1000, questions=encoded))
        answers = {}
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if time.time() - listener.stat().st_mtime > 5 or not alive(listener_pid):
                    return {}
                for i, q in enumerate(raw):
                    target = directory / f'answer-{i}.json'
                    if q['question'] in answers or not target.exists():
                        continue
                    answer = load(target)
                    if not isinstance(answer, str) or not answer.strip() or len(answer.encode()) >= 65536 or (approval and answer not in (ALLOW, DENY)):
                        continue
                    answers[q['question']] = answer
                    write(directory / f'receipt-{i}.json', answer)
                if len(answers) == len(raw):
                    if approval:
                        return dict(hookSpecificOutput=dict(hookEventName='PermissionRequest', decision=dict(behavior='allow' if next(iter(answers.values())) == ALLOW else 'deny')))
                    return dict(hookSpecificOutput=dict(hookEventName='PreToolUse', permissionDecision='allow', updatedInput=dict(tool_input, answers=answers)))
                time.sleep(.1)
            return {}
        finally:
            (directory / 'done').touch()
    except (OSError, ValueError, TypeError, KeyError):
        return {}
