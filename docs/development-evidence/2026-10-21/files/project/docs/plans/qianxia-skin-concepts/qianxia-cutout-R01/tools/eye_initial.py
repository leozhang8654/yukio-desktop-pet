from pathlib import Path
import sys,json,hashlib
sys.path[:0]=['/Users/developer/.cache/yukio-sr/lib/python3.13/site-packages','/Users/developer/.cache/yukio-sam2-source']
import torch,numpy as np,cv2
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
r=Path(__file__).resolve().parents[1];predictor=SAM2ImagePredictor(build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml','/Users/developer/.cache/yukio-sam2-models/sam2.1_hiera_tiny.pt',device='mps'));records=[]
with torch.inference_mode():
 for p in sorted((r/'source').glob('*.png')):
  state=p.stem.split('-',1)[1]
  if state=='task_complete':continue
  im=Image.open(p).convert('RGBA');a=np.array(im);bg=Image.new('RGBA',im.size,'#909098');bg.alpha_composite(im);predictor.set_image(np.array(bg.convert('RGB')))
  for side,(x0,y0,x1,y1) in [('left',(400,493,526,584)),('right',(582,507,716,594))]:
   b=a[y0:y1,x0:x1,:3].astype(float);teal=((b[:,:,1]>b[:,:,0]*1.3)&(b[:,:,2]>b[:,:,0]*1.2)&(b[:,:,1]>75)).astype('uint8');n,l,s,c=cv2.connectedComponentsWithStats(teal,8);k=1+np.argmax(s[1:,4]);xx,yy,ww,hh,area=s[k];cx,cy=c[k]+[x0,y0]
   box=[int(x0+xx-9),int(y0+yy-5),int(x0+xx+ww+8),int(y0+yy+hh+24)];pos=[[cx,cy],[cx,cy+16]];neg=[[box[0]-5,cy+10],[box[2]+6,cy+10],[cx,box[1]-8],[cx,box[3]+6]]
   masks,scores,_=predictor.predict(point_coords=np.array(pos+neg,dtype=np.float32),point_labels=np.array([1,1,0,0,0,0]),box=np.array(box,dtype=np.float32),multimask_output=True)
   d=r/'reference/eye-sam'/state/side;d.mkdir(parents=True,exist_ok=True)
   for j,m in enumerate(masks):Image.fromarray((m>0.5).astype('uint8')*255).save(d/f'option-{j}.png')
   chosen=int(np.argmax(scores));out=r/'masks'/state;out.mkdir(exist_ok=True);Image.fromarray((masks[chosen]>.5).astype('uint8')*255).save(out/f'iris-{side}.png')
   rec={'state':state,'side':side,'box':box,'positive':pos,'negative':neg,'scores':scores.tolist(),'chosen':chosen};records.append(rec);print(state,side,box,flush=True)
(r/'reference/eye-sam-parameters.json').write_text(json.dumps(records,indent=2))
