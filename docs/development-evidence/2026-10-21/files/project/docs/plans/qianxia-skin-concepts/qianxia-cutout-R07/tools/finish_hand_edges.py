from pathlib import Path
from PIL import Image
import numpy as np,cv2,json
r=Path(__file__).resolve().parents[1];records=[]
for state,part,boxes in [('failed','hand-and-card',[(346,591,425,644)]),('verify','hand-and-probe',[(379,602,425,648)])]:
 p=r/'masks'/state/(part+'.png');m=np.array(Image.open(p));src=np.array(Image.open(next((r/'source').glob('*-'+state+'.png')))).astype(float);before=m.copy()
 for x0,y0,x1,y1 in boxes:
  R,G,B=src[y0:y1,x0:x1,:3].transpose(2,0,1);green=(G-R>7)&(G-B>4);v=m[y0:y1,x0:x1];v[green]=0
 if state=='failed':m[590,422:425]=0 # reviewed external jaw-colored detached fragment
 else:
  original=np.array(Image.open(r.parent/'qianxia-cutout-R01/masks/verify/hand-and-probe.png'))
  m[732:742,474:516]=np.maximum(m[732:742,474:516],original[732:742,474:516])
 Image.fromarray(m).save(p);records.append({'state':state,'part':part,'changed':int(np.sum(m!=before))})
p=r/'masks/write_file/left-hand.png';m=np.array(Image.open(p));a=np.array(Image.open(next((r/'source').glob('*-write_file.png')))).astype(float);before=m.copy()
for x0,y0,x1,y1 in [(400,798,405,810),(409,810,415,816)]:
 R,G,B=a[y0:y1,x0:x1,:3].transpose(2,0,1);pink=(B-G>7)&(R-G>25)&(R>95);v=m[y0:y1,x0:x1];v[pink]=0
m[804,402]=0 # opens the same visible inter-finger background notch, no fill of source keyboard color
Image.fromarray(m).save(p);records.append({'state':'write_file','part':'left-hand','changed':int(np.sum(m!=before))})
p=r/'masks/question_for_user/pressing-hand.png';m=np.array(Image.open(p));src=np.array(Image.open(next((r/'source').glob('*-question_for_user.png')))).astype(float);before=m.copy();di=cv2.distanceTransform((m>127).astype('uint8'),cv2.DIST_L2,5);x0,y0,x1,y1=788,733,809,777;R,G,B=src[y0:y1,x0:x1,:3].transpose(2,0,1);edge=di[y0:y1,x0:x1]<2.5;light=(G>70)&(B>70)&(np.abs(R-G)<45);limit=np.clip((130-np.maximum(G,B))/55,0,1)*255;v=m[y0:y1,x0:x1];sel=edge&light;v[sel]=np.minimum(v[sel],np.round(limit[sel]).astype('uint8'));Image.fromarray(m).save(p);records.append({'state':'question_for_user','part':'pressing-hand','changed':int(np.sum(m!=before))})
(r/'reference/hand-edge-finish.json').write_text(json.dumps(records,indent=2));print(records)
