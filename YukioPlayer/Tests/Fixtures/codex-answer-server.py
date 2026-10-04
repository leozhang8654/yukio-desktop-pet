"""Manual native-card check. Local protocol fixture; no real conversation is changed."""
import json, os, pathlib, socket, struct, tempfile, uuid, sys
root = pathlib.Path(tempfile.mkdtemp(prefix='yukio-codex-fixture-'))
path = str(root/'ipc.sock')
question = 'Codex 协议回传实测：点击测试答案'
config = dict(provider='gpt', socketPath=path, session='fixture-session', callID='fixture-call', question=dict(title=question, options=['YUKIO_CODEX_OK','YUKIO_CODEX_CANCEL']), output='/tmp/yukio-codex-fixture-click.json')
pathlib.Path('/tmp/yukio-codex-fixture-card.json').write_text(json.dumps(config, ensure_ascii=False))
server=socket.socket(socket.AF_UNIX);server.bind(path);server.listen(1);server.settimeout(180)
print('READY',flush=True)
conn,_=server.accept();conn.settimeout(12)
def send(obj):
 data=json.dumps(obj).encode();conn.sendall(struct.pack('<I',len(data))+data)
def read(n):
 data=b''
 while len(data)<n:
  chunk=conn.recv(n-len(data))
  if not chunk:raise EOFError()
  data+=chunk
 return data
while True:
 try:msg=json.loads(read(struct.unpack('<I',read(4))[0]))
 except EOFError:break
 method=msg.get('method')
 if method=='thread-stream-following-changed':
  if not msg['params']['following']:break
  state=dict(id='fixture-session',cwd='/tmp',turns=[dict(status='inProgress',turnId='turn',items=[dict(type='agentMessage',id='fixture-call',questions=[dict(title=question,options=['YUKIO_CODEX_OK','YUKIO_CODEX_CANCEL'])])])],requests=[])
  if '--canonical' in sys.argv:
   state['turnHistory']=dict(kind='canonical',history=dict(entitiesByKey={'turn':state['turns'][0]},islands=[dict(entries=[dict(key='index',value='turn')])]))
   state['turns']=[]
  send(dict(type='broadcast',method='thread-stream-state-changed',sourceClientId='owner',version=11,params=dict(conversationId='fixture-session',change=dict(type='snapshot',conversationState=state))))
  continue
 result={}
 if method=='initialize':result={'clientId':'fixture-client'}
 elif method=='thread-owner-discovery':result={'ownerClientId':'owner'}
 elif method=='thread-follower-steer-turn':
  params=msg['params'];assert params['conversationId']=='fixture-session'
  text=params['input'][0]['text'];body=text.split('>\n',1)[1].rsplit('\n<',1)[0];reply=json.loads(body)[0]
  assert json.loads(reply['questionItemId'])==['request_user_input_async','fixture-call',0]
  assert reply['question']==question
  assert reply['answer']=='YUKIO_CODEX_OK'
  pathlib.Path('/tmp/yukio-codex-fixture-server-receipt.json').write_text(json.dumps(dict(accepted=True,answer=reply['answer'],navigationMessages=0)))
  result={'result':{'turnId':'turn'}}
 else:raise AssertionError('Unexpected protocol action: '+str(method))
 send(dict(type='response',requestId=msg['requestId'],resultType='success',handledByClientId='owner',result=result))
conn.close();server.close()
