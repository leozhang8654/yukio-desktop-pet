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
