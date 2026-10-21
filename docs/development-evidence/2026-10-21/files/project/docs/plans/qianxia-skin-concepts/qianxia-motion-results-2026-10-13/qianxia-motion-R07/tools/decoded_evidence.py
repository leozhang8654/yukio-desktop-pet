"""Maker's encoded-file inspection evidence; never imports or rewrites rigs."""
from pathlib import Path
from PIL import Image,ImageDraw
import json,numpy as np
R=Path(__file__).resolve().parents[1]
def tile(im,n,w,h,c):return im.crop((n%c*w,n//c*h,(n%c+1)*w,(n//c+1)*h))
def composite(im,bg):
 out=Image.new('RGBA',im.size,bg);out.alpha_composite(im);return out.convert('RGB')
for s in json.loads((R/'motion/motion.json').read_text())['states']:
 name=s['id'];atlas=Image.open(R/'motion'/s['asset']).convert('RGBA');frames=[tile(atlas,n,384,416,s['columns']) for n in range(max(s['sequence'])+1)];source=Image.open(R/f'rigs/{name}/source-2x.png').convert('RGBA');allow=np.array(Image.open(R/f'rigs/{name}/eyes-allowed-2x.png'))>0
 energy=[np.abs(np.array(f).astype(float)-np.array(source).astype(float))[~allow].sum() for f in frames];extreme=frames[int(np.argmax(energy))]
 out=Image.new('RGB',(384*4,440),'#222222');draw=ImageDraw.Draw(out)
 for i,bg in enumerate(['#000000','#ffffff','#ff00ff','#303040']):out.paste(composite(extreme,bg),(i*384,24));draw.text((i*384+8,5),name+' / '+bg,fill='white')
 out.save(R/f'review/{name}-encoded-backgrounds.png')
 if s['blink']:
  b=s['blink'];eyes=Image.open(R/'motion'/b['asset']).convert('RGBA');box=(b['x']-3,b['y']-3,b['x']+b['width']+3,b['y']+b['height']+3);w=(box[2]-box[0])*3;h=(box[3]-box[1])*3
  views=[source,frames[0]];rows=(len(b['frames'][0])+3)//2
  out=Image.new('RGB',(w*2,(h+24)*rows),'#303040');draw=ImageDraw.Draw(out)
  for n in b['frames'][0]:
   f=frames[0].copy();f.paste(tile(eyes,n,b['width'],b['height'],b['columns']),(b['x'],b['y']));views.append(f)
  for i,f in enumerate(views):x=i%2*w;y=i//2*(h+24);out.paste(composite(f.crop(box),'#dddddd').resize((w,h),Image.Resampling.NEAREST),(x,y+24));draw.text((x+4,y+4),name+' / '+(['source','encoded open']+[f"{j}/{b['levels']}" for j in range(1,b['levels']+1)])[i],fill='white')
  out.save(R/f'review/{name}-encoded-lids.png')
print('Decoded evidence written for 12 states')
