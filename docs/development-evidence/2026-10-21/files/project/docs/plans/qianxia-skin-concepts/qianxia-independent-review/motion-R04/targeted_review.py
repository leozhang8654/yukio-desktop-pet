from pathlib import Path
from PIL import Image,ImageDraw
import json,numpy as np
out=Path(__file__).resolve().parent;r=out.parents[1]/'qianxia-motion-R04';m=json.loads((r/'motion/motion.json').read_text());ix=json.loads((out/'inspection-index.json').read_text())
for n,box,ids in [('failed',[108,207,143,247],[0,7,14,20]),('write_file',[107,231,156,263],[0,3,9,10]),('verify',[112,188,163,252],[0,14,25,36]),('read_web',[108,198,145,227],[0,9,11,18]),('respond',[105,209,151,249],[0,8,16,24])]:
 s=next(s for s in m['states'] if s['id']==n);a=Image.open(r/'motion'/s['asset']).convert('RGBA');src=Image.open(r/'rigs'/n/'source-2x.png').convert('RGBA');clean=Image.open(r/'rigs'/n/'cleanplate-2x.png').convert('RGBA');w,h=box[2]-box[0],box[3]-box[1];cells=[('source',src),('cleanplate',clean)]+[(f'frame {i}',a.crop((i%s['columns']*384,i//s['columns']*416,(i%s['columns']+1)*384,(i//s['columns']+1)*416))) for i in ids];can=Image.new('RGB',((w*5+10)*3,(h*5+24)*2),'#bbb');d=ImageDraw.Draw(can)
 for j,(label,pic) in enumerate(cells):x=j%3*(w*5+10);y=j//3*(h*5+24);im=pic.crop(box);bg=Image.new('RGBA',im.size,'magenta');bg.alpha_composite(im);can.paste(bg.convert('RGB').resize((w*5,h*5),Image.Resampling.NEAREST),(x,y+24));d.text((x,y+4),n+' '+label+' '+str(box),fill='black')
 can.save(out/'evidence'/f'{n}-targeted500.png')
# 4 backgrounds of each actual max-delta body ROI
for q in ix:
 s=next(s for s in m['states'] if s['id']==q['state']);a=Image.open(r/'motion'/s['asset']).convert('RGBA');i=q['context_frames'][1];f=a.crop((i%s['columns']*384,i//s['columns']*416,(i%s['columns']+1)*384,(i//s['columns']+1)*416));box=q['detail_roi_2x'];im=f.crop(box);w,h=im.size;can=Image.new('RGB',(w*4+10,h*4+48),'#bbb');d=ImageDraw.Draw(can)
 for j,k in enumerate(['black','white','magenta','checker']):
  x=j%2*(w*2+10);y=j//2*(h*2+24)
  if k=='checker':
   yy,xx=np.indices((h,w));ar=np.where((xx//8+yy//8)%2,190,245).astype('uint8');bg=Image.fromarray(np.repeat(ar[:,:,None],3,2)).convert('RGBA')
  else:bg=Image.new('RGBA',(w,h),k)
  bg.alpha_composite(im);can.paste(bg.convert('RGB').resize((w*2,h*2),Image.Resampling.NEAREST),(x,y+24));d.text((x,y+4),f"{q['state']} frame {i} {k}",fill='black')
 can.save(out/'evidence'/f"{q['state']}-encoded-four-bg200.png")
