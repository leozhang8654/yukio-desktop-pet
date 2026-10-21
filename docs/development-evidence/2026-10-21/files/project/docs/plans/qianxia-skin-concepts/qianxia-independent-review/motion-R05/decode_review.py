from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json
out=Path(__file__).resolve().parent;root=out.parents[1]/'qianxia-motion-R05';ev=out/'evidence';manifest=json.loads((root/'motion/motion.json').read_text());records=[]
def tile(im,i,w,h,cols):return im.crop(((i%cols)*w,(i//cols)*h,(i%cols+1)*w,(i//cols+1)*h))
def bg(im,color='#dddddd'):
 b=Image.new('RGBA',im.size,color);b.alpha_composite(im);return b.convert('RGB')
for st in manifest['states']:
 name=st['id'];
 if name not in ['write_file','verify','failed']:continue
 src=Image.open(root/'rigs'/name/'source-2x.png').convert('RGBA');sheet=Image.open(root/'motion'/st['asset']).convert('RGBA');w,h=st['frameWidth']*st['pixelScale'],st['frameHeight']*st['pixelScale'];n=max(st['sequence'])+1;frames=[tile(sheet,i,w,h,st['columns']) for i in range(n)];a=np.stack([np.array(f) for f in frames]);base=a[0];delta=np.abs(a.astype('int16')-base);blink=st.get('blink');deltaBody=delta.copy()
 if blink:deltaBody[:,blink['y']:blink['y']+blink['height'],blink['x']:blink['x']+blink['width']]=0
 energy=deltaBody.sum(axis=(1,2,3));maxf=int(energy.argmax());deltaAny=delta.sum(axis=(1,2,3));maxany=int(deltaAny.argmax());chosen=[0,maxf if energy[maxf]>0 else maxany,st['sequence'][-1]];canvas=Image.new('RGB',(w*4+30,h+235),'#bbb');d=ImageDraw.Draw(canvas)
 for i,(label,im) in enumerate([('source-2x',src)]+[(f'encoded frame {j}',frames[j]) for j in chosen]):canvas.paste(bg(im),(i*(w+10),24));d.text((i*(w+10),5),name+' '+label,fill='black');canvas.paste(bg(im).resize((192,208)),(i*(w+10),h+27))
 canvas.save(ev/f'{name}-source-encoded.png')
 maskpaths=list((root/'inputs/masks'/name).glob('*.png'));handpaths=[p for p in maskpaths if not p.name.startswith('iris-')];box=None
 if handpaths:
  masks=[Image.open(p).convert('L') for p in handpaths];boxes=[m.getbbox() for m in masks];scale=w/masks[0].width;box=[max(0,int(min(b[j] for b in boxes)*scale)-16) for j in [0,1]]+[min([w,h][j],int(max(b[j+2] for b in boxes)*scale)+17) for j in [0,1]]
 elif blink:box=[blink['x']-8,blink['y']-8,blink['x']+blink['width']+8,blink['y']+blink['height']+8]
 else:box=[80,90,300,270]
 # diverse sampled encoded frames, including strongest body delta and pairwise farthest frame
 f2=int(np.abs(a.astype('int16')-a[maxf].astype('int16')).sum(axis=(1,2,3)).argmax());ids=list(dict.fromkeys([0,maxf,f2,n//3,2*n//3,n-1]));cw,ch=box[2]-box[0],box[3]-box[1];c=Image.new('RGB',(cw*2*3+20,(ch*2+24)*2),'#bbb');dr=ImageDraw.Draw(c)
 for i,j in enumerate(ids):x=(i%3)*(cw*2+10);y=(i//3)*(ch*2+24);c.paste(bg(frames[j].crop(box),'#ff00ff').resize((cw*2,ch*2),Image.Resampling.NEAREST),(x,y+24));dr.text((x,y+4),f'{name} frame {j}; ROI {box}',fill='black')
 c.save(ev/f'{name}-decoded-detail200.png')
 if blink:
  eyesheet=Image.open(root/'motion'/blink['asset']).convert('RGBA');bw,bh=blink['width'],blink['height'];er=[blink['x']-3,blink['y']-3,blink['x']+bw+3,blink['y']+bh+3];ecw,ech=er[2]-er[0],er[3]-er[1];c=Image.new('RGB',(ecw*3*3+20,(ech*3+24)*3),'#bbb');dr=ImageDraw.Draw(c)
  eyeims=[('source',src.crop(er)),('encoded open',frames[0].crop(er))]
  for level,eidx in enumerate(blink['frames'][0]):
   im=frames[0].copy();im.paste(tile(eyesheet,eidx,bw,bh,blink['columns']),(blink['x'],blink['y']));eyeims.append((f'closing {level+1} tile {eidx}',im.crop(er)))
  for i,(label,im) in enumerate(eyeims):x=(i%3)*(ecw*3+10);y=(i//3)*(ech*3+24);c.paste(bg(im).resize((ecw*3,ech*3),Image.Resampling.NEAREST),(x,y+24));dr.text((x,y+4),name+' '+label,fill='black')
  c.save(ev/f'{name}-decoded-lids300.png')
 records.append({'state':name,'body_unique_frames':n,'context_frames':chosen,'detail_frames':ids,'detail_roi_2x':box,'max_body_delta_frame':maxf,'has_blink':bool(blink),'duration_ms':sum(st['durationsMs']),'loopStart':st['loopStart'],'mode':st.get('mode')})
(out/'inspection-index.json').write_text(json.dumps(records,indent=2));print(json.dumps(records,indent=2))
