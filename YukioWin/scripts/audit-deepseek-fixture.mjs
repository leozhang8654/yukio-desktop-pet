// Controlled Deep Code manager: no model requests, commands or user data.
import fs from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const [bridgePath, root, scenario, report] = process.argv.slice(2);
const bridge = await import(pathToFileURL(bridgePath).href);
const session = 'windows-audit-' + scenario;
const messages = [{id:'question-1', role:'tool', content:JSON.stringify({
  awaitUserResponse:true, metadata:{kind:'ask_user_question',
    questions:[{question:'请选择测试答案：中文能否正确回传？', options:[{label:'中文回答：可以'}, {label:'取消'}]}]}
})}];
const entry = {status: scenario === 'question' ? 'waiting_for_user' : 'ask_permission', planMode:true};
if (scenario !== 'question') entry.askPermissions = [{toolCallId:'audit-only-1',name:'audit',
  description:'仅验证批准回执，不执行命令',command:'AUDIT ONLY — no command is executed',scopes:['audit-fixture']}];
const calls = [];
const manager = {
  getSession:()=>entry, listSessionMessages:()=>messages,
  replySession:async (id, prompt)=>{
    calls.push({id,prompt});
    entry.status='pending'; entry.askPermissions=[];
    messages.push({role:'user',content:prompt.text,meta:{isAnswers:prompt.isAnswers}});
  },
  denySessionPermission:id=>{calls.push({id,denied:true});entry.status='permission_denied';entry.askPermissions=[];}
};
const pending = scenario === 'question' ? bridge.pendingQuestion(manager,session) : bridge.pendingApproval(manager,session);
const accepted = await bridge.answerPending(manager,pending,{root,timeoutMs:45000});
await fs.writeFile(report,JSON.stringify({accepted,scenario,calls,entry,messages},null,2));
if (!accepted || calls.length !== 1) process.exitCode=1;
