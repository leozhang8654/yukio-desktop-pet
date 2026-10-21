from pathlib import Path
import sys,json,hashlib
sys.path[:0]=['/Users/developer/.cache/yukio-sr/lib/python3.13/site-packages','/Users/developer/.cache/yukio-sam2-source']
import numpy as np,cv2,torch
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
r=Path(__file__).resolve().parents[1];ck='/Users/developer/.cache/yukio-sam2-models/sam2.1_hiera_tiny.pt';pr=SAM2ImagePredictor(build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml',ck,device='mps'));records=[]
with torch.inference_mode():
 for state,part in [('failed','hand-and-card'),('write_file','left-hand'),('verify','hand-and-probe')]:
  src=np.array(Image.open(next((r/'source').glob('*-'+state+'.png'))));mask=np.array(Image.open(r/'masks'/state/(part+'.png')));ys,xs=np.nonzero(mask);box=[int(xs.min())-18,int(ys.min())-18,int(xs.max())+19,int(ys.max())+19];x0,y0,x1,y1=box;rgb=src[y0:y1,x0:x1,:3];m=(mask[y0:y1,x0:x1]>127).astype('uint8');di=cv2.distanceTransform(m,cv2.DIST_L2,5);do=cv2.distanceTransform(1-m,cv2.DIST_L2,5);points=[];labs=[]
  for y in range(3,m.shape[0],16):
   for x in range(3,m.shape[1],16):
    if di[y,x]>7:points.append([x,y]);labs.append(1)
    elif 5<do[y,x]<15:points.append([x,y]);labs.append(0)
  pr.set_image(rgb);masks,scores,logits=pr.predict(point_coords=np.array(points,dtype=np.float32),point_labels=np.array(labs),box=np.array([15,15,m.shape[1]-15,m.shape[0]-15]),multimask_output=True)
  out=r/'experiments/sam-local'/state/part;out.mkdir(parents=True,exist_ok=True)
  for k,ma in enumerate(masks):
   full=np.zeros(mask.shape,np.uint8);full[y0:y1,x0:x1]=(ma>.5).astype('uint8')*255;Image.fromarray(full).save(out/f'mask-{k}.png');rgba=src.copy();rgba[:,:,3]=np.minimum(rgba[:,:,3],full);im=Image.fromarray(rgba).crop(box);bg=Image.new('RGBA',(im.width*4,im.height*2),'white');bg.alpha_composite(im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST));dark=Image.new('RGBA',(im.width*2,im.height*2),'#292934');dark.alpha_composite(im.resize(dark.size,Image.Resampling.NEAREST));bg.alpha_composite(dark,(im.width*2,0));bg.save(out/f'preview-{k}.png')
  rec={'state':state,'part':part,'crop':box,'points_crop_coordinates':points,'labels':labs,'scores':scores.tolist(),'checkpoint_sha256':hashlib.sha256(Path(ck).read_bytes()).hexdigest()};records.append(rec);print(state,scores,flush=True)
(r/'reference/sam-local-retry.json').write_text(json.dumps(records,indent=2))
