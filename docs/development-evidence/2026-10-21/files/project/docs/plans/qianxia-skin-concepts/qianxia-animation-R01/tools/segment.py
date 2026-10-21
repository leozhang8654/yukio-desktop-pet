from pathlib import Path
import os,sys,json,hashlib,time
sys.path[:0]=['/Users/developer/.cache/yukio-sr/lib/python3.13/site-packages','/Users/developer/.cache/yukio-sam2-source']
import torch,numpy as np,cv2
from PIL import Image,ImageDraw
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
r=Path(__file__).resolve().parents[1]
# Boxes and labelled points in the unresized R02 source coordinate system.
specs={
'idle':[('touching-hand',[386,727,535,835],[[447,774],[496,751]],[[350,780],[564,764],[563,841]]),('orb',[516,713,620,814],[[565,765]],[[501,752],[569,843]])],
 'thinking':[('resting-hand',[516,790,635,876],[[566,831]],[[493,822],[642,829]])],
 'read_file':[('crossed-hands-visible',[523,788,654,834],[[577,814]],[[571,765],[580,854]])],
 'view_image':[('hand-and-stylus',[368,655,524,819],[[421,741],[472,756],[500,790]],[[338,765],[531,831],[529,694]])],
 'write_file':[('left-hand',[347,735,485,814],[[403,775]],[[330,765],[398,828]]),('right-hand',[733,741,856,821],[[792,781]],[[877,780],[799,834]])],
 'verify':[('hand-and-probe',[363,590,517,785],[[412,683],[474,680],[492,751]],[[345,725],[534,640],[524,794]])],
 'read_web':[('pointing-hand',[318,620,452,700],[[375,656],[402,677]],[[307,691],[466,698],[381,731]])],
 'default_work':[('trackball-hand',[344,735,462,820],[[391,777],[420,763]],[[328,771],[438,805],[443,837]])],
 'respond':[('hand-and-card',[295,582,543,782],[[403,669],[351,728]],[[303,809],[562,672],[420,756]])],
 'task_complete':[('resting-sleeves',[301,717,892,851],[[415,790],[715,790]],[[600,695],[600,858],[951,790]])],
 'question_for_user':[('pressing-hand',[710,715,811,798],[[751,752],[784,773]],[[701,781],[805,811],[848,744]])],
 'failed':[('hand-and-card',[329,582,527,763],[[435,651],[374,701]],[[294,765],[548,695],[414,780]])]
}
(r/'prompts/sam-points.json').write_text(json.dumps(specs,indent=2))
checkpoint=Path('/Users/developer/.cache/yukio-sam2-models/sam2.1_hiera_tiny.pt');device='mps' if torch.backends.mps.is_available() else 'cpu'
model=build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml',str(checkpoint),device=device);predictor=SAM2ImagePredictor(model)
report={'model':'SAM2.1 hiera tiny','checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'config':'configs/sam2.1/sam2.1_hiera_t.yaml','device':device,'torch':torch.__version__,'status':'initial selections only, not approved rigs','parts':[]}
with torch.inference_mode():
 for p in sorted((r/'source').glob('[0-9][0-9]-*.png')):
  state=p.stem.split('-',1)[1];image=Image.open(p).convert('RGBA');a=np.array(image);bg=Image.new('RGBA',image.size,'#909098');bg.alpha_composite(image);predictor.set_image(np.array(bg.convert('RGB')))
  for name,box,pos,neg in specs[state]:
   folder=r/'rigs'/state/name;folder.mkdir(parents=True,exist_ok=True)
   masks,scores,logits=predictor.predict(point_coords=np.array(pos+neg,dtype=np.float32),point_labels=np.array([1]*len(pos)+[0]*len(neg)),box=np.array(box,dtype=np.float32),multimask_output=True)
   k=int(np.argmax(scores));raw=masks[k]>0.5;visible=raw&(a[:,:,3]>0)
   for j,m in enumerate(masks):Image.fromarray((m>0.5).astype('uint8')*255).save(folder/f'sam-option-{j}.png')
   Image.fromarray(visible.astype('uint8')*255).save(folder/'initial-candidate-mask.png')
   n,labels,stats,_=cv2.connectedComponentsWithStats(visible.astype('uint8'),8)
   cropbox=(max(box[0]-35,0),max(box[1]-35,0),min(box[2]+35,a.shape[1]),min(box[3]+35,a.shape[0]))
   overlay=bg.copy();tint=Image.new('RGBA',image.size,(0,240,100,0));tint.putalpha(Image.fromarray(visible.astype('uint8')*90));overlay.alpha_composite(tint);od=ImageDraw.Draw(overlay);od.rectangle(box,outline='#ffe100',width=2)
   for point in pos:od.ellipse((point[0]-4,point[1]-4,point[0]+4,point[1]+4),fill='lime')
   for point in neg:od.ellipse((point[0]-4,point[1]-4,point[0]+4,point[1]+4),fill='red')
   overlay.crop(cropbox).resize(((cropbox[2]-cropbox[0])*2,(cropbox[3]-cropbox[1])*2),Image.Resampling.NEAREST).save(folder/'initial-overlay-200.png')
   rec={'state':state,'part':name,'input_file':str(p.relative_to(r)),'input_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'box':box,'positive_points':pos,'negative_points':neg,'sam_scores':scores.tolist(),'chosen_option':k,'selected_pixels':int(visible.sum()),'removed_fully_transparent_pixels':int((raw&~visible).sum()),'components':n-1,'component_areas':stats[1:,cv2.CC_STAT_AREA].tolist(),'visual_review':'pending','status':'initial_candidate'};report['parts'].append(rec);(folder/'segmentation.json').write_text(json.dumps(rec,indent=2));print(state,name,'score',scores[k],'components',n-1,flush=True)
  (r/'review/sam-initial-report.json').write_text(json.dumps(report,indent=2))
