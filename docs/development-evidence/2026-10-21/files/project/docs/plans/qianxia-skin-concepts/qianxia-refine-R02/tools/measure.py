from pathlib import Path
import cv2,numpy as np,json
r=Path(__file__).resolve().parents[1];before=r.parent/'qianxia-refine-R01/candidates'
base=cv2.imread(str(before/'10-task_complete.png'),cv2.IMREAD_UNCHANGED)
# Individually identifiable stationary furniture parts; no face, sleeves or device changes.
regions={'front_light':[290,895,909,925],'left_desk_leg':[131,990,229,1228],'right_desk_leg':[970,990,1080,1228],'boxes':[820,1037,962,1217],'left_chair_leg':[394,1000,466,1169],'rabbit_base':[116,800,270,852]}
features=lambda a:cv2.Canny(cv2.cvtColor(a[:,:,:3],cv2.COLOR_BGR2GRAY),60,160)
b=features(base);records=[]
for p in sorted(before.glob('[0-9][0-9]-*.png')):
 if p.name.startswith('10-'):continue
 a=cv2.imread(str(p),cv2.IMREAD_UNCHANGED);f=features(a);matches={}
 for name,(x1,y1,x2,y2) in regions.items():
  xa=max(0,x1-15);ya=max(0,y1-5);xb=min(a.shape[1],x2+15);yb=min(a.shape[0],y2+60)
  result=cv2.matchTemplate(f[ya:yb,xa:xb],b[y1:y2,x1:x2],cv2.TM_CCOEFF_NORMED)
  _,score,_,pos=cv2.minMaxLoc(result);matches[name]={'dx':pos[0]+xa-x1,'dy':pos[1]+ya-y1,'edge_match_score':round(score,4)}
 records.append({'state':p.stem,'matches':matches})
summary={k:{'median_dx':float(np.median([t['matches'][k]['dx'] for t in records])),'median_dy':float(np.median([t['matches'][k]['dy'] for t in records])),'dy_range':[min(t['matches'][k]['dy'] for t in records),max(t['matches'][k]['dy'] for t in records)]} for k in regions}
out={'method':'Canny edges + normalized template matching; source-complete patches matched independently to 11 states; not pixel identity','source_regions':regions,'records':records,'summary':summary}
(r/'review/scene-landmarks.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
