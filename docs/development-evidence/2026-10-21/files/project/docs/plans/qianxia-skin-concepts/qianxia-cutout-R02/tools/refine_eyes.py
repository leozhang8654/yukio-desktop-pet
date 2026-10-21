from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,cv2,json
r=Path(__file__).resolve().parents[1];before=r.parent/'qianxia-cutout-R01';records=[]
def robustfit(x,y,degree):
 x=np.asarray(x);y=np.asarray(y);p=np.polyfit(x,y,degree)
 for _ in range(3):
  residual=np.abs(np.polyval(p,x)-y);keep=residual<max(1.1,np.quantile(residual,.8));p=np.polyfit(x[keep],y[keep],degree)
 return p
for f in sorted((before/'masks').glob('*/iris-*.png')):
 a=np.array(Image.open(f))>127;yy,xx=np.nonzero(a);x0,x1=xx.min(),xx.max();y0,y1=yy.min(),yy.max();w=x1-x0;h=y1-y0
 # Four semantic arcs are fitted separately. Glint rows are excluded from the iris side fit.
 xs=np.arange(x0+int(w*.13),x1-int(w*.1));tops=[np.nonzero(a[:,x])[0][0] for x in xs];tp=robustfit(xs,tops,2)
 ys=np.arange(y0+int(h*.2),y1-int(h*.12));ys=ys[(ys<y0+h*.28)|(ys>y0+h*.58)]
 ls=[np.nonzero(a[y])[0][0] for y in ys];lp=robustfit(ys,ls,2)
 ys2=np.arange(y0+int(h*.26),y1-int(h*.10));rs=[np.nonzero(a[y])[0][-1] for y in ys2];rp=robustfit(ys2,rs,2)
 xb=np.arange(x0+int(w*.30),x1-int(w*.27));bottoms=[np.nonzero(a[:,x])[0][-1] for x in xb];bp=robustfit(xb,bottoms,2)
 # Avoid polynomial extrapolation: bound within the observed eye extent, with half-pixel coverage.
 box=(int(x0)-8,int(y0)-4,int(x1)+6,int(y1)+5);scale=8
 py,px=np.indices(((box[3]-box[1])*scale,(box[2]-box[0])*scale));X=(px+.5)/scale+box[0];Y=(py+.5)/scale+box[1]
 mask=(Y>=np.polyval(tp,X)-.15)&(Y<=np.polyval(bp,X)+.35)&(X>=np.polyval(lp,Y)-.15)&(X<=np.polyval(rp,Y)+.35)
 mask &= (X>=x0-1)&(X<=x1+1)&(Y>=y0-1)&(Y<=y1+1)
 src=np.array(Image.open(next((r/'source').glob('*-'+f.parent.name+'.png'))))
 # The white oval glint crosses the left iris outline. Locate its original white center, then keep its visible oval.
 candidates=[]
 for y in range(int(y0+h*.24),int(y0+h*.57)):
  l=int(round(np.polyval(lp,y)));pix=src[y,l+2:l+8,:3];candidates.append((int(np.sum(np.min(pix,axis=1)>232)),y))
 peak=max(z[0] for z in candidates);bright=[y for score,y in candidates if score>=max(3,peak-1)]
 if bright:
  gy=(min(bright)+max(bright))/2;gl=float(np.polyval(lp,gy));rx=6.2;ry=(max(bright)-min(bright)+2.2)/2
  glint=((X-(gl+2.0))/rx)**2+((Y-gy)/ry)**2<=1;mask|=glint
 out=np.zeros(a.shape,np.uint8);tile=(mask.reshape((box[3]-box[1],scale,box[2]-box[0],scale)).mean((1,3))*255).round().astype('uint8');out[box[1]:box[3],box[0]:box[2]]=tile;out[src[:,:,3]==0]=0
 Image.fromarray(out).save(r/'masks'/f.parent.name/f.name);records.append({'state':f.parent.name,'part':f.stem,'bounds':[int(x0),int(y0),int(x1),int(y1)],'top':tp.tolist(),'left':lp.tolist(),'right':rp.tolist(),'bottom':bp.tolist(),'glint':{'center':[gl+2,gy],'radii':[rx,ry]}})
(r/'reference/eye-arc-refinement.json').write_text(json.dumps({'method':'source-referenced separate arc fitting with original white glint, 8x area coverage; no RGB repaint','parts':records},indent=2))
