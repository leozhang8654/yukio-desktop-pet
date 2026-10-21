from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json
r=Path(__file__).resolve().parents[1];changes=[]
# Precisely bounded finger edges flagged by the 200% contour review.
for state,part,axis,lo,hi in [('failed','hand-and-card','right',693,750),('write_file','left-hand','bottom',355,474),('write_file','right-hand','bottom',744,846)]:
 p=r/'masks'/state/(part+'.png');m=np.array(Image.open(p));src=np.array(Image.open(next((r/'source').glob('*-'+state+'.png'))));old=m.copy();dark=src[:,:,:3].max(2)<95
 for v in range(lo,hi+1):
  line=m[v,:] if axis=='right' else m[:,v];nz=np.flatnonzero(line>0)
  if not len(nz):continue
  end=int(nz[-1]);candidates=[k for k in range(end+1,end+5) if (dark[v,k] if axis=='right' else dark[k,v])]
  if candidates:
   limit=max(candidates)
   if axis=='right':m[v,end+1:limit+1]=255
   else:m[end+1:limit+1,v]=255
 Image.fromarray(m).save(p);changes.append({'state':state,'part':part,'axis':axis,'range':[lo,hi],'added_pixels':int(((m>0)&(old==0)).sum()),'reason':'include omitted original dark ink along visually checked fingertip edges; max 4 source pixels'})
# Remove two clearly visible sleeve-colour wedges, retaining surrounding ink.
for state,part,box in [('idle','touching-hand',(417,816,426,826)),('read_web','pointing-hand',(419,652,429,661))]:
 p=r/'masks'/state/(part+'.png');m=np.array(Image.open(p));src=np.array(Image.open(next((r/'source').glob('*-'+state+'.png'))));x0,y0,x1,y1=box;c=src[y0:y1,x0:x1,:3].astype(int);pink=(c[:,:,0]>170)&(c[:,:,0]-c[:,:,1]>55)&(c[:,:,2]-c[:,:,1]>12);local=m[y0:y1,x0:x1];removed=int(((local>0)&pink).sum());local[pink]=0;Image.fromarray(m).save(p);changes.append({'state':state,'part':part,'box':box,'removed_pixels':removed,'reason':'visually identified external pink sleeve wedge'})
(r/'reference/local-ink-refinement.json').write_text(json.dumps(changes,indent=2))
