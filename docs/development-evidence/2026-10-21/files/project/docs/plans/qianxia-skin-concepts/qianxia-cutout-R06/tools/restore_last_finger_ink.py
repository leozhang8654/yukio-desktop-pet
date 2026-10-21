from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json
r=Path(__file__).resolve().parents[1];old=r.parent/'qianxia-cutout-R05';key='write_file/left-hand';p=r/'masks'/(key+'.png');a=np.array(Image.open(old/'masks'/(key+'.png')))
points=[(434.2,778),(439,778),(448,789),(466,796),(466,799),(464,802),(461,804),(456,804.4),(452,804.2),(448,803.4),(444.5,801.5),(442,798),(439.5,795),(437.7,791),(435.8,787),(434.8,783)]
pts=np.array(points);out=[]
for i in range(len(pts)):
 a0,b,c,d=pts[(i-1)%len(pts)],pts[i],pts[(i+1)%len(pts)],pts[(i+2)%len(pts)];t=np.linspace(0,1,60,endpoint=False)[:,None];out.extend((2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*(c-a0)*.22+(-2*t**3+3*t*t)*c+(t**3-t*t)*(d-b)*.22)
out=np.array(out);lo=np.floor(out.min(0)-2).astype(int);hi=np.ceil(out.max(0)+3).astype(int);im=Image.new('L',tuple((hi-lo)*8));ImageDraw.Draw(im).polygon([tuple(x) for x in (out-lo)*8],fill=255);region=np.array(im.resize(tuple(hi-lo),Image.Resampling.BOX));x0,y0=lo;x1,y1=hi;before=a.copy();a[y0:y1,x0:x1]=np.maximum(a[y0:y1,x0:x1],region);Image.fromarray(a).save(p)
(r/'reference/last-finger-ink.json').write_text(json.dumps({'part':key,'points':points,'operation':'union of source-visible finger ink and skin; no source RGB edits, no global dilation','changed_pixels':int(np.sum(a!=before))},indent=2));print('changed',np.sum(a!=before))
# The enclosed 3x9 region is the original dark finger separator and skin, not background.
a[771:780,432:435]=255;Image.fromarray(a).save(p)
