from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json
r=Path(__file__).resolve().parents[1];old=r.parent/'qianxia-cutout-R01'
def curve(points,tension=.38):
 p=np.asarray(points,float);out=[]
 for i in range(len(p)):
  a,b,c,d=p[(i-1)%len(p)],p[i],p[(i+1)%len(p)],p[(i+2)%len(p)];t=np.linspace(0,1,max(12,int(np.linalg.norm(c-b)*6)),endpoint=False)[:,None]
  out.extend((2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*(c-a)*tension+(-2*t**3+3*t*t)*c+(t**3-t*t)*(d-b)*tension)
 return np.array(out)
def polygon(pts,size):
 p=curve(pts);lo=np.floor(p.min(0)-2).astype(int);hi=np.ceil(p.max(0)+3).astype(int);m=Image.new('L',tuple((hi-lo)*8));ImageDraw.Draw(m).polygon([tuple(x) for x in ((p-lo)*8)],fill=255);full=Image.new('L',size);full.paste(m.resize(tuple(hi-lo),Image.Resampling.BOX),tuple(lo));return np.array(full)
regions={
'idle/touching-hand':[('pink',(419,809,439,830))],
'failed/hand-and-card':[('green',(346,591,415,644)),('pink',(326,677,376,761)),('pink',(398,730,414,761))],
'respond/hand-and-card':[('pink',(300,720,403,781))],
'read_web/pointing-hand':[('pink',(406,630,437,667))],
'verify/hand-and-probe':[('green',(379,602,424,648))],
'view_image/hand-and-stylus':[('pink',(437,746,465,778))],
'write_file/left-hand':[('pink',(367,792,416,820))],
'write_file/right-hand':[('pink',(735,771,759,807))],
'question_for_user/pressing-hand':[('cyan',(788,733,809,777))]
}
records=[]
for key,rs in regions.items():
 state,name=key.split('/');src=Image.open(next((r/'source').glob('*-'+state+'.png')));a=np.array(src).astype(float);m=np.array(Image.open(old/'masks'/state/(name+'.png')))
 if state=='failed':
  # Replace only the missed wrist arc; original visible dark stroke continues below the R01 crop.
  pts=[(382,725),(406,726),(418,725),(416,731),(410,736),(409,740),(410,745),(407,751),(400,756),(388,758),(376,756),(366,752),(363,742)]
  patch=polygon(pts,src.size);m[730:761,380:414]=patch[730:761,380:414]
 if state=='verify':
  pts=[(469,730),(493,725),(501,732),(503,745),(505,760),(506,771),(504,778),(501,780),(498,777),(494,769),(490,758),(484,747),(479,738)]
  patch=polygon(pts,src.size);m[738:786,474:516]=patch[738:786,474:516]
 for kind,box in rs:
  x0,y0,x1,y1=box;R,G,B=a[y0:y1,x0:x1,:3].transpose(2,0,1)
  if kind=='pink':pollution=np.clip((B-G-6)/14,0,1)*np.clip((R-G-14)/35,0,1)
  elif kind=='green':pollution=np.clip((G-R-3)/13,0,1)*np.clip((G-B-1)/12,0,1)
  else:pollution=np.clip((B-R-5)/20,0,1)*np.clip((G-R-1)/13,0,1)*np.clip((np.maximum(G,B)-45)/70,0,1)
  m[y0:y1,x0:x1]=(m[y0:y1,x0:x1].astype(float)*(1-pollution)).round().astype('uint8')
 Image.fromarray(m).save(r/'masks'/state/(name+'.png'));records.append({'part':key,'regions':rs,'wrist_retrace':state=='failed','tip_retrace':state=='verify'})
(r/'reference/local-hand-repairs.json').write_text(json.dumps({'method':'bounded adjacent-color exclusion on independently identified regions; two individually traced missing contours; source RGB unchanged','parts':records},indent=2))
