from pathlib import Path
from PIL import Image,ImageDraw
import json,numpy as np,cv2,heapq,shutil
r=Path(__file__).resolve().parents[1];records=json.loads((r/'reference/manual-contours.json').read_text());out=r/'reference/manual-v1';out.mkdir(exist_ok=True)
# Guided refinement searches ONLY a narrow corridor around each reviewed exterior stroke.
# It follows original dark ink; it does not alter source art or globally erode/dilate masks.
for key,pts in records['contours'].items():
 state,name=key.split('/');p=r/'masks'/state/(name+'.png');shutil.copy2(p,out/(state+'-'+name+'.png'));a=np.array(Image.open(next((r/'source').glob('*-'+state+'.png'))).convert('RGBA'));lum=a[:,:,:3].mean(2)/255
 fixed=[]
 for x,y in pts:
  opts=[(float(lum[yy,xx])*8+((xx-x)**2+(yy-y)**2)*.12,xx,yy) for yy in range(y-4,y+5) for xx in range(x-4,x+5) if a[yy,xx,3]>0]
  _,x,y=min(opts);fixed.append((x,y))
 path=[]
 for start,end in zip(fixed,fixed[1:]+fixed[:1]):
  x0=min(start[0],end[0])-5;x1=max(start[0],end[0])+6;y0=min(start[1],end[1])-5;y1=max(start[1],end[1])+6
  v=np.array(end)-start;den=max(1,float(v@v));q=[(0,start)];dist={start:0};prev={}
  while q:
   cost,u=heapq.heappop(q)
   if u==end:break
   if cost!=dist[u]:continue
   for dx,dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
    t=(u[0]+dx,u[1]+dy);x,y=t
    if not(x0<=x<x1 and y0<=y<y1):continue
    delta=np.array(t)-start;proj=np.clip(float(delta@v)/den,0,1);gap=float(np.linalg.norm(delta-v*proj))
    if gap>5:continue
    score=cost+(1 if dx*dy==0 else 1.414)*(1+20*float(lum[y,x])**2+gap*.08)
    if score<dist.get(t,1e99):dist[t]=score;prev[t]=u;heapq.heappush(q,(score,t))
  line=[end]
  while line[-1]!=start:line.append(prev[line[-1]])
  path.extend(reversed(line))
 contour=np.array(path,dtype='int32').reshape(-1,1,2);simp=cv2.approxPolyDP(contour,.4,True).reshape(-1,2).tolist()
 minx,miny=np.min(contour.reshape(-1,2),axis=0)-2;maxx,maxy=np.max(contour.reshape(-1,2),axis=0)+3
 m=Image.new('L',((maxx-minx)*4,(maxy-miny)*4));ImageDraw.Draw(m).polygon([((x-minx)*4,(y-miny)*4) for x,y in simp],fill=255);full=Image.new('L',(a.shape[1],a.shape[0]));full.paste(m.resize((maxx-minx,maxy-miny),Image.Resampling.BOX),(int(minx),int(miny)));raw=np.array(full);raw[a[:,:,3]==0]=0;Image.fromarray(raw).save(p)
 records['contours'][key]=simp
(r/'reference/refined-ink-contours.json').write_text(json.dumps(records,indent=2))
# Five enclosed missing pixels sit in the white iris highlight, which belongs to the moving iris layer.
p=r/'masks/question_for_user/iris-left.png';raw=np.array(Image.open(p));c,_=cv2.findContours((raw>0).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);fill=np.zeros_like(raw);cv2.drawContours(fill,c,-1,255,cv2.FILLED);ys,xs=np.nonzero((fill>0)&(raw==0));assert len(xs)==5
shutil.copy2(p,r/'reference/question-iris-before-hole-fix.png');raw[ys,xs]=255;Image.fromarray(raw).save(p);(r/'reference/iris-highlight-fix.json').write_text(json.dumps({'state':'question_for_user','part':'iris-left','pixels_xy':list(zip(xs.tolist(),ys.tolist())),'reason':'5 enclosed omitted white highlight pixels; highlight must move with iris'},indent=2))
