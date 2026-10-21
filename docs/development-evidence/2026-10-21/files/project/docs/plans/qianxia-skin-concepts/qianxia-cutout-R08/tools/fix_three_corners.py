from pathlib import Path
from PIL import Image
import numpy as np,json
r=Path(__file__).resolve().parents[1];records=[]
# Source-coordinate local boundary limits, preserving all source RGB and non-ROI alpha.
ops=[('default_work/iris-left',(449,569,456,574),'left',[(569,451.15),(570,451.8),(571,452.4),(572,453.15),(573,454.1)]),('write_file/iris-left',(450,564,458,569),'left',[(564,451.8),(565,452.25),(566,452.9),(567,453.65),(568,454.6)]),('read_web/iris-right',(683,508,690,514),'right',[(508,683.3),(509,683.9),(510,684.5),(511,685.1),(512,685.6),(513,686.0)])]
for key,box,side,knots in ops:
 p=r/'masks'/(key+'.png');a=np.array(Image.open(p));old=a.copy();x0,y0,x1,y1=box
 for y in range(y0,y1):
  edge=np.interp(y,*np.array(knots).T);xs=np.arange(x0,x1);coverage=np.clip((xs+.5-edge) if side=='left' else (edge-xs+.5),0,1)
  a[y,x0:x1]=np.minimum(a[y,x0:x1],np.rint(coverage*255).astype('uint8'))
 Image.fromarray(a).save(p);records.append(dict(part=key,roi=box,boundary=side,knots=knots,changed_pixels=int(np.sum(a!=old))))
(r/'reference/three-corner-repairs.json').write_text(json.dumps(records,indent=2));print(records)
