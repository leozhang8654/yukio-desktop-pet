from pathlib import Path
from PIL import Image
import numpy as np,cv2,json
r=Path(__file__).resolve().parents[1]
rois={'default_work/iris-left':[(437,559,462,579)],'default_work/iris-right':[(623,566,642,584)],'failed/iris-left':[(438,545,460,562)],'idle/iris-right':[(625,563,644,581)],'read_web/iris-left':[(428,493,450,513),(434,552,456,566)],'read_web/iris-right':[(672,503,693,525)],'respond/iris-left':[(489,544,511,563)],'respond/iris-right':[(625,551,644,569)],'view_image/iris-left':[(443,555,464,574)],'write_file/iris-left':[(438,555,463,575)]};rec=[]
for key,boxes in rois.items():
 state,part=key.split('/');p=r/'masks'/state/(part+'.png');a=np.array(Image.open(p));src=np.array(Image.open(next((r/'source').glob('*-'+state+'.png')))).astype(float);count=0
 for x0,y0,x1,y1 in boxes:
  m=a[y0:y1,x0:x1].copy();R,G,B=src[y0:y1,x0:x1,:3].transpose(2,0,1)
  light=((R>145)&(G>100)&(B>110)).astype('uint8');n,labels,stats,_=cv2.connectedComponentsWithStats(light,8);bg=np.zeros(light.shape,bool)
  for i in range(1,n):
   c=labels==i
   if np.any(c&(m==0)):bg|=c
  # Only the source-colored regions connected to external sclera/skin are excluded.
  border=cv2.distanceTransform((~bg).astype('uint8'),cv2.DIST_L2,5)<1.5
  limit=np.clip((190-R)/65,0,1);new=m.copy();new[bg|border]=np.minimum(new[bg|border],(limit[bg|border]*255).round().astype('uint8'));count+=int(np.sum(new!=m));a[y0:y1,x0:x1]=new
 Image.fromarray(a).save(p);rec.append({'part':key,'rois':boxes,'changed_pixels':count})
(r/'reference/corner-repairs.json').write_text(json.dumps({'method':'within reviewer-specified corner ROIs only, remove source sclera/skin connected to external background; preserve dark iris contour and all non-ROI pixels','parts':rec},indent=2));print(rec)
