from pathlib import Path
from PIL import Image,ImageDraw
import json
out=Path(__file__).resolve().parent;r=out.parents[1]/'qianxia-motion-R05';m=json.loads((r/'motion/motion.json').read_text());ix=json.loads((out/'inspection-index.json').read_text());records=[]
for q in ix:
 n=q['state'];s=next(s for s in m['states'] if s['id']==n);a=Image.open(r/'motion'/s['asset']).convert('RGBA');count=max(s['sequence'])+1;box=q['detail_roi_2x'];w,h=box[2]-box[0],box[3]-box[1]
 for begin in range(0,count,9):
  ids=list(range(begin,min(begin+9,count)));rows=(len(ids)+2)//3;c=Image.new('RGB',((w*2+10)*3,(h*2+24)*rows),'#bbb');d=ImageDraw.Draw(c)
  for j,i in enumerate(ids):
   frame=a.crop((i%s['columns']*384,i//s['columns']*416,(i%s['columns']+1)*384,(i//s['columns']+1)*416));im=frame.crop(box);bg=Image.new('RGBA',im.size,'magenta');bg.alpha_composite(im);x=j%3*(w*2+10);y=j//3*(h*2+24);c.paste(bg.convert('RGB').resize((w*2,h*2),Image.Resampling.NEAREST),(x,y+24));d.text((x,y+4),f'{n} frame {i}',fill='black')
  file=f'evidence/{n}-all-frames-{begin:02d}-200.png';c.save(out/file);records.append({'state':n,'file':file,'unique_frame_indices':ids,'roi_384x416':box})
(out/'all-frames-index.json').write_text(json.dumps(records,indent=2));print(json.dumps(records,indent=2))
