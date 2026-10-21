"""Decode candidate atlases, validate interaction-only contracts, build live preview."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from PIL import Image

p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
allowed=np.array(Image.open(Path(__file__).resolve().parents[3]/'sources/interaction-rig/allowed-output-mask.png'))>0
manifest=json.loads((a.assets/'interaction/interaction.json').read_text());rows=[]
for s in manifest['states']:
 im=Image.open(a.assets/'interaction'/s['asset']).convert('RGBA');w=s['frameWidth']*s['pixelScale'];h=s['frameHeight']*s['pixelScale'];cols=im.width//w;frames=[]
 assert im.width%w==0 and im.height%h==0
 assert len(s['sequence'])==len(s['durationsMs']) and all(d>0 for d in s['durationsMs'])
 assert min(s['sequence'])>=0 and max(s['sequence'])<cols*(im.height//h)
 assert 0<=s['loopStart']<len(s['sequence'])
 for i in range(max(s['sequence'])+1):
  f=np.array(im.crop((i%cols*w,i//cols*h,i%cols*w+w,i//cols*h+h)))
  assert not np.any((f[:,:,3]>0)&~allowed),'pixels outside approved output envelope'
  # Match the documented alpha > 24 body silhouette threshold.
  # A single alpha=1 resampling fringe is reported, not treated as solid clipping.
  assert not np.any(f[[0,-1],:,3]>24) and not np.any(f[:,[0,-1],3]>24),'clipped solid canvas edge'
  hits=np.zeros((h,w),bool)
  for y,l,r in s['hitRuns'][i]:
   assert 0<=y<h and 0<=l<r<=w;hits[y,l:r]=True
  assert np.all(f[:,:,3][hits]>0),'hit outside visible body'
  frames.append(f)
 first,last=frames[s['sequence'][s['loopStart']]],frames[s['sequence'][-1]]
 delta=float(np.mean(np.abs(first.astype(float)-last.astype(float))))
 adjacent=[float(np.mean(np.abs(frames[x].astype(float)-frames[y].astype(float)))) for x,y in zip(s['sequence'],s['sequence'][1:])]
 if s['loop'] and adjacent: assert delta<=max(adjacent)*1.25+1e-6,'loop seam larger than adjacent movement'
 rows.append({'id':s['id'],'uniqueFrames':len(frames),'steps':len(s['sequence']),'durationMs':sum(s['durationsMs']),'loopSeamMeanRGBA':delta,'decoded':True,'maxCanvasBorderAlpha':max(int(max(f[[0,-1],:,3].max(),f[:,[0,-1],3].max())) for f in frames),'sha256':hashlib.sha256((a.assets/'interaction'/s['asset']).read_bytes()).hexdigest()})
 if s.get('blink'):
  b=s['blink'];eye=Image.open(a.assets/'interaction'/b['asset']).convert('RGBA');base=frames[0]
  for level in range(6):
   patch=np.array(eye.crop((level*b['width'],0,(level+1)*b['width'],b['height'])))
   assert np.array_equal(patch[:,:,3],base[b['y']:b['y']+b['height'],b['x']:b['x']+b['width'],3])
# The original 12 motion atlases and eyes are not rewritten by this pipeline.
regression=[]
for f in (a.baseline/'motion').glob('*'):
 if f.is_file():
  target=a.assets/'motion'/f.name
  assert hashlib.sha256(f.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest(),f.name
  regression.append(f.name)
report={'encodedChecks':'passed','dailyResourcesUnchanged':regression,'states':rows,'visualReview':'pending','nativeWindows':'pending'}
(a.out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
# Embed metadata to keep the preview usable from file:// without fetch access.
preview='''<!doctype html><meta charset="utf-8"><title>雪绪 · 抛掷与晕眩候选</title>
<style>body{font:15px system-ui;background:#19222d;color:#edf3f8;margin:24px}header{position:sticky;top:0;background:#19222d;padding:12px;z-index:1}button,select,input{margin:5px;padding:6px}main{display:grid;grid-template-columns:repeat(3,minmax(230px,1fr));gap:14px}article{background:#293544;border-radius:12px;padding:12px}canvas{display:block;margin:auto;background:repeating-conic-gradient(#ddd 0 25%,#eee 0 50%) 0/20px 20px}small{display:block;color:#a8c1d1;margin:6px}</style>
<header><b>雪绪 · 交互动画候选</b> <button id="play">暂停</button><button id="step">逐帧 +20 ms</button><select id="speed"><option value="1">原速</option><option value=".25">四分之一速度</option></select><select id="zoom"><option value="1">原尺寸</option><option value="2">200%</option></select><select id="bg"><option value="checker">棋盘格</option><option value="white">白</option><option value="black">黑</option><option value="magenta">洋红</option></select><span id="clock"></span></header><main></main>
<script>const manifest=MANIFEST;const base=BASE;let playing=true,time=0,last=performance.now();const views=[];for(const s of manifest.states){const article=document.createElement('article');article.innerHTML=`<b>${s.id}</b><small></small><canvas width="${s.frameWidth*2}" height="${s.frameHeight*2}"></canvas>`;document.querySelector('main').append(article);const im=new Image;im.src=base+s.asset;views.push({s,im,canvas:article.querySelector('canvas'),label:article.querySelector('small')});}function draw(){document.querySelector("main").style.gridTemplateColumns=Number(zoom.value)===2?"repeat(auto-fit,minmax(464px,1fr))":"repeat(3,minmax(230px,1fr))";for(const v of views){const {s,im,canvas,label}=v;const duration=s.durationsMs.reduce((a,b)=>a+b,0);let t=time%duration,step=0;while(step<s.sequence.length-1&&t>=s.durationsMs[step])t-=s.durationsMs[step++];const index=s.sequence[step],w=canvas.width,h=canvas.height,cols=im.width/w;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,w,h);if(im.complete&&im.width)ctx.drawImage(im,index%cols*w,Math.floor(index/cols)*h,w,h,0,0,w,h);canvas.style.width=s.frameWidth*Number(zoom.value)+'px';const bg=document.querySelector('#bg').value;canvas.style.background=bg==='checker'?'repeating-conic-gradient(#ddd 0 25%,#eee 0 50%) 0/20px 20px':bg;label.textContent=`帧 ${index} · 第 ${Math.floor(time/duration)+1} 遍 · ${duration} ms`;}clock.textContent=(time/1000).toFixed(2)+' s';}function tick(now){if(playing)time+=Math.min(now-last,100)*Number(speed.value);last=now;draw();requestAnimationFrame(tick);}play.onclick=()=>{playing=!playing;play.textContent=playing?'暂停':'播放'};document.querySelector('#step').onclick=()=>{playing=false;time+=20;draw()};requestAnimationFrame(tick);</script>'''
# Preview sits next to the metadata; relative links are independent of machine path.
import os
preview_manifest={**manifest,'states':[{k:v for k,v in state.items() if k!='hitRuns'} for state in manifest['states']]}
preview=preview.replace('MANIFEST',json.dumps(preview_manifest)).replace('BASE',json.dumps(os.path.relpath(a.assets/'interaction',a.out)+'/'))
(a.out/'preview.html').write_text(preview)
print(json.dumps({'passed':True,'states':len(rows),'unchangedDailyFiles':len(regression)}))
