"""Explicit single-use approvals. No free text or implicit default grants."""
import hashlib
import json
from .events import PetQuestion, QuestionOption

ALLOW = '允许这一次 / Allow once'
DENY = '拒绝 / Deny'
METHODS = {'item/commandExecution/requestApproval': 'thread-follower-command-approval-decision',
           'item/fileChange/requestApproval': 'thread-follower-file-approval-decision',
           'item/permissions/requestApproval': 'thread-follower-permissions-request-approval-response'}

def question(provider, details):
    return PetQuestion(details, header=provider + ' · 等你批准 / Approval',
                       options=[QuestionOption(ALLOW), QuestionOption(DENY)], approval=True)

def pending(snapshot, session):
    from .codex_answer import turns_in, AnswerError
    if snapshot.get('id') != session:
        raise AnswerError('protocol')
    live = {t.get('id'): t for t in turns_in(snapshot) if t.get('status') == 'inProgress'}
    result = []
    for request in snapshot.get('requests', []):
        p = request.get('params', {})
        if (request.get('method') not in METHODS or request.get('id') is None or request.get('completed')
            or p.get('threadId') != session or not p.get('turnId') or p['turnId'] not in live):
            continue
        details = dict(p)
        if request['method'] == 'item/fileChange/requestApproval':
            item = next((i for i in live[p['turnId']].get('items', []) if i.get('id') == p.get('itemId')), {})
            if not item.get('changes'):
                continue
            details['changes'] = item['changes']
        body = json.dumps(dict(request=request, details=details), sort_keys=True, ensure_ascii=False).encode()
        if len(body) >= 65536:
            continue
        display = {k:v for k,v in details.items() if k not in ('threadId','turnId','itemId','availableDecisions')}
        sections = [{'item/fileChange/requestApproval':'GPT 申请修改文件', 'item/permissions/requestApproval':'GPT 申请临时访问权限'}.get(request['method'], 'GPT 申请运行以下操作')]
        for key, title in [('reason','申请原因'),('cwd','操作位置'),('command','具体操作')]:
            if isinstance(display.get(key), str): sections.append(title + '：\n' + display.pop(key))
        if display: sections.append('申请详情：\n' + json.dumps(display, ensure_ascii=False, sort_keys=True, indent=2))
        q = question('GPT', '\n\n'.join(sections))
        if 'availableDecisions' in p and 'accept' not in p['availableDecisions']:
            q.options = [QuestionOption(DENY)]
        result.append(('codex-approval:' + hashlib.sha256(body).hexdigest(), q, request))
    return result

def submission(snapshot, session, call_id, displayed, answer):
    from .codex_answer import AnswerError
    matches = [r for key, q, r in pending(snapshot, session)
               if key == call_id and q == displayed and answer in [o.label for o in q.options]]
    if len(matches) != 1 or answer not in (ALLOW, DENY):
        raise AnswerError('expired')
    request = matches[0]
    params = dict(conversationId=session, requestId=request['id'])
    if request['method'] == 'item/permissions/requestApproval':
        permissions = request['params'].get('permissions')
        if not isinstance(permissions, dict):
            raise AnswerError('protocol')
        params['response'] = dict(permissions=permissions if answer == ALLOW else {}, scope='turn')
    else:
        params['decision'] = 'accept' if answer == ALLOW else 'decline'
    return METHODS[request['method']], params
