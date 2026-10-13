"""Provider-page approval controls through UI Automation; choices come only from the pet UI."""
import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from .approval_surface import provider, decision, is_request
from .events import PetQuestion, QuestionOption, PetEvent, Kind, PetState
from .codex_answer import AnswerError

SUPPORTED = {'chrome.exe','msedge.exe','brave.exe','arc.exe','chromium.exe','claude.exe','codex.exe','chatgpt.exe'}

def process_name(pid):
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.restype = wintypes.HANDLE
    api.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x1000, False, pid)
    if not handle:
        return ''
    try:
        size = wintypes.DWORD(32768); buf = ctypes.create_unicode_buffer(size.value)
        return os.path.basename(buf.value).lower() if api.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)) else ''
    finally:
        api.CloseHandle(handle)

def address(node):
    for getter in (node.GetValuePattern, node.GetLegacyIAccessiblePattern):
        try:
            pattern = getter()
            if pattern and pattern.Value:
                return pattern.Value
        except Exception:
            pass
    return ''

def content(root, deadline):
    stack, texts, buttons, count = [(root, 0)], [], [], 0
    while stack:
        node, depth = stack.pop(); count += 1
        if count > 160 or depth > 14 or time.monotonic() >= deadline:
            raise TimeoutError()
        if node.IsOffscreen:
            continue
        role = node.ControlTypeName
        if role == 'ButtonControl':
            if node.IsEnabled and decision(node.Name) is not None:
                buttons.append((node.Name, node))
            continue
        if role in ('EditControl','HyperlinkControl','MenuControl','ToolBarControl'):
            continue
        if role == 'TextControl':
            if node.Name: texts.append(node.Name)
            continue
        stack.extend((child, depth+1) for child in reversed(node.GetChildren()))
    text = '\n'.join(texts)
    return (text, buttons) if is_request(text, [b[0] for b in buttons]) else None

def scan(auto):
    deadline = time.monotonic() + 2
    result = {}
    for window in auto.GetRootControl().GetChildren():
        if time.monotonic() >= deadline: break
        if window.IsOffscreen or process_name(window.ProcessId) not in SUPPORTED:
            continue
        stack, visited = [(window, None, '', 0)], 0
        while stack:
            node, doc, url, depth = stack.pop(); visited += 1
            if visited > 1800 or depth >= 35 or time.monotonic() >= deadline: break
            if node.IsOffscreen: continue
            role = node.ControlTypeName
            if role == 'DocumentControl':
                doc, url = node, address(node)
                if not provider(url): continue
            who = provider(url)
            found = None
            if doc is not None and who and role in ('GroupControl','PaneControl','WindowControl'):
                try:
                    found = content(node, deadline)
                    if found and any(content(child, deadline) for child in node.GetChildren()): found = None
                except TimeoutError:
                    found = None
            if found:
                text, buttons = found
                identity = f'{window.ProcessId}:{window.NativeWindowHandle}:{url}:{node.GetRuntimeId()}'
                session = 'surface-' + hashlib.sha256(identity.encode()).hexdigest()
                body = f'{who.upper()} · {window.Name}\n{url}\n\n{text}'
                key = 'surface-approval:' + hashlib.sha256((identity + body + '\n'.join(b[0] for b in buttons)).encode()).hexdigest()
                q = PetQuestion(body, header=who.upper() + ' · 等你批准 / Approval', options=[QuestionOption(b[0]) for b in buttons], approval=True)
                result[key] = dict(session=session, provider=who, question=q, root=node, buttons=buttons, document=doc, address=url)
                continue
            if role not in ('HyperlinkControl','MenuControl','ToolBarControl'):
                stack.extend((child, doc, url, depth+1) for child in reversed(node.GetChildren()))
    return result

class SurfaceApprovalBridge:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='yukio-surface')
        self.future = None; self.last = 0; self.known = {}; self.attempted = set()
    def _read(self):
        if os.name != 'nt': return {}
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            return {k: {field:v[field] for field in ('session','provider','question')} for k,v in scan(auto).items()}
    def poll(self, now, enabled, providers):
        events = []
        next_known = None
        if self.future and self.future.done():
            try: next_known = self.future.result()
            except Exception: next_known = {}
            self.future = None
        if not enabled: next_known = {}
        source = lambda c: {'gpt':'codex','claude':'claude-transcript','deepseek':'deepcode'}[c['provider']]
        if next_known is not None:
            next_known = {k:c for k,c in next_known.items() if c['provider'] in providers}
            for key, c in self.known.items():
                if key not in next_known:
                    events.append(PetEvent(now, source(c), c['session'], Kind.activity_end, event_id=key))
            for key, c in next_known.items():
                if key not in self.known:
                    events.append(PetEvent(now, source(c), c['session'], Kind.session_title, detail=c['question'].header))
                    events.append(PetEvent(now, source(c), c['session'], Kind.activity_start, event_id=key, activity=PetState.question_for_user,
                        tool='Approval', detail=c['question'].short_label, question=c['question']))
            self.known = next_known
        if enabled and not self.future and now - self.last >= 2000:
            self.last = now; self.future = self.executor.submit(self._read)
        return events
    def send(self, session, call_id, displayed, answer):
        return self.executor.submit(self._send, session, call_id, displayed, answer).result(timeout=8)
    def _send(self, session, call_id, displayed, answer):
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            c = scan(auto).get(call_id)
            if (call_id in self.attempted or not c or c['session'] != session or c['question'] != displayed or decision(answer) is None):
                raise AnswerError('expired')
            button = next((b for label,b in c['buttons'] if label == answer), None)
            if button is None: raise AnswerError('expired')
            self.attempted.add(call_id)
            try:
                button.GetInvokePattern().Invoke()
                deadline = time.monotonic()+2
                while time.monotonic() < deadline:
                    if address(c['document']) == c['address'] and c['root'].ControlTypeName and content(c['root'], deadline) is None:
                        return
                    time.sleep(.1)
            except Exception:
                pass
            raise AnswerError('rejected')
