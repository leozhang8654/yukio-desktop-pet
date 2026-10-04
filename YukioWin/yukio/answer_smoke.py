"""Opt-in packaged transport check, restricted to isolated test pipes."""
import json
from pathlib import Path

from .codex_answer import AnswerError, send_answer
from .events import PetQuestion


def run(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    endpoint = config['endpoint']
    if not endpoint.startswith('\\\\.\\pipe\\yukio-answer-test-'):
        raise ValueError('Only isolated test pipes are accepted')
    status = 'received'
    try:
        send_answer('session', config['call'], PetQuestion.parse({'title': 'Which?', 'options': ['A', 'B']}), 'A', endpoint)
    except AnswerError as error:
        status = error.code
    Path(config['output']).write_text(json.dumps({'status': status}), encoding='utf-8')
    return 0
