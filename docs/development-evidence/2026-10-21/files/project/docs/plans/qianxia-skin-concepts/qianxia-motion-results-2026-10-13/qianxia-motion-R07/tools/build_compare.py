"""Side-by-side R06 (parent) vs R07 player. Both columns share one clock and
one blink schedule so only the body/gaze timing differs."""
from pathlib import Path
import json
R=Path(__file__).resolve().parents[1]
old=json.loads((R.parent/'qianxia-motion-R06/motion/motion.json').read_text())
new=json.loads((R/'motion/motion.json').read_text())
names={'idle':'待机','thinking':'思考','read_file':'读文件','view_image':'看图片','write_file':'写文件','verify':'验证','read_web':'浏览网页','default_work':'工作中','respond':'回答','task_complete':'完成','question_for_user':'等待回应','failed':'遇到问题'}
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>千夏 R06 / R07 对照</title>
<style>
:root{--bg:#161b25;--panel:#212b3b;--line:#39465b;--text:#e9eef6;--muted:#aab6c8;--stage:#30303f;--accent:#8bdde6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,-apple-system,"PingFang SC",sans-serif}
header{max-width:1200px;margin:auto;padding:28px 20px 8px}h1{margin:0;font-size:26px}header p{color:var(--muted);margin:6px 0}
.bar{display:flex;gap:8px;flex-wrap:wrap;position:sticky;top:0;background:#161b25ee;padding:10px 20px;z-index:3;border-bottom:1px solid #343e4e}
button,select{font:inherit;font-size:14px;border:1px solid #495568;border-radius:8px;padding:6px 12px;background:#263347;color:#fff;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px;max-width:1200px;margin:16px auto;padding:0 20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.card h2{font-size:16px;margin:10px 14px 0;display:flex;justify-content:space-between;align-items:baseline}.card h2 small{font-weight:400;color:var(--muted);font-size:12px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);margin-top:8px}
.side{background:var(--stage);display:flex;flex-direction:column;align-items:center;padding:8px 0 6px;overflow:hidden}
.side b{font-size:12px;color:var(--muted);font-weight:500}.side.new b{color:var(--accent)}
canvas{width:192px;height:208px;max-width:100%;height:auto;aspect-ratio:384/416}
.zoom .grid{grid-template-columns:1fr}.zoom canvas{width:384px}
.white .side{background:#fff}.black .side{background:#000}.checker .side{background:repeating-conic-gradient(#bbb 0 25%,#eee 0 50%) 0/24px 24px}
.card footer{display:flex;gap:6px;padding:8px 12px;font-size:12px;color:var(--muted);align-items:center}
.card footer button{font-size:12px;padding:3px 8px}
@media (max-width:520px){.grid{grid-template-columns:1fr;padding:0 16px}.bar{padding:10px 16px}header{padding:20px 16px 4px}}
</style>
<header><h1>千夏 R06 / R07 动作对照</h1><p>左边是上一轮 R06，右边是本轮 R07。两边共用同一时钟和同一套眨眼，R06 眨眼 6 级，R07 眨眼 12 级。默认 192×208 实际显示尺寸、真实速度。</p></header>
<div class="bar"><button id="toggle">暂停</button><button id="restart">全部重新开始</button><button id="zoom">放大 2 倍</button><select id="speed"><option value="1">真实速度</option><option value="0.5">半速</option><option value="0.25">四分之一速度</option></select><select id="bg"><option value="">深灰背景</option><option value="white">白色背景</option><option value="black">黑色背景</option><option value="checker">棋盘格背景</option></select><button id="blink">眨眼：开</button></div>
<main class="grid" id="grid"></main>
<script>
const OLD=__OLD__,NEW=__NEW__,NAMES=__NAMES__;
let paused=false,speed=1,blink=true,time=0,last=performance.now();const cards=[];
// Decode once into a resident ImageBitmap: plain <img> atlases can be evicted and re-decoded
// mid-playback, which stalls the first frames of a blink.
function load(src){return new Promise((ok,no)=>{const im=new Image;im.onload=()=>createImageBitmap(im).then(ok,()=>ok(im));im.onerror=()=>no(src);im.src=src})}
function select(s,t){const dur=s.durationsMs.reduce((a,b)=>a+b,0),lead=s.durationsMs.slice(0,s.loopStart).reduce((a,b)=>a+b,0);let ms=t*1000;if(ms>=dur)ms=lead+(ms-lead)%(dur-lead);for(let i=0;i<s.sequence.length;i++){if(ms<s.durationsMs[i])return s.sequence[i];ms-=s.durationsMs[i]}return s.sequence.at(-1)}
const blinks=[];let seed=48173,end=0;function rng(){seed=(1664525*seed+1013904223)>>>0;return seed/4294967296}
function extend(t){while(end<t+10){let st=end+2.8+4.2*rng(),d=.18+.08*rng();blinks.push([st,d]);end=st+d;if(rng()<.125){st=end+.10+.08*rng();d=.18+.08*rng();blinks.push([st,d]);end=st+d}}}
const sm=x=>{x=Math.min(Math.max(x,0),1);return x*x*(3-2*x)};
// Same lid curve as YukioPlayer BlinkClock.level(at:levels:); each side uses its own level count.
function lidAmount(t){if(!blink)return 0;extend(t);for(const[st,d]of blinks){const u=(t-st)/d;if(u<=0)break;if(u<1)return u<.36?sm(u/.36):u<.52?1:1-sm((u-.52)/.48)}return 0}
// Repaint a canvas only when its body frame or lid pose changes.
// When only the lid changes, only the small eye box is repainted.
function paint(side,s,t,a){const f=select(s,t),l=s.blink&&side.eye?Math.round(a*s.blink.levels):0;if(side.f===f&&side.l===l)return;const ctx=side.ctx,b=s.blink,fx=f%s.columns*384,fy=Math.floor(f/s.columns)*416;
if(side.f!==f){ctx.clearRect(0,0,384,416);ctx.drawImage(side.body,fx,fy,384,416,0,0,384,416)}else{ctx.clearRect(b.x,b.y,b.width,b.height);ctx.drawImage(side.body,fx+b.x,fy+b.y,b.width,b.height,b.x,b.y,b.width,b.height)}
side.f=f;side.l=l;if(l){const n=b.frames[f][l-1];ctx.clearRect(b.x,b.y,b.width,b.height);ctx.drawImage(side.eye,n%b.columns*b.width,Math.floor(n/b.columns)*b.height,b.width,b.height,b.x,b.y,b.width,b.height)}}
async function init(){for(const s of NEW.states){const o=OLD.states.find(x=>x.id===s.id);const el=document.createElement('article');el.className='card';
const sec=(x)=>(x.durationsMs.reduce((a,b)=>a+b,0)/1000).toFixed(1);
el.innerHTML='<h2>'+NAMES[s.id]+'<small>'+(s.mode==='enter_then_hold'?'进入一次后停留':s.mode==='static'?'静止姿态':(o.mode!==s.mode?'R06 '+(o.mode==='loop'?'循环':'一次')+' → R07 循环 '+sec(s)+' 秒':'循环 R06 '+sec(o)+' 秒 → R07 '+sec(s)+' 秒'))+'</small></h2><div class="pair"><div class="side"><b>R06 上一轮</b><canvas width="384" height="416"></canvas></div><div class="side new"><b>R07 本轮</b><canvas width="384" height="416"></canvas></div></div><footer><button>重新播放这一格</button><span class="meter"></span></footer>';
document.querySelector('#grid').append(el);const [c1,c2]=el.querySelectorAll('canvas');
const card={s,o,el,offset:0,a:{ctx:c1.getContext('2d'),body:await load('../qianxia-motion-R06/motion/'+o.asset),eye:o.blink?await load('../qianxia-motion-R06/motion/'+o.blink.asset):null},b:{ctx:c2.getContext('2d'),body:await load('motion/'+s.asset),eye:s.blink?await load('motion/'+s.blink.asset):null}};
el.querySelector('footer button').onclick=()=>{card.offset=time;card.a.f=card.b.f=null};cards.push(card)}
// Touch every eye atlas once before playback so the first blink does not pay the GPU upload.
for(const c of cards)for(const [side,s] of [[c.a,c.o],[c.b,c.s]])if(side.eye&&s.blink){const b=s.blink;side.ctx.drawImage(side.eye,0,0,b.width,b.height,b.x,b.y,b.width,b.height);side.f=null}
requestAnimationFrame(tick)}
function tick(now){if(!paused)time+=Math.min((now-last)/1000,.1)*speed;last=now;const a=lidAmount(time);for(const c of cards){const t=Math.max(0,time-c.offset);paint(c.a,c.o,t,a);paint(c.b,c.s,t,a)}requestAnimationFrame(tick)}
document.querySelector('#toggle').onclick=e=>{paused=!paused;e.target.textContent=paused?'继续':'暂停'};
document.querySelector('#restart').onclick=()=>{cards.forEach(c=>c.offset=time)};
document.querySelector('#zoom').onclick=e=>{document.body.classList.toggle('zoom');e.target.textContent=document.body.classList.contains('zoom')?'实际尺寸':'放大 2 倍'};
document.querySelector('#speed').onchange=e=>speed=+e.target.value;
document.querySelector('#bg').onchange=e=>{for(const n of['white','black','checker'])document.body.classList.remove(n);if(e.target.value)document.body.classList.add(e.target.value)};
document.querySelector('#blink').onclick=e=>{blink=!blink;cards.forEach(c=>c.a.f=c.b.f=null);e.target.textContent='眨眼：'+(blink?'开':'关')};
init().catch(e=>document.querySelector('#grid').textContent='资源读取失败：'+e);
</script></html>'''
html=html.replace('__OLD__',json.dumps(old)).replace('__NEW__',json.dumps(new)).replace('__NAMES__',json.dumps(names,ensure_ascii=False))
(R/'compare.html').write_text(html)
print('compare',R/'compare.html')
