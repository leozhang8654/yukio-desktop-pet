from pathlib import Path
import cv2,numpy as np,json
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[1];before=r.parent/'qianxia-cutout-R01'
for state,part in [('write_file','left-hand'),('failed','hand-and-card'),('verify','hand-and-probe'),('respond','hand-and-card')]:
 src=np.array(Image.open(next((r/'source').glob('*-'+state+'.png'))).convert('RGBA'));raw=np.array(Image.open(before/'masks'/state/(part+'.png')));b=(raw>127).astype('uint8');ys,xs=np.nonzero(b);x0=max(0,int(xs.min())-25);x1=min(src.shape[1],int(xs.max())+26);y0=max(0,int(ys.min())-25);y1=min(src.shape[0],int(ys.max())+26);a=src[y0:y1,x0:x1,:3];inside=b[y0:y1,x0:x1];di=cv2.distanceTransform(inside,cv2.DIST_L2,5);do=cv2.distanceTransform(1-inside,cv2.DIST_L2,5)
 trimap=np.where(inside,cv2.GC_PR_FGD,cv2.GC_PR_BGD).astype('uint8');trimap[di>7]=cv2.GC_FGD;trimap[do>7]=cv2.GC_BGD
 cv2.grabCut(a,trimap,None,np.zeros((1,65),np.float64),np.zeros((1,65),np.float64),5,cv2.GC_INIT_WITH_MASK)
 m=np.isin(trimap,[cv2.GC_FGD,cv2.GC_PR_FGD]).astype('uint8')*255;full=np.zeros_like(raw);full[y0:y1,x0:x1]=m;out=r/'experiments'/state/part;out.mkdir(parents=True,exist_ok=True);Image.fromarray(full).save(out/'graphcut-mask.png')
 rgba=src.copy();rgba[:,:,3]=np.minimum(rgba[:,:,3],full);cut=Image.fromarray(rgba).crop((x0,y0,x1,y1));canvas=Image.new('RGBA',(cut.width*4,cut.height*2),'white');canvas.alpha_composite(cut.resize((cut.width*2,cut.height*2),Image.Resampling.NEAREST));bg=Image.new('RGBA',(cut.width*2,cut.height*2),'#333344');bg.alpha_composite(cut.resize(bg.size,Image.Resampling.NEAREST));canvas.alpha_composite(bg,(cut.width*2,0));canvas.save(out/'cutout-200.png')
 print(state,part,'changed',int(np.sum(full!=raw)))
