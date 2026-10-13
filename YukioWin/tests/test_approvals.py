import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from yukio.approvals import ALLOW, DENY, pending, submission
from yukio.codex_answer import AnswerError
from yukio.answer_bridge import AnswerBridge, run_claude_hook
from yukio.answer_setup import merge_settings, hook_command
from yukio.approval_surface import provider, is_request


def snapshot(method='item/commandExecution/requestApproval', **extra):
    return dict(id='s', turns=[dict(id='t', status='inProgress', items=[dict(id='i', changes=[dict(path='example.txt', diff='+ test')])])],
        requests=[dict(id=42, method=method, params=dict(threadId='s', turnId='t', itemId='i', command='echo test', **extra))])

class ApprovalTests(unittest.TestCase):
    def test_only_exact_live_request_and_explicit_decisions(self):
        snap = snapshot(); key, q, _ = pending(snap, 's')[0]
        for answer, decision in [(ALLOW,'accept'), (DENY,'decline')]:
            method, p = submission(snap, 's', key, q, answer)
            self.assertEqual(method, 'thread-follower-command-approval-decision')
            self.assertEqual(p['decision'], decision)
        for mutate in [lambda s:s['requests'][0]['params'].update(command='changed'),
                       lambda s:s['turns'][0].update(status='completed'),
                       lambda s:s['requests'].append(copy.deepcopy(s['requests'][0])),
                       lambda s:s['requests'][0]['params'].update(turnId='other')]:
            changed = copy.deepcopy(snap); mutate(changed)
            with self.assertRaises(AnswerError): submission(changed,'s',key,q,ALLOW)
        with self.assertRaises(AnswerError): submission(snap,'wrong',key,q,ALLOW)
        with self.assertRaises(AnswerError): submission(snap,'s',key,q,'yes')
    def test_permission_scope_is_once_and_file_details_required(self):
        snap = snapshot('item/permissions/requestApproval', permissions={'network':{'enabled':True}})
        key,q,_ = pending(snap,'s')[0]
        for answer in [ALLOW,DENY]:
            _,p = submission(snap,'s',key,q,answer)
            self.assertEqual(p['response']['scope'],'turn')
            self.assertEqual(bool(p['response']['permissions']), answer == ALLOW)
        snap = snapshot(availableDecisions=['acceptForSession','decline'])
        self.assertEqual([o.label for o in pending(snap,'s')[0][1].options],[DENY])
        snap = snapshot('item/fileChange/requestApproval')
        self.assertIn('example.txt',pending(snap,'s')[0][1].text)
        snap['turns'][0]['items']=[]
        self.assertEqual(pending(snap,'s'),[])
    def test_surface_excludes_artifacts_lookalikes_and_nonrequests(self):
        self.assertEqual(provider('https://chatgpt.com/c/test'),'gpt')
        for url in ['https://claude.ai.evil.test/','https://claude.ai@evil.test/','https://claude.ai/artifact/test','http://claude.ai/']:
            self.assertIsNone(provider(url))
        self.assertTrue(is_request('Allow access to this file?', ['Allow once','Deny']))
        for labels in [['Copy','Send'],['Always allow','Cancel'],['Allow','Allow','Deny']]:
            self.assertFalse(is_request('Allow access to this file?',labels))
    def test_hook_merge_preserves_rules_and_is_idempotent(self):
        original={'permissions':{'deny':['Bash']},'hooks':{'PermissionRequest':[{'matcher':'*','hooks':[{'type':'command','command':'existing'}]}]}}
        once=merge_settings(original,'yukio')
        self.assertEqual(once,merge_settings(once,'yukio'))
        self.assertEqual(once['permissions'],original['permissions'])
        self.assertEqual(once['hooks']['PermissionRequest'][0]['hooks'][0]['command'],'existing')
    def test_claude_receipt_round_trip_allow_and_deny_and_offline(self):
        payload=json.dumps(dict(hook_event_name='PermissionRequest',session_id='s',tool_name='Bash',cwd='/tmp',tool_input={'command':'echo 中文'}))
        for answer in [ALLOW,DENY]:
            with tempfile.TemporaryDirectory() as root:
                self.assertEqual(run_claude_hook(payload,root,timeout=.1),{})
                bridge=AnswerBridge(root); bridge.poll(time.time()*1000)
                output=[]
                thread=threading.Thread(target=lambda:output.append(run_claude_hook(payload,root,timeout=4)))
                thread.start(); event=None
                for _ in range(80):
                    event=next((e for e in bridge.poll(time.time()*1000) if e.question),None)
                    if event: break
                    time.sleep(.025)
                self.assertIsNotNone(event)
                self.assertTrue(event.question.approval)
                with self.assertRaises(AnswerError): bridge.send('wrong',event.event_id,event.question,ALLOW)
                with self.assertRaises(AnswerError): bridge.send('s',event.event_id,event.question,'yes')
                bridge.send('s',event.event_id,event.question,answer)
                thread.join(5)
                decision=output[0]['hookSpecificOutput']['decision']
                self.assertEqual(decision,{'behavior':'allow' if answer==ALLOW else 'deny'})
                bridge.send('s',event.event_id,event.question,answer) # receipt makes retry idempotent
                with self.assertRaises(AnswerError): bridge.send('s',event.event_id,event.question,DENY if answer==ALLOW else ALLOW)

if __name__ == '__main__': unittest.main()
