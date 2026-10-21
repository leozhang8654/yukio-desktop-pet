from pathlib import Path
import sys,json,hashlib
sys.path[:0]=['/Users/developer/.cache/yukio-sr/lib/python3.13/site-packages','/Users/developer/.cache/yukio-sam2-source']
import torch,numpy as np,cv2
from PIL import Image,ImageDraw
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
r=Path(__file__).resolve().parents[1]
specs=json.loads((r/'prompts/sam-points.json').read_text())
extra={
'view_image/hand-and-stylus':([[491,714],[504,800],[378,755]],[[392,688],[492,681],[475,680]]),
'write_file/left-hand':([[481,786],[369,793],[429,804]],[[472,756],[478,767]]),
'write_file/right-hand':([[751,784],[810,801]],[[736,792],[741,787]]),
'respond/hand-and-card':([[320,669],[317,683],[400,748],[310,720]],[[294,734],[295,753],[512,748],[397,736]]),
'question_for_user/pressing-hand':([[783,785],[721,757]],[[810,779],[807,773]]),
'read_web/pointing-hand':([[331,676],[414,681]],[[341,650]])}
checkpoint='/Users/developer/.cache/yukio-sam2-models/sam2.1_hiera_tiny.pt'
predictor=SAM2ImagePredictor(build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml',checkpoint,device='mps'))
records=[]
with torch.inference_mode():
 for p in sorted((r/'source').glob('*.png')):
  state=p.stem.split('-',1)[1]
  if state in ('read_file','task_complete'):continue
  original=Image.open(p).convert('RGBA');a=np.array(original)
  for name,box,pos,neg in specs[state]:
   key=f'{state}/{name}';ep,en=extra.get(key,([],[]));pos=pos+ep;neg=neg+en
   crop=[max(0,box[0]-65),max(0,box[1]-65),min(a.shape[1],box[2]+65),min(a.shape[0],box[3]+65)]
   bg=Image.new('RGBA',original.size,'#909098');bg.alpha_composite(original)
   predictor.set_image(np.array(bg.crop(crop).convert('RGB')))
   origin=np.array(crop[:2]);masks,scores,logits=predictor.predict(point_coords=np.array(pos+neg,dtype=np.float32)-origin,point_labels=np.array([1]*len(pos)+[0]*len(neg)),box=np.array(box,dtype=np.float32)-np.tile(origin,2),multimask_output=True)
   out=r/'rigs'/state/name/'refinement-02';out.mkdir(exist_ok=True)
   k=int(np.argmax(scores));selected=np.zeros(a.shape[:2],np.uint8)
   for j,m in enumerate(masks):
    full=np.zeros(a.shape[:2],np.uint8);full[crop[1]:crop[3],crop[0]:crop[2]]=(m>0.5).astype(np.uint8)*255;full[a[:,:,3]==0]=0
    Image.fromarray(full).save(out/f'sam-option-{j}.png')
    if j==k:selected=full
   Image.fromarray(selected).save(out/'candidate-mask.png')
   tinted=bg.copy();t=Image.new('RGBA',original.size,(0,240,100,0));t.putalpha(Image.fromarray((selected>0).astype('uint8')*90));tinted.alpha_composite(t)
   for target,label in [(bg,'source'),(tinted,'overlay')]:target.crop(crop).resize(((crop[2]-crop[0])*2,(crop[3]-crop[1])*2),Image.Resampling.NEAREST).save(out/f'{label}-200.png')
   n,l,s,c=cv2.connectedComponentsWithStats(selected,8)
   rec={'state':state,'part':name,'crop':crop,'positive_points':pos,'negative_points':neg,'scores':scores.tolist(),'chosen':k,'components_xywh_area':s[1:].tolist(),'status':'candidate_requires_visual_review'}
   (out/'parameters.json').write_text(json.dumps(rec,indent=2));records.append(rec);print(key,s[1:].tolist(),flush=True)
(r/'review/sam-refinement-02.json').write_text(json.dumps(records,indent=2))
