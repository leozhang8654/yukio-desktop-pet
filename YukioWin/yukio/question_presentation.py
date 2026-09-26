"""Local card acknowledgements, scoped to session + call (not remote delivery)."""
from collections import OrderedDict


def question_key(pending):
    return (pending.session, pending.call_id) if pending else None


class QuestionPresentationState:
    def __init__(self):
        self.records = OrderedDict()

    def _remember(self, key):
        if key not in self.records:
            self.records[key] = {'dismissed': False, 'notice': None}
            if len(self.records) > 512:
                self.records.popitem(last=False)
        return self.records[key]

    def is_dismissed(self, key):
        return self.records.get(key, {}).get('dismissed', False)

    def dismiss(self, key):
        self._remember(key)['dismissed'] = True

    def notice(self, key):
        return self.records.get(key, {}).get('notice')

    def set_notice(self, key, notice):
        self._remember(key)['notice'] = notice
