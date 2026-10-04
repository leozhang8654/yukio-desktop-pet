"""Codex question replies over desktop IPC, without clipboard or keyboard input."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import struct
import time
import uuid

from .events import PetQuestion
from .l10n import tr


class AnswerError(Exception):
    def __init__(self, code):
        self.code = code
        messages = {
            'unavailable': ('Codex connection unavailable · retry', 'Codex 未连接 · 可重试'),
            'protocol': ('Codex connection format changed', 'Codex 接口格式已变化'),
            'expired': ('Question expired or already answered', '问题已结束或已回答'),
            'rejected': ('Not confirmed · check before retrying', '未确认接收 · 核对后重试'),
        }
        super().__init__(tr(*messages[code]))


def turns_in(snapshot):
    state = snapshot.get('turnHistory', {})
    if state.get('kind') == 'canonical':
        try:
            history = state['history']
            entities, islands = history['entitiesByKey'], history['islands']
            result, seen = [], set()
            for island in islands:
                for entry in island['entries']:
                    key = entry['value']
                    turn = entities[key]
                    if not isinstance(turn, dict):
                        raise TypeError()
                    if key not in seen:
                        result.append(turn)
                        seen.add(key)
            return result
        except (KeyError, TypeError, AttributeError):
            raise AnswerError('protocol') from None
    turns = snapshot.get('turns')
    if not isinstance(turns, list):
        raise AnswerError('protocol')
    return turns


def submission(snapshot, session, call_id, question, answer):
    if snapshot.get('id') != session:
        raise AnswerError('protocol')
    turn = next((t for t in reversed(turns_in(snapshot)) if t.get('status') == 'inProgress'), None)
    if turn is None:
        raise AnswerError('expired')
    items = turn.get('items', [])
    for item in items:
        if item.get('id') != call_id or item.get('type') != 'agentMessage':
            continue
        questions = item.get('questions') or []
        first = questions[0] if questions else {}
        parsed = PetQuestion.parse(first)
        title = first.get('title')
        if not isinstance(title, str) or parsed is None or parsed.text != question.text:
            continue
        question_id = json.dumps(['request_user_input_async', call_id, 0], separators=(',', ':'))
        for previous in items:
            if previous.get('type') not in ('userMessage', 'steeringUserMessage'):
                continue
            if previous['type'] == 'steeringUserMessage' and previous.get('status') != 'accepted':
                continue
            for part in previous.get('content', previous.get('input', [])):
                text = part.get('text', '')
                start, end = '<send_user_message_question_reply>', '</send_user_message_question_reply>'
                if start in text and end in text:
                    try:
                        replies = json.loads(text.split(start, 1)[1].split(end, 1)[0])
                        if any(r.get('questionItemId') == question_id for r in replies):
                            raise AnswerError('expired')
                    except (ValueError, TypeError, AttributeError):
                        pass
        reply = json.dumps([dict(questionItemId=question_id, question=title, answer=answer)], ensure_ascii=False)
        text = '<send_user_message_question_reply>\n' + reply + '\n</send_user_message_question_reply>'
        ident = str(uuid.uuid4())
        return 'thread-follower-steer-turn', dict(
            conversationId=session, input=[dict(type='text', text=text, text_elements=[])],
            clientUserMessageId=ident, attachments=[],
            restoreMessage=dict(id=ident, cwd=snapshot.get('cwd'), context=dict(
                prompt=text, addedFiles=[], fileAttachments=[], imageAttachments=[],
                commentAttachments=[], turnTrigger='send_user_message_async_question')))
    matching = []
    for request in snapshot.get('requests', []):
        params = request.get('params', {})
        questions = params.get('questions', [])
        parsed = PetQuestion.parse(questions[0]) if len(questions) == 1 else None
        if (request.get('method') == 'item/tool/requestUserInput' and params.get('itemId') == call_id
                and parsed and parsed.text == question.text and isinstance(questions[0].get('id'), str)):
            matching.append(request)
    if len(matching) != 1:
        raise AnswerError('expired')
    request = matching[0]
    return 'thread-follower-submit-user-input', dict(conversationId=session, requestId=request['id'],
        response=dict(answers={request['params']['questions'][0]['id']: dict(answers=[answer])}))


class NamedPipe:
    """Raw byte pipe with cancellable, bounded reads and writes (no pickle framing)."""
    def __init__(self, path, deadline):
        import _winapi
        self.api = _winapi
        self.deadline = deadline
        self.handle = _winapi.CreateFile(path, _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
            0, None, _winapi.OPEN_EXISTING,
            _winapi.FILE_FLAG_OVERLAPPED | 0x100000 | 0x10000, 0)  # SQOS: identification only

    def _finish(self, operation, error):
        api = self.api
        try:
            if error == api.ERROR_IO_PENDING:
                timeout = max(0, int((self.deadline - time.monotonic()) * 1000))
                if api.WaitForMultipleObjects([operation.event], False, timeout) != 0:
                    raise TimeoutError()
            count, error = operation.GetOverlappedResult(True)
            if error:
                raise OSError(error, 'Codex pipe I/O failed')
            return count
        except BaseException:
            operation.cancel()
            operation.GetOverlappedResult(True)
            raise

    def recv(self, count):
        operation, error = self.api.ReadFile(self.handle, count, overlapped=True)
        self._finish(operation, error)
        return operation.getbuffer()

    def sendall(self, data):
        while data:
            operation, error = self.api.WriteFile(self.handle, data, overlapped=True)
            count = self._finish(operation, error)
            if count <= 0:
                raise EOFError()
            data = data[count:]

    def close(self):
        self.api.CloseHandle(self.handle)


class Connection:
    def __init__(self, endpoint=None, timeout=12):
        self.deadline = time.monotonic() + timeout
        self.client = 'initializing-client'
        self.snapshots = []
        self.transport = None
        try:
            if os.name == 'nt':
                self.transport = NamedPipe(endpoint or r'\\.\pipe\codex-ipc', self.deadline)
            else:
                self.transport = socket.socket(socket.AF_UNIX)
                self.transport.settimeout(timeout)
                self.transport.connect(endpoint or str(Path(os.environ.get('CODEX_HOME', Path.home()/'.codex'))/'ipc/ipc.sock'))
            reply = self.request('initialize', dict(clientType='yukio'), version=0)
            self.client = reply['result']['clientId']
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.transport is not None:
            self.transport.close()
            self.transport = None

    def write(self, message):
        body = json.dumps(message, ensure_ascii=False).encode()
        self.transport.sendall(struct.pack('<I', len(body)) + body)

    def read(self, count):
        result = bytearray()
        while len(result) < count:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            if isinstance(self.transport, socket.socket):
                self.transport.settimeout(remaining)
            chunk = self.transport.recv(count - len(result))
            if not chunk:
                raise EOFError()
            result.extend(chunk)
        return bytes(result)

    def receive(self):
        length = struct.unpack('<I', self.read(4))[0]
        if not 0 < length <= 64 << 20:
            raise AnswerError('protocol')
        message = json.loads(self.read(length))
        if message.get('type') == 'client-discovery-request':
            self.write(dict(type='client-discovery-response', requestId=message['requestId'], response=dict(canHandle=False)))
        params = message.get('params', {})
        if (message.get('type') == 'broadcast' and message.get('method') == 'thread-stream-state-changed'
                and params.get('change', {}).get('type') == 'snapshot'):
            self.snapshots.append((message.get('sourceClientId'), params))
        return message

    def request(self, method, params, version=1, target=None):
        ident = str(uuid.uuid4())
        message = dict(type='request', requestId=ident, sourceClientId=self.client,
            version=version, method=method, params=params, timeoutMs=5000)
        if target:
            message['targetClientId'] = target
        self.write(message)
        while time.monotonic() < self.deadline:
            reply = self.receive()
            if reply.get('type') == 'response' and reply.get('requestId') == ident:
                if reply.get('resultType') != 'success':
                    raise AnswerError('rejected')
                return reply
        raise AnswerError('unavailable')

    def follow(self, session, owner, following):
        self.write(dict(type='broadcast', method='thread-stream-following-changed', sourceClientId=self.client,
            targetClientIds=[owner], version=1, params=dict(conversationId=session, hostId='local', following=following)))

    def snapshot(self, session, owner):
        while time.monotonic() < self.deadline:
            for index, (source, params) in enumerate(self.snapshots):
                if source == owner and params.get('conversationId') == session:
                    self.snapshots.pop(index)
                    return params['change']['conversationState']
            self.receive()
        raise AnswerError('unavailable')


def send_answer(session, call_id, question, answer, endpoint=None):
    connection = None
    try:
        connection = Connection(endpoint)
        owner = connection.request('thread-owner-discovery', dict(hostId='local', conversationId=session)).get('handledByClientId')
        if not owner:
            raise AnswerError('unavailable')
        connection.follow(session, owner, True)
        try:
            state = connection.snapshot(session, owner)
            method, params = submission(state, session, call_id, question, answer)
            result = connection.request(method, params, target=owner).get('result', {})
            if method == 'thread-follower-steer-turn':
                if not isinstance(result.get('result', {}).get('turnId'), str):
                    raise AnswerError('protocol')
            else:
                if result.get('ok') is not True:
                    raise AnswerError('protocol')
                connection.request('thread-follower-load-complete-history', dict(conversationId=session), target=owner)
                updated = connection.snapshot(session, owner)
                if not any(str(item.get('requestId')) == str(params['requestId']) and item.get('completed') is True
                           for turn in turns_in(updated) for item in turn.get('items', [])):
                    raise AnswerError('rejected')
        finally:
            try:
                connection.follow(session, owner, False)
            except (OSError, EOFError):
                pass
    except AnswerError:
        raise
    except (OSError, EOFError):
        raise AnswerError('unavailable') from None
    except (KeyError, ValueError, TypeError, AttributeError):
        raise AnswerError('protocol') from None
    finally:
        if connection:
            connection.close()
