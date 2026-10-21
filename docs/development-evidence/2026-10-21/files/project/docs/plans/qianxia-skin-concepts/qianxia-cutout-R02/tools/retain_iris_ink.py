from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,cv2,json
r=Path(__file__).resolve().parents[1];meta=json.loads((r/'reference/eye-arc-refinement.json').read_text())['parts'];records=[]
def curve(p):
 p=np.array(p,float);out=[]
 for i in range(len(p)):
  a,b,c,d=p[(i-1)%len(p)],p[i],p[(i+1)%len(p)],p[(i+2)%len(p)];t=np.linspace(0,1,32,endpoint=False)[:,None];out.extend((2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*(c-a)*.3+(-2*t**3+3*t*t)*c+(t**3-t*t)*(d-b)*.3)
 return np.array(out)
for row in meta:
 state,part=row['state'],row['part'];p=r/'masks'/state/(part+'.png');old=np.array(Image.open(p));src=np.array(Image.open(next((r/'source').glob('*-'+state+'.png'))));ys,xs=np.nonzero(old);x0,x1=xs.min()-7,xs.max()+8;y0,y1=ys.min()-6,ys.max()+7;a=old[y0:y1,x0:x1];rgb=src[y0:y1,x0:x1,:3];Y,X=np.indices(a.shape);Y+=y0;X+=x0
 near=cv2.distanceTransform((a<128).astype('uint8'),cv2.DIST_L2,5)<5;ink=(rgb[:,:,0]<140)&(rgb[:,:,1]<155)&(rgb[:,:,2]<175)
 reg=Y>np.polyval(row['top'],X)+1
 # Preserve original iris ink only inside a narrow, source-colored side/bottom search corridor.
 m=((a>127)|(near&ink&reg)).astype('uint8');cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);c=max(cs,key=cv2.contourArea);pts=cv2.approxPolyDP(c,.65,True)[:,0,:].astype(float);pts=curve(pts);im=Image.new('L',(a.shape[1]*8,a.shape[0]*8));ImageDraw.Draw(im).polygon([tuple(q*8+4) for q in pts],fill=255);out=np.zeros_like(old);out[y0:y1,x0:x1]=np.array(im.resize((a.shape[1],a.shape[0]),Image.Resampling.BOX));Image.fromarray(out).save(p);records.append({'state':state,'part':part,'crop':[int(x0),int(y0),int(x1),int(y1)],'arc_control_points_crop':pts[::32].tolist()})
(r/'reference/retained-iris-ink.json').write_text(json.dumps({'method':'source dark-ink detection within 5 px of semantic iris perimeter, excluding fixed top lash, then subpixel contour coverage','parts':records},indent=2))
