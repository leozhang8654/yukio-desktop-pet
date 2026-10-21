from pathlib import Path
from PIL import Image,ImageDraw
import json,numpy as np
out=Path(__file__).resolve().parent;r=out.parents[1]/'qianxia-motion-R02';m=json.loads((r/'motion/motion.json').read_text());ev=out/'evidence';records=[]
def tile(im,i,w,h,c):return im.crop((i%c*w,i//c*h,(i%c+1)*w,(i//c+1)*h))
def bg(im,k):
 a=np.zeros((im.height,im.width,4),np.uint8);a[:,:,3]=255
 if k=='checker':
  y,x=np.indices((im.height,im.width));v=np.where((x//8+y//8)%2,190,245);a[:,:,:3]=v[:,:,None]
 else:a[:,:,:3]={'black':[0,0,0],'white':[255,255,255],'magenta':[255,0,255]}[k]
 b=Image.fromarray(a);b.alpha_composite(im);return b.convert('RGB')
for s in m['states']:
 n=s['id'];im=Image.open(r/'motion'/s['asset']).convert('RGBA');frames=[tile(im,i,384,416,s['columns']) for i in range(max(s['sequence'])+1)];b=s.get('blink')
 if b:
  box=(b['x'],b['y'],b['x']+b['width'],b['y']+b['height']);crops=[f.crop(box) for f in frames];energy=[np.abs(np.array(f).astype('int16')-np.array(crops[0]).astype('int16')).sum() for f in crops];idx=int(np.argmax(energy));eye=Image.open(r/'motion'/b['asset']).convert('RGBA');w,h=b['width'],b['height'];can=Image.new('RGB',(w*2*3+20,(h*2+24)*4),'#bbb');d=ImageDraw.Draw(can)
  cells=[(f'max-eye body {idx} close {l+1}',tile(eye,b['frames'][idx][l],w,h,b['columns']),'white') for l in range(6)]+[(f'close 3 {k}',tile(eye,b['frames'][idx][2],w,h,b['columns']),k) for k in ['black','white','magenta','checker']]
  for j,(label,pic,k) in enumerate(cells):x=(j%3)*(w*2+10);y=(j//3)*(h*2+24);can.paste(bg(pic,k).resize((w*2,h*2),Image.Resampling.NEAREST),(x,y+24));d.text((x,y+4),label,fill='black')
  can.save(ev/f'{n}-max-gaze-and-backgrounds200.png');records.append({'state':n,'max_eye_delta_frame':idx,'six_levels_viewed':True})
 if n=='respond':
  box=(85,178,173,249);w,h=88,71;can=Image.new('RGB',((w*2+10)*5,(h*2+24)*5),'#bbb');d=ImageDraw.Draw(can)
  for j,f in enumerate(frames):x=j%5*(w*2+10);y=j//5*(h*2+24);can.paste(bg(f.crop(box),'magenta').resize((w*2,h*2),Image.Resampling.NEAREST),(x,y+24));d.text((x,y+4),f'frame {j}',fill='black')
  can.save(ev/'respond-all-25-frames200.png');box=(80,171,186,264);w,h=106,93;can=Image.new('RGB',(w*4+10,h*4+48),'#bbb');d=ImageDraw.Draw(can)
  for j,k in enumerate(['black','white','magenta','checker']):x=j%2*(w*2+10);y=j//2*(h*2+24);can.paste(bg(frames[-1].crop(box),k).resize((w*2,h*2),Image.Resampling.NEAREST),(x,y+24));d.text((x,y+4),'frame 24 '+k,fill='black')
  can.save(ev/'respond-encoded-four-bg200.png')
(out/'extra-index.json').write_text(json.dumps(records,indent=2))
