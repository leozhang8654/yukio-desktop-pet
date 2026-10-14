"""Read document URLs in the foreground window through Windows UI Automation.

Called on the focus worker. No message text, history links, cookies or keystrokes.
The native reader is Windows-only; failure preserves completion reminders.
"""
import time
import re
import threading
from .visible_chat import VisibleChat

SUPPORTED_EXES = {'chrome.exe', 'msedge.exe', 'brave.exe', 'arc.exe', 'chromium.exe',
                  'claude.exe', 'codex.exe', 'chatgpt.exe'}


SIDE_PANEL = "chrome-extension://hehggadaopoacecdllhhajmbjkdcmajg/codex-sidepanel/index.html"
_targets = {}
_target_lock = threading.Lock()


def selected_header(root):
    stack, buttons, visited = [(root, 0)], [], 0
    while stack and visited < 128:
        node, depth = stack.pop()
        visited += 1
        role = node.ControlTypeName
        if role == "ButtonControl":
            title = node.Name
            if not buttons and title != "New chat":
                return None
            buttons.append(title)
            if len(buttons) == 3:
                return buttons[1] if buttons[2] == "More actions" else None
            continue
        if role not in ("DocumentControl", "PaneControl", "GroupControl", "CustomControl") or depth >= 16:
            continue
        children = node.GetChildren()
        if len(stack) + len(children) > 128:
            return None
        stack.extend((c, depth + 1) for c in reversed(children))
    return None


def session_for_header(header, titles):
    if not header:
        return None
    title = re.sub(r" (?:No chats|1 chat|[0-9]+ chats) in progress$", "", header.strip())
    if len(title) < 2 or "…" in title or title.endswith("...") or title in ("New chat", "ChatGPT", "新聊天", "新对话"):
        return None
    matches = {ident for ident, name in titles if name and name.strip() == title}
    return next(iter(matches)) if len(matches) == 1 else None


def collect_documents(root, now=time.monotonic, titles=(), on_panel=None):
    """Bounded traversal, kept separate for regression tests with an accessibility fixture."""
    deadline = now() + .35
    queue = [(root, 0)]
    cursor, chats = 0, []
    while cursor < len(queue) and cursor < 512 and now() < deadline:
        node, depth = queue[cursor]
        cursor += 1
        if node.IsOffscreen:
            continue
        role = node.ControlTypeName
        if role == 'DocumentControl':
            address = ''
            for getter in (node.GetValuePattern, node.GetLegacyIAccessiblePattern):
                try:
                    pattern = getter()
                    address = pattern.Value if pattern else ''
                except Exception:
                    continue
                if address:
                    break
            chat = VisibleChat.from_url(address)
            if chat:
                chats.append(chat)
            if address == SIDE_PANEL:
                session = session_for_header(selected_header(node), titles)
                if session:
                    chats.append(VisibleChat('gpt', session))
                    if on_panel:
                        on_panel(session)
                # No message-body scanning, even for an unmatched header.
                continue
            if not address.startswith('chrome-extension://'):
                continue
        if role in ('HyperlinkControl', 'ToolBarControl', 'MenuControl', 'TabControl', 'TabItemControl'):
            continue
        if depth < 20:
            children = node.GetChildren()
            if len(queue) + len(children) > 512:
                return []
            queue.extend((child, depth + 1) for child in children)
    return chats if cursor == len(queue) and now() < deadline else []


def read(process_id, titles=()):
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            root = auto.GetForegroundControl()
            if root is None or root.ProcessId != process_id:
                return []
            handle = root.NativeWindowHandle
            panels = []
            chats = collect_documents(root, titles=titles, on_panel=panels.append)
            current = auto.GetForegroundControl()
            if current is None or current.ProcessId != process_id or current.NativeWindowHandle != handle:
                return []
            if panels:
                selected = [tab for tab in _tabs(root) if tab.GetSelectionItemPattern().IsSelected]
                if len(selected) == 1:
                    tab = selected[0]
                    with _target_lock:
                        for session in panels:
                            _targets[session] = (handle, process_id, tuple(tab.GetRuntimeId()), _tab_title(tab.Name))
            return chats
    except Exception:
        return []


def _tab_title(title):
    return re.sub(r" - (?:内存用量|Memory usage).*?$", "", title)


def _tabs(root):
    queue, result, cursor = [root], [], 0
    while cursor < len(queue) and cursor < 512:
        node = queue[cursor]
        cursor += 1
        role = node.ControlTypeName
        if role in ('DocumentControl', 'ToolBarControl', 'MenuControl'):
            continue
        if role == 'TabItemControl':
            result.append(node)
            continue
        children = node.GetChildren()
        if len(queue) + len(children) > 512:
            return []
        queue.extend(children)
    return result if cursor == len(queue) else []


def has_session(session):
    with _target_lock:
        return session in _targets


def open_session(session):
    """Select only the original, still-existing browser tab; never open Codex."""
    with _target_lock:
        target = _targets.get(session)
    if not target:
        return False
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            handle, pid, runtime_id, title = target
            root = auto.ControlFromHandle(handle)
            if root is None or root.ProcessId != pid:
                return False
            matches = [tab for tab in _tabs(root)
                       if tuple(tab.GetRuntimeId()) == runtime_id and _tab_title(tab.Name) == title]
            if len(matches) != 1:
                return False
            matches[0].GetSelectionItemPattern().Select()
            root.SetActive()
            return True
    except Exception:
        return False
