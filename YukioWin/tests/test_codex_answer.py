"""Question validation and real local byte-stream / Windows named-pipe transport."""
import copy
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

from yukio.codex_answer import AnswerError, NamedPipe, send_answer, submission, turns_in
from yukio.events import PetQuestion


QUESTION = PetQuestion.parse({'title': 'Which?', 'options': ['A', 'B']})


def snapshot(canonical=True):
    turn = dict(status='inProgress', items=[dict(type='agentMessage', id='call', questions=[dict(title='Which?', options=['A', 'B'])])])
    result = dict(id='session', cwd='/tmp', turns=[turn], requests=[])
    if canonical:
        result['turns'] = []
        result['turnHistory'] = dict(kind='canonical', history=dict(entitiesByKey={'turn': turn},
            islands=[dict(entries=[dict(key='index', value='turn')])]))
    return result


class QuestionValidationTests(unittest.TestCase):
    def test_canonical_and_legacy_match_same_live_question(self):
        for canonical in [False, True]:
            method, params = submission(snapshot(canonical), 'session', 'call', QUESTION, '中文 A')
            self.assertEqual(method, 'thread-follower-steer-turn')
            self.assertIn('中文 A', params['input'][0]['text'])
            self.assertEqual(params['conversationId'], 'session')

    def test_wrong_thread_call_text_and_completed_turn_cannot_send(self):
        for session, call, q in [('other', 'call', QUESTION), ('session', 'other', QUESTION), ('session', 'call', PetQuestion.parse({'title': 'Different'}))]:
            with self.assertRaises(AnswerError):
                submission(snapshot(), session, call, q, 'A')
        snap = snapshot()
        turns_in(snap)[0]['status'] = 'completed'
        with self.assertRaises(AnswerError):
            submission(snap, 'session', 'call', QUESTION, 'A')

    def test_duplicate_answer_is_rejected_in_canonical_history(self):
        snap = snapshot()
        _, params = submission(snap, 'session', 'call', QUESTION, 'A')
        turns_in(snap)[0]['items'].append(dict(type='steeringUserMessage', status='accepted', content=params['input']))
        with self.assertRaises(AnswerError) as raised:
            submission(snap, 'session', 'call', QUESTION, 'B')
        self.assertEqual(raised.exception.code, 'expired')

    def test_detached_and_stale_turns_do_not_override_canonical_index(self):
        snap = snapshot()
        snap['turns'] = snapshot(False)['turns']
        snap['turnHistory']['history']['islands'][0]['entries'] = []
        with self.assertRaises(AnswerError):
            submission(snap, 'session', 'call', QUESTION, 'A')
        snap['turnHistory']['history']['islands'][0]['entries'] = [dict(value='missing')]
        with self.assertRaises(AnswerError) as raised:
            turns_in(snap)
        self.assertEqual(raised.exception.code, 'protocol')

    def test_blocking_request_is_not_sent_as_chat_and_multiple_questions_rejected(self):
        snap = snapshot()
        snap['requests'] = [dict(id=42, method='item/tool/requestUserInput', params=dict(itemId='blocking', questions=[dict(id='choice', question='Which?')]))]
        method, params = submission(snap, 'session', 'blocking', QUESTION, 'B')
        self.assertEqual(method, 'thread-follower-submit-user-input')
        self.assertEqual(params['response'], {'answers': {'choice': {'answers': ['B']}}})
        snap['requests'][0]['params']['questions'].append(dict(id='second', question='Other?'))
        with self.assertRaises(AnswerError):
            submission(snap, 'session', 'blocking', QUESTION, 'B')


