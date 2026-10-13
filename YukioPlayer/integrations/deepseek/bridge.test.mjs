import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {answerPending, pendingQuestion} from './bridge.mjs';
const pause = ms => new Promise(r => setTimeout(r, ms));
function fixture() {
  const questions = [{question:'Which?', options:[{label:'A'}, {label:'B'}]}];
  const messages = [{id:'q1', role:'tool', content:JSON.stringify({awaitUserResponse:true,metadata:{kind:'ask_user_question',questions}})}];
  const entry = {status:'waiting_for_user', planMode:true};
  let calls = 0;
  return {entry, messages, get calls() {return calls;}, getSession:()=>entry, listSessionMessages:()=>messages,
    replySession: async (session, prompt) => {
      calls++; assert.equal(session,'s'); assert.equal(prompt.planMode,true); assert.equal(prompt.permissions,undefined);
      messages.push({role:'user', content:prompt.text, meta:{isAnswers:prompt.isAnswers}}); entry.status='pending';
    }};
}
test('exact pending question is saved before the final receipt, with no permission grants', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(),'yukio-deepseek-test-'));
  try {
    await fs.writeFile(path.join(root,'listener-deepseek'),String(process.pid));
    const manager=fixture(), pending=pendingQuestion(manager,'s');
    const work=answerPending(manager,pending,{root,timeoutMs:1500});
    let dir;
    for(let i=0;i<40;i++) { const names=await fs.readdir(root);dir=names.find(n=>n!=='listener-deepseek');if(dir)break;await pause(10); }
    assert.ok(dir);
    await fs.writeFile(path.join(root,dir,'answer-0.json'),JSON.stringify('中文 A'));
    assert.equal(await work,true);
    assert.equal(JSON.parse(await fs.readFile(path.join(root,dir,'receipt-0.json'),'utf8')),'中文 A');
    assert.equal(manager.calls,1);assert.equal(pendingQuestion(manager,'s'),null);
  } finally { await fs.rm(root,{recursive:true,force:true}); }
});
test('tool authorization and answered or unrelated messages are never treated as questions', () => {
  const m=fixture();m.entry.askPermissions=[{tool:'Bash'}];assert.equal(pendingQuestion(m,'s'),null);
  m.entry.askPermissions=[];m.messages.push({role:'user',content:'already answered'});assert.equal(pendingQuestion(m,'s'),null);
});
test('missing listener leaves the normal CLI question untouched', async () => {
  const m=fixture();assert.equal(await answerPending(m,pendingQuestion(m,'s'),{root:'/nonexistent/yukio-test'}),false);assert.equal(m.calls,0);
});

test('approval allows only current batch once; deny never resumes execution', async () => {
  const {pendingApproval, ALLOW, DENY} = await import('./bridge.mjs');
  for (const answer of [ALLOW, DENY]) {
    const root = await fs.mkdtemp(path.join(os.tmpdir(),'yukio-approval-test-'));
    try {
      await fs.writeFile(path.join(root,'listener-deepseek'),String(process.pid));
      const entry={status:'ask_permission',planMode:true,askPermissions:[{toolCallId:'a',name:'Bash',command:'echo 中文',scopes:['shell']}]};
      let called=0;
      const manager={getSession:()=>entry, denySessionPermission:()=>{called++;entry.status='permission_denied';},
        replySession:(_,prompt)=>{called++;assert.deepEqual(prompt.permissions,[{toolCallId:'a',permission:'allow'}]);assert.equal(prompt.alwaysAllows,undefined);assert.equal(prompt.planMode,true);entry.status='pending';entry.askPermissions=[];return Promise.resolve();}};
      const work=answerPending(manager,pendingApproval(manager,'s'),{root,timeoutMs:1500});
      let dir;
      for(let i=0;i<60;i++){dir=(await fs.readdir(root)).find(n=>n!=='listener-deepseek');if(dir)break;await pause(10);}
      assert.ok(dir);await fs.writeFile(path.join(root,dir,'answer-0.json'),JSON.stringify(answer));
      assert.equal(await work,true);assert.equal(called,1);
      assert.equal(JSON.parse(await fs.readFile(path.join(root,dir,'receipt-0.json'),'utf8')),answer);
    }finally{await fs.rm(root,{recursive:true,force:true});}
  }
});
test('changed permission batch and free text cannot authorize execution', async () => {
  const {pendingApproval, ALLOW} = await import('./bridge.mjs');
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'yukio-stale-approval-'));
  try {
    await fs.writeFile(path.join(root,'listener-deepseek'),String(process.pid));
    const entry={status:'ask_permission',askPermissions:[{toolCallId:'a',command:'echo test',scopes:[]}]};
    let called=0;const m={getSession:()=>entry,replySession:()=>{called++;}};
    const original=pendingApproval(m,'s');const work=answerPending(m,original,{root,timeoutMs:500});
    let dir;for(let i=0;i<40;i++){dir=(await fs.readdir(root)).find(n=>n!=='listener-deepseek');if(dir)break;await pause(10);}
    await fs.writeFile(path.join(root,dir,'answer-0.json'),JSON.stringify('yes'));
    await pause(130);assert.equal(called,0);
    entry.askPermissions[0].command='different operation';
    await fs.writeFile(path.join(root,dir,'answer-0.json'),JSON.stringify(ALLOW));
    assert.equal(await work,false);assert.equal(called,0);
    entry.askPermissions[0].scopes='bad';assert.equal(pendingApproval(m,'s'),null);
  }finally{await fs.rm(root,{recursive:true,force:true});}
});
