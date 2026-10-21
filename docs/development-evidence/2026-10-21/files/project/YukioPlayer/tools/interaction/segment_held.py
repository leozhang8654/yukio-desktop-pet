"""Reproducible SAM 2.1 initial selections. Dependencies/model are external."""
import argparse, hashlib, json, subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor

p=argparse.ArgumentParser(); p.add_argument('--checkpoint',required=True); p.add_argument('--out',type=Path,required=True); args=p.parse_args()
args.out.mkdir(parents=True,exist_ok=False)
source=Path(__file__).resolve().parents[3]/'sources/interaction-rig/source.png'
im=np.array(Image.open(source).convert('RGBA')); rgb=(im[:,:,:3]*(im[:,:,3:4]/255)+245*(1-im[:,:,3:4]/255)).astype('uint8')
prompts={
 'left-leg':{'points':[[181,324],[177,366],[167,402],[185,291],[213,352],[143,280]],'labels':[1,1,1,1,0,0],'box':[149,277,204,425]},
 'right-leg':{'points':[[213,340],[224,397],[223,437],[214,306],[177,358],[238,270]],'labels':[1,1,1,1,0,0],'box':[197,284,246,463]},
 'coat-left':{'points':[[140,278],[127,305],[166,260],[177,333]],'labels':[1,1,0,0],'box':[111,218,163,328]},
 'coat-right':{'points':[[255,275],[266,301],[222,274],[223,330]],'labels':[1,1,0,0],'box':[232,213,285,328]}}
model=build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml',args.checkpoint,device='cpu')
predictor=SAM2ImagePredictor(model)
with torch.inference_mode():
 predictor.set_image(rgb)
 for name,pr in prompts.items():
  masks,scores,_=predictor.predict(point_coords=np.array(pr['points']),point_labels=np.array(pr['labels']),box=np.array(pr['box']),multimask_output=True)
  for i,m in enumerate(masks): Image.fromarray(m.astype('uint8')*255).save(args.out/f'{name}-sam-{i}.png')
  pr['scores']=[float(s) for s in scores]; pr['candidate']=int(np.argmax(scores))
  Image.fromarray(masks[pr['candidate']].astype('uint8')*255).save(args.out/f'{name}-raw.png')
record={'model':'SAM 2.1 Hiera tiny','config':'configs/sam2.1/sam2.1_hiera_t.yaml','device':'cpu','torch':torch.__version__,'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'checkpointSha256':hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest(),'coordinateSystem':'384x480 source pixels, top-left','prompts':prompts}
(args.out/'prompts.json').write_text(json.dumps(record,indent=2))
print(args.out)