class TransportTests(unittest.TestCase):
    packaged_exe = None
    def test_real_byte_transport_roundtrip_and_rejection(self):
        for mode in ['canonical', 'legacy', 'rejected', 'expired', 'blocking', 'unconfirmed']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                self.roundtrip(tmp, mode)

    def roundtrip(self, tmp, mode):
        errors, received = [], []
        deadline = time.monotonic() + 8
        if os.name == 'nt':
            import _winapi
            endpoint = r'\\.\pipe\yukio-answer-test-' + str(uuid.uuid4())
            handle = _winapi.CreateNamedPipe(endpoint, 3 | _winapi.FILE_FLAG_OVERLAPPED, 0, 1, 65536, 65536, 0, _winapi.NULL)
            listener = None
        else:
            endpoint = str(Path(tmp)/'ipc.sock')
            listener = socket.socket(socket.AF_UNIX)
            listener.bind(endpoint); listener.listen(1); listener.settimeout(8)

        def server():
            transport = None
            try:
                if os.name == 'nt':
                    transport = NamedPipe.__new__(NamedPipe)
                    transport.api, transport.handle, transport.deadline = _winapi, handle, deadline
                    operation = _winapi.ConnectNamedPipe(handle, overlapped=True)
                    transport._finish(operation, _winapi.ERROR_IO_PENDING)
                else:
                    transport, _ = listener.accept(); transport.settimeout(8)
                def read(n):
                    result = b''
                    while len(result) < n:
                        chunk = transport.recv(n-len(result))
                        if not chunk: raise EOFError()
                        result += chunk
                    return result
                def send(message):
                    body = json.dumps(message).encode()
                    # Fragment the frame to exercise exact reads on both platforms.
                    data = struct.pack('<I', len(body)) + body
                    transport.sendall(data[:2]); transport.sendall(data[2:])
                state = snapshot(mode != 'legacy')
                if mode == 'expired': turns_in(state)[0]['status'] = 'completed'
                if mode in ('blocking', 'unconfirmed'):
                    state['requests'] = [dict(id=42, method='item/tool/requestUserInput', params=dict(itemId='blocking', questions=[dict(id='choice', question='Which?')]))]
                def broadcast():
                    send(dict(type='broadcast', method='thread-stream-state-changed', sourceClientId='owner', params=dict(conversationId='session', change=dict(type='snapshot', conversationState=state))))
                while True:
                    message = json.loads(read(struct.unpack('<I', read(4))[0]))
                    method = message.get('method')
                    if method == 'thread-stream-following-changed':
                        if not message['params']['following']: break
                        broadcast(); continue
                    result = {}
                    if method == 'initialize': result = dict(clientId='test-client')
                    elif method == 'thread-owner-discovery': result = dict(ownerClientId='owner')
                    elif method in ('thread-follower-steer-turn', 'thread-follower-submit-user-input'):
                        received.append(message)
                        assert message['params']['conversationId'] == 'session'
                        assert message['targetClientId'] == 'owner'
                        result = dict(result=dict(turnId='turn')) if method.endswith('steer-turn') else dict(ok=True)
                    elif method == 'thread-follower-load-complete-history':
                        if mode == 'blocking':
                            turns_in(state)[0]['items'].append(dict(requestId=42, completed=True))
                        broadcast()
                    else: raise AssertionError(method)
                    send(dict(type='response', requestId=message['requestId'], resultType='error' if mode == 'rejected' and method == 'thread-follower-steer-turn' else 'success', handledByClientId='owner', result=result))
            except BaseException as error:
                errors.append(error)
            finally:
                if transport: transport.close()
        worker = threading.Thread(target=server, daemon=True); worker.start()
        try:
            call = 'blocking' if mode in ('blocking', 'unconfirmed') else 'call'
            if self.packaged_exe:
                config = Path(tmp)/'config.json'; output = Path(tmp)/'result.json'
                config.write_text(json.dumps(dict(endpoint=endpoint, call=call, output=str(output))), encoding='utf-8')
                subprocess.run([self.packaged_exe, '--codex-answer-smoke', str(config)], check=True, timeout=20)
                expected = 'expired' if mode == 'expired' else 'rejected' if mode in ('rejected', 'unconfirmed') else 'received'
                self.assertEqual(json.loads(output.read_text())['status'], expected)
            elif mode in ('expired', 'rejected', 'unconfirmed'):
                with self.assertRaises(AnswerError): send_answer('session', call, QUESTION, 'A', endpoint)
            else:
                send_answer('session', call, QUESTION, 'A', endpoint)
        finally:
            worker.join(9)
            if listener: listener.close()
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(received), 0 if mode == 'expired' else 1)

    @unittest.skipUnless(os.name == 'nt', 'Windows named pipe only')
    def test_named_pipe_read_timeout_is_cancelled(self):
        import _winapi
        endpoint = r'\\.\pipe\yukio-answer-timeout-' + str(uuid.uuid4())
        handle = _winapi.CreateNamedPipe(endpoint, 3 | _winapi.FILE_FLAG_OVERLAPPED, 0, 1, 4096, 4096, 0, _winapi.NULL)
        operation = _winapi.ConnectNamedPipe(handle, overlapped=True)
        client = NamedPipe(endpoint, time.monotonic() + .15)
        try:
            operation.GetOverlappedResult(True)
            start = time.monotonic()
            with self.assertRaises((TimeoutError, OSError)): client.recv(4)
            self.assertLess(time.monotonic() - start, 2)
        finally:
            client.close(); _winapi.CloseHandle(handle)


if __name__ == '__main__':
    if '--exe' in sys.argv:
        TransportTests.packaged_exe = str(Path(sys.argv[sys.argv.index('--exe') + 1]).resolve())
        suite = unittest.TestSuite([TransportTests('test_real_byte_transport_roundtrip_and_rejection')])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
    unittest.main()
