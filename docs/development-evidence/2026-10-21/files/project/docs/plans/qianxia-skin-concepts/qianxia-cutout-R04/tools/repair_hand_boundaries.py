from pathlib import Path
from PIL import Image
import numpy as np,json
r=Path(__file__).resolve().parents[1];prev=r.parent/'qianxia-cutout-R03';rec=[]
keys=['idle/touching-hand','failed/hand-and-card','verify/hand-and-probe','respond/hand-and-card','view_image/hand-and-stylus','write_file/left-hand','write_file/right-hand','question_for_user/pressing-hand'];arr={k:np.array(Image.open(prev/'masks'/(k+'.png'))) for k in keys}
def edge(key,box,side,knots,mode='replace',fade=0):
 a=arr[key];x0,y0,x1,y1=box;y,x=np.mgrid[y0:y1,x0:x1];v=x if side in ['top','bottom'] else y;b=np.interp(v,*np.array(knots).T);c=np.clip({'top':y+.5-b,'bottom':b-y+.5,'left':x+.5-b,'right':b-x+.5}[side],0,1)*255;old=a[y0:y1,x0:x1].copy()
 if mode=='min':c=np.minimum(c,old)
 if fade:
  lo,hi=(x0,x1) if side in ['top','bottom'] else (y0,y1);w=np.minimum(np.clip((v-lo+.5)/fade,0,1),np.clip((hi-.5-v)/fade,0,1));c=c*w+old*(1-w)
 a[y0:y1,x0:x1]=np.rint(c).astype('uint8');rec.append(dict(part=key,roi=box,side=side,knots=knots,mode=mode,fade=fade))
edge('failed/hand-and-card',(383,585,449,610),'top',[(383,603.87),(400,599.6),(425,593.325),(449,587.301)],fade=7)
edge('verify/hand-and-probe',(402,589,447,619),'top',[(402,612.066),(412,607.646),(435,597.48),(447,592.176)],fade=6)
edge('respond/hand-and-card',(296,715,323,748),'left',[(715,302),(719,303.06),(723,304.34),(727,305.82),(731,307.50),(735,309.40),(739,311.50),(743,313.816),(748,317.0)],fade=4)
edge('respond/hand-and-card',(389,720,432,734),'bottom',[(389,728.31),(432,721.43)],mode='min')
edge('write_file/right-hand',(738,758,760,791),'left',[(758,751),(762,749.824),(766,748.696),(770,747.616),(774,746.584),(778,745.6),(782,744.664),(786,743.776),(791,742.75)],fade=4)
edge('question_for_user/pressing-hand',(788,729,810,754),'right',[(729,793.0),(733,795.1),(737,796.8),(741,798.1),(745,799.1),(749,799.8),(754,800.15)],fade=3)
edge('view_image/hand-and-stylus',(435,746,465,779),'right',[(746,461.5),(748,461.2),(750,460.5),(752,459.5),(754,457.8),(756,456.5),(758,455),(760,453.1),(762,451.5),(764,450.3),(765,448.5),(766,446.5),(768,444),(770,443.5),(772,442.2),(774,441.1),(776,439.6),(778,437.2),(779,435.8)],fade=2)
edge('write_file/left-hand',(367,792,416,819),'bottom',[(367,807),(372,807.5),(376,806),(379,804.7),(382,808.2),(387,811),(391,812.0),(396,812),(401,810.3),(405,808.2),(407,807.0),(410,810),(414,812),(416,812)],fade=2)
edge('idle/touching-hand',(420,815,437,828),'bottom',[(420,817.0),(422,818.25),(424,819.1),(426,820.6),(428,821.2),(430,822.1),(433,822.5),(437,822.0)],mode='min')
# Explicit isolated hair remnants, outside instrument ink; no global erosion.
a=arr['verify/hand-and-probe'];s=np.array(Image.open(next((r/'source').glob('*-verify.png'))));x0,y0,x1,y1=376,632,390,651;c=s[y0:y1,x0:x1,:3].astype(float);R,G,B=c.transpose(2,0,1);green=(G>70)&(G>R-3)&(G>B+4);a[y0:y1,x0:x1][green]=0
for k,a in arr.items():Image.fromarray(a).save(r/'masks'/(k+'.png'))
(r/'reference/hand-boundary-repairs.json').write_text(json.dumps(rec,indent=2));print('modified',len(arr))
