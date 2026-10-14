from concurrent.futures import ThreadPoolExecutor
from .events import PetEvent, PetState, Kind
from .codex_answer import pending_approvals

class ApprovalMonitor:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='yukio-approvals')
        self.future = None
        self.cursor = 0
        self.shown = {}
        self.last_poll = 0
    def poll(self, sessions, now, enabled=True):
        events = []
        if self.future and self.future.done():
            session, future = self.session, self.future
            self.future = None
            try:
                found = future.result()
            except Exception:
                found = []
            next_shown = {key: q for key, q, _ in found} if enabled else {}
            old = self.shown.get(session, {})
            for key in old.keys() - next_shown.keys():
                events.append(PetEvent(now, 'codex', session, Kind.activity_end, event_id=key))
            for key, q in next_shown.items():
                if key not in old:
                    events.append(PetEvent(now, 'codex', session, Kind.activity_start, event_id=key,
                        activity=PetState.question_for_user, question=q, tool='Approval', detail=q.short_label))
            self.shown[session] = next_shown
        if not enabled:
            for session, items in self.shown.items():
                events.extend(PetEvent(now, 'codex', session, Kind.activity_end, event_id=key) for key in items)
            self.shown.clear()
        elif sessions and not self.future and now - self.last_poll >= 500:
            self.session = sessions[self.cursor % len(sessions)]
            self.cursor += 1; self.last_poll = now
            self.future = self.executor.submit(pending_approvals, self.session)
        return events
