'use strict';
const byId=id=>document.getElementById(id);
const published=document.documentElement.dataset.view==='published';
const statusURL=published?'./status.json':'./api/status';
const refreshInterval=published?60000:3000;
const labels={complete:'已完成',active:'正在做',planned:'之后做',blocked:'待解决'};
let project=null, filter='all', lastProject='';
const expandedStages=new Set();
const time=value=>{if(!value)return '—';const d=new Date(value);return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(d):'时间未知';};
const el=(tag,className,text)=>{const n=document.createElement(tag);if(className)n.className=className;if(text!==undefined)n.textContent=text;return n;};
if(published){
  byId('publication').hidden=false;
  byId('offline').textContent='暂时无法读取公开进度。下方如有内容，是上次成功读取的版本。';
  byId('runtime-eyebrow').textContent='公开版说明';
  byId('runtime-heading').textContent='这里展示开发进度，活动记录留在本机。';
  byId('runtime-state').textContent='不读取私人活动';
  byId('runtime-description').textContent='完整计划、完成情况和选择原因可以在这里查看。本机记录器的实时数字、聊天内容和密钥不会通过这个网站上传。';
  byId('runtime-metrics').hidden=true;
  byId('runtime-time').textContent='发布新进度后，本页会自动检查更新；这不代表电脑上的活动正在向外直播。';
  byId('updates-description').textContent='这里保留已经发布的开发记录。页面每分钟检查一次新版；电脑上尚未发布的进展不会自动出现。';
}
function renderStages(){
  document.querySelectorAll('#stages details').forEach(n=>n.open?expandedStages.add(n.dataset.stage):expandedStages.delete(n.dataset.stage));
  const focusedStage=document.activeElement?.closest('#stages details')?.dataset.stage;
  const host=byId('stages');host.replaceChildren();
  const stages=project.stages.filter(s=>filter==='all'||s.status===filter);
  for(const s of stages){
    const card=el('article',`stage ${s.status}`);card.dataset.stage=s.id;card.id=`stage-${s.id}`;
    card.append(el('span','step-number',String(project.stages.indexOf(s)+1).padStart(2,'0')));
    const body=el('div','stage-body');body.append(el('h3','',s.title),el('p','stage-description',s.summary));
    const details=el('details');details.dataset.stage=s.id;details.open=expandedStages.has(s.id);
    const summary=el('summary');
    summary.append(el('span','when-closed','展开详情'),el('span','when-open','收起详情'),el('span','detail-hint',s.status==='complete'?'做了什么 · 为什么这样做':'具体安排 · 为什么这样做'));
    details.append(summary);
    if(s.explanation?.length){
      const sections=el('div','detail-sections');
      for(const section of s.explanation){
        const block=el('section','detail-block');block.append(el('h4','',section.title));
        for(const paragraph of section.paragraphs)block.append(el('p','',paragraph));
        sections.append(block);
      }
      details.append(sections);
    }else{
      const list=el('ul');for(const line of s.details||[])list.append(el('li','',line));details.append(list);
    }
    if(s.example){const example=el('div','detail-example');example.append(el('strong','','举个容易理解的例子'),el('p','',s.example));details.append(example);}
    if(s.evidence)details.append(el('p','evidence',s.evidence));body.append(details);card.append(body,el('span',`status ${s.status}`,labels[s.status]||'待确认'));host.append(card);
  }
  if(!stages.length)host.append(el('p','empty','这个分类暂时没有阶段。'));
  if(focusedStage)host.querySelector(`[data-stage="${focusedStage}"] summary`)?.focus({preventScroll:true});
}
function renderProject(p){
  project=p;const current=p.stages.find(s=>s.id===p.focus_id)||p.stages[0];
  const next=p.stages.find((s,i)=>i>p.stages.indexOf(current)&&s.status!=='complete')
    ||(current.status!=='complete'?current:p.stages.find(s=>s.status!=='complete'));
  byId('updated').textContent=time(p.updated_at);byId('work-state').textContent=p.work_state;
  byId('focus-tag').textContent=current.status==='complete'?'本轮已完成':'当前步骤';
  byId('stage-position').textContent=`第 ${p.stages.indexOf(current)+1} / ${p.stages.length} 阶段`;
  byId('focus-title').textContent=current.title;byId('focus-description').textContent=p.current_note;
  byId('focus-outcome').textContent=current.outcome;byId('boundary').textContent=p.boundary;
  byId('next-title').textContent=next===current?'完成当前步骤的剩余检查':next?.title||'本轮计划已交付';
  byId('next-description').textContent=next===current
    ?(current.checks||[]).filter(c=>!c.done).map(c=>c.label).join('；')||current.summary
    :next?.summary||'继续根据实际使用情况完善。';
  byId('acceptance').replaceChildren();
  for(const item of current.checks||[]){const c=el('span',`check ${item.done?'done':''}`);c.append(el('span','circle',item.done?'✓':'·'),el('span','',item.label));byId('acceptance').append(c);}
  byId('milestones').textContent=`${p.stages.filter(s=>s.status==='complete').length} / ${p.stages.length} 个阶段已完成`;
  renderStages();byId('update-list').replaceChildren();
  for(const update of p.updates.slice().reverse()){
    const row=el('li');const t=el('time','',update.at.length===10?update.at:time(update.at));t.dateTime=update.at;
    row.append(t,el('p','',update.text));byId('update-list').append(row);
  }
}
const bytes=value=>typeof value==='number'?(value<1048576?(value/1024).toFixed(0)+' KB':(value/1048576).toFixed(1)+' MB'):'—';
function renderRuntime(r){
  const heartbeat=new Date(r?.updated_at||'').getTime();
  const stale=r?.state&&!['unavailable','stopped','failed'].includes(r.state)&&(!Number.isFinite(heartbeat)||Date.now()-heartbeat>15000);
  const state=stale?'stale':r?.state||'unavailable';
  const states={active:['正在记录','complete','正在查找最近一天有活动的 Codex 会话，轮流保存发现的记录。'],waiting:['等待新活动','neutral','记录器正在运行。目前已读到可保存的末尾；新活动或写完的记录出现后会继续。'],degraded:['部分需要检查','active','部分文件暂时无法记录；其他文件继续处理，之后会重试。'],paused_capacity:['已暂停保存','blocked','保存空间不足或已达到设置的上限。旧记录会保留，不会自动删除；处理空间问题后可重新启动。'],source_unavailable:['未找到会话目录','active','记录器会继续等待。找到 Codex 的本地记录后再开始。'],stopped:['已经停止','neutral','记录器已停止。保存过的历史仍然保留。'],stale:['状态暂未更新','active','记录器超过 15 秒没有报告状态，可能正在处理较大的记录，也可能已中断；现在无法确认。'],unavailable:['尚未连接','neutral','自动记录器尚未连接。接入后，这里显示实际运行数字。'],starting:['正在启动','neutral','正在准备本地记录器。'],failed:['需要检查','blocked','记录器遇到问题。历史保留，修复后可以继续。']};
  states.partial_history=['正在记录，历史有缺口','active','过大的单条内容已标为未读取，后面的记录继续处理。缺口不会被当成成功，也不会自动把两边的操作接在一起。'];
  const [label,cls,description]=states[state]||states.unavailable;
  const pill=byId('runtime-state');pill.textContent=label;pill.className=`status ${cls}`;
  byId('runtime-description').textContent=state==='degraded'&&r?.scan_complete===false?'这次未能完整检查指定范围，可能遇到数量限制或无法读取的目录。已找到的会话仍会继续处理，不能把这里当成全部聊天。':description;
  if(Number.isSafeInteger(r?.observation_gaps)&&r.observation_gaps>0)byId('runtime-description').textContent+=` 已保存的历史中标出了 ${r.observation_gaps.toLocaleString()} 处缺口；同一处即使分几次处理，也只计一次。`;
  byId('metric-found').textContent=typeof r?.discovered_files==='number'?r.discovered_files.toLocaleString():'—';
  byId('metric-events').textContent=typeof r?.events_saved_this_run==='number'?r.events_saved_this_run.toLocaleString():'—';
  byId('metric-errors').textContent=typeof r?.error_files==='number'?r.error_files.toLocaleString():'—';
  byId('metric-size').textContent=bytes(r?.database_bytes);
  const coverage=typeof r?.tracked_files==='number'?`正在跟进 ${r.tracked_files} 个会话文件，${r.pending_files??0} 个等待处理。保存上限 ${bytes(r.max_database_bytes)}。 `:'';
  byId('runtime-time').textContent=r?.updated_at?`${coverage}记录器报告于 ${time(r.updated_at)} · ${r.mode==='synthetic'?'模拟验证数据':'本机实际记录'} · 数量表示观察到的记录，不代表已完成的任务。`:'记录器尚未连接时，不显示示例数字。';
}
async function refresh(){
  try{
    const response=await fetch(statusURL,{cache:'no-store',signal:AbortSignal.timeout(5000)});
    if(!response.ok)throw Error('unavailable');const data=await response.json();
    if(!Array.isArray(data.project?.stages))throw Error('invalid');
    const serialized=JSON.stringify(data.project);
    if(serialized!==lastProject){renderProject(data.project);lastProject=serialized;}
    if(published){
      byId('connection').textContent='已读取公开进度';byId('connection').className='connection';
      byId('last-sync').textContent=`本版发布于 ${time(data.publication?.exported_at)} · 公开开发进度`;
    }else{
      renderRuntime(data.collector);
      byId('connection').textContent='自动刷新已连接';byId('connection').className='connection live';
      byId('last-sync').textContent='刚刚同步 · 仅本机访问 · 不上传聊天内容';
    }
    byId('offline').hidden=true;
  }catch{
    byId('connection').textContent='连接暂时中断';byId('connection').className='connection lost';byId('offline').hidden=false;
    byId('last-sync').textContent='显示上次内容 · 等待重新连接';
  }finally{setTimeout(refresh,refreshInterval);}
}
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{
  filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));if(project)renderStages();
}));
byId('focus-details').addEventListener('click',()=>{
  if(!project)return;
  filter='all';document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter==='all')));
  renderStages();
  const card=byId(`stage-${project.focus_id}`);if(!card)return;
  card.querySelector('details').open=true;expandedStages.add(project.focus_id);
  card.querySelector('summary').focus({preventScroll:true});card.scrollIntoView({block:'start'});
});
refresh();
