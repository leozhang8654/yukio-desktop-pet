from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
r=Path(__file__).resolve().parents[1];rows=[]
for p in sorted((r/'masks').glob('*/iris-*.png')):
 a=np.array(Image.open(p));ys,xs=np.nonzero(a);box=(int(xs.min())-5,int(ys.min())-5,int(xs.max())+6,int(ys.max())+6);src=Image.open(next((r/'source').glob('*-'+p.parent.name+'.png'))).convert('RGBA').crop(box);cut=Image.open(r/'parts'/p.parent.name/p.name).crop(box);w,h=src.size;row=Image.new('RGB',(800,220),'#888888');d=ImageDraw.Draw(row);d.text((3,3),p.parent.name+'/'+p.stem+' | source / white / black / magenta / mask (200%)',fill='white')
 for i,col in enumerate([None,'white','black','#ff00ff']):
  im=src if col is None else Image.new('RGBA',src.size,col)
  if col is not None:im.alpha_composite(cut)
  row.paste(im.resize((w*2,h*2),Image.Resampling.NEAREST).convert('RGB'),(i*160,25))
 row.paste(Image.open(p).crop(box).resize((w*2,h*2),Image.Resampling.NEAREST).convert('RGB'),(640,25));rows.append(row)
for k in range(0,len(rows),6):
 out=Image.new('RGB',(800,220*len(rows[k:k+6])),'#888888')
 for i,row in enumerate(rows[k:k+6]):out.paste(row,(0,i*220))
 out.save(r/'review'/f'eye-review-page-{k//6+1}.png')
