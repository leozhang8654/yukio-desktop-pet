"""Read document URLs in the foreground window through Windows UI Automation.

Called on the focus worker. No message text, history links, cookies or keystrokes.
The native reader is Windows-only; failure preserves completion reminders.
"""
import time
from .visible_chat import VisibleChat

SUPPORTED_EXES = {'chrome.exe', 'msedge.exe', 'brave.exe', 'arc.exe', 'chromium.exe',
                  'claude.exe', 'codex.exe', 'chatgpt.exe'}


def collect_documents(root, now=time.monotonic):
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


def read(process_id):
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            root = auto.GetForegroundControl()
            if root is None or root.ProcessId != process_id:
                return []
            handle = root.NativeWindowHandle
            chats = collect_documents(root)
            current = auto.GetForegroundControl()
            if current is None or current.ProcessId != process_id or current.NativeWindowHandle != handle:
                return []
            return chats
    except Exception:
        return []
