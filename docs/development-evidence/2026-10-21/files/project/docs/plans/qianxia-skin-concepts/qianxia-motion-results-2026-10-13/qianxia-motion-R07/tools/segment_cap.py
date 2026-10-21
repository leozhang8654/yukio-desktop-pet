from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,'/Users/developer/.cache/yukio-sam2-source')
import torch,numpy as np,cv2
from PIL import Image
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
r=Path(__file__).resolve().parents[1]; im=Image.open(r/'inputs/source/11-question_for_user.png').convert('RGBA'); bg=Image.new('RGBA',im.size,'#888890');bg.alpha_composite(im)
ck=Path('/Users/developer/.cache/yukio-sam2-models/sam2.1_hiera_tiny.pt');m=build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml',str(ck),device='mps'); pred=SAM2ImagePredictor(m)
pts=[[800,805],[758,808],[800,785],[841,809],[800,829],[798,840],[732,820],[774,775],[820,773]];labels=[1,1,1,1,1,0,0,0,0]
with torch.inference_mode():
 pred.set_image(np.array(bg.convert('RGB'))); masks,scores,_=pred.predict(point_coords=np.array(pts),point_labels=np.array(labels),box=np.array([750,781,850,835]),multimask_output=True)
d=r/'rigs/question_for_user/cap-segmentation';d.mkdir(exist_ok=True)
for i,ma in enumerate(masks):
 ma=ma>0.5
 Image.fromarray(ma.astype('uint8')*255).save(d/f'option-{i}.png'); out=np.array(bg);out[ma,:3]=(out[ma,:3]*.6+np.array([0,255,100])*.4).astype('uint8');Image.fromarray(out).crop((735,765,865,850)).resize((780,510)).save(d/f'overlay-{i}.png')
(d/'sam.json').write_text(json.dumps({'checkpoint_sha256':hashlib.sha256(ck.read_bytes()).hexdigest(),'points':pts,'labels':labels,'box':[750,781,850,835],'scores':scores.tolist(),'selected':'pending visual'},indent=2));print(scores)
