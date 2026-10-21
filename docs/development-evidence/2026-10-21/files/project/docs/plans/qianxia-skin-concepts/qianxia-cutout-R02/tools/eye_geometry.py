from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,cv2,json
r=Path(__file__).resolve().parents[1];rows=[]
for p in sorted((r/'masks').glob('*/iris-*.png')):
 a=np.array(Image.open(p));ys,xs=np.nonzero(a);x0,x1=int(xs.min()),int(xs.max());y0,y1=int(ys.min()),int(ys.max());src=Image.open(next((r/'source').glob('*-'+p.parent.name+'.png')));box=(x0-6,y0-6,x1+7,y1+7);im=src.crop(box).resize(((x1-x0+13)*4,(y1-y0+13)*4));d=ImageDraw.Draw(im)
 for x in range((x0//10)*10,x1+8,10):
  u=(x-box[0])*4;d.line((u,0,u,im.height),fill=(80,80,255),width=1);d.text((u,0),str(x),fill='blue')
 for y in range((y0//10)*10,y1+8,10):
  v=(y-box[1])*4;d.line((0,v,im.width,v),fill=(80,80,255),width=1);d.text((0,v),str(y),fill='blue')
 out=r/'experiments'/p.parent.name/p.stem;out.mkdir(parents=True,exist_ok=True);im.save(out/'grid.png');rows.append([p.parent.name,p.stem,x0,y0,x1,y1])
print(json.dumps(rows))
