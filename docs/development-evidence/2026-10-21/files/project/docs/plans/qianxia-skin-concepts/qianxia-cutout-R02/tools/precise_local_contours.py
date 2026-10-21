from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,runpy
r=Path(__file__).resolve().parents[1];old=r.parent/'qianxia-cutout-R01'
# Retain original approved-scope arcs; only replace the explicitly reviewed defective contour stretches.
def smooth(p):
 p=np.array(p,float);out=[]
 for i in range(len(p)):
  a,b,c,d=p[(i-1)%len(p)],p[i],p[(i+1)%len(p)],p[(i+2)%len(p)];t=np.linspace(0,1,100,endpoint=False)[:,None]
  out.extend((2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*(c-a)*.3+(-2*t**3+3*t*t)*c+(t**3-t*t)*(d-b)*.3)
 return np.array(out)
def poly(pts,size):
 pts=smooth(pts);lo=np.floor(pts.min(0)-2).astype(int);hi=np.ceil(pts.max(0)+3).astype(int);a=Image.new('L',tuple((hi-lo)*8));ImageDraw.Draw(a).polygon([tuple(p) for p in (pts-lo)*8],fill=255);full=Image.new('L',size);full.paste(a.resize(tuple(hi-lo),Image.Resampling.BOX),tuple(lo));return np.array(full)
patches={
'failed/hand-and-card':([325,590,425,762],[(369,644),(363,624),(363,615),(369,610),(384,605),(440,592),(450,702),(425,710),(417,711),(420,717),(418,727),(414,732),(409,737),(409,742),(409,746),(407,751),(401,756),(390,758),(377,756),(364,751),(352,741),(344,730),(339,720),(335,709),(332,698),(332,684),(335,673),(341,661),(352,650)]),
'respond/hand-and-card':([300,723,403,781],[(299,716),(440,713),(440,725),(413,728),(389,730),(385,732),(386,736),(390,741),(392,747),(392,752),(391,759),(386,765),(378,772),(366,776),(355,776),(342,772),(330,765),(320,754),(313,741),(308,727),(305,714)]),
'view_image/hand-and-stylus':([437,746,465,778],[(435,743),(461,741),(462,749),(458,756),(450,762),(439,765),(438,770),(433,777),(429,770)]),
'write_file/right-hand':([735,771,759,807],[(752,765),(762,771),(762,807),(749,799),(744,797),(743,792),(746,780)]),
'write_file/left-hand':([367,792,416,820],[(362,786),(416,782),(416,814),(406,809),(402,802),(400,790),(399,800),(396,806),(389,810),(382,809),(376,807),(375,799),(374,788),(373,797),(369,803),(362,803)]),
'read_web/pointing-hand':([406,630,437,667],[(400,626),(412,628),(417,636),(420,644),(423,650),(423,658),(429,665),(432,675),(403,677)]),
'idle/touching-hand':([419,809,439,830],[(415,803),(442,803),(441,820),(434,823),(428,823),(423,820),(420,817),(415,822)])
}
records=[]
for key,(box,pts) in patches.items():
 state,name=key.split('/');f=r/'masks'/state/(name+'.png');a=np.array(Image.open(f));p=poly(pts,Image.open(f).size);x0,y0,x1,y1=box
 # Replace the complete local region to avoid holes from color-threshold experiments.
 a[y0:y1,x0:x1]=p[y0:y1,x0:x1]
 # Retain the stable original coverage outside the changed local region.
 Image.fromarray(a).save(f);records.append({'part':key,'box':box,'points':pts})
(r/'reference/precise-local-contours.json').write_text(json.dumps(records,indent=2))
