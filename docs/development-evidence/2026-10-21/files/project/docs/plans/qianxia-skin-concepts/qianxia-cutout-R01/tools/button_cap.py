from pathlib import Path
import sys,json
sys.path[:0]=['/Users/developer/.cache/yukio-sr/lib/python3.13/site-packages','/Users/developer/.cache/yukio-sam2-source']
import numpy as np,torch
from PIL import Image,ImageDraw
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
r=Path(__file__).resolve().parents[1];im=Image.open(r/'source/11-question_for_user.png').convert('RGBA');bg=Image.new('RGBA',im.size,'#909098');bg.alpha_composite(im)
pred=SAM2ImagePredictor(build_sam2('configs/sam2.1/sam2.1_hiera_t.yaml','/Users/developer/.cache/yukio-sam2-models/sam2.1_hiera_tiny.pt',device='mps'))
with torch.inference_mode():
 pred.set_image(np.array(bg.convert('RGB')));m,s,_=pred.predict(point_coords=np.array([[800,805],[815,818],[784,778],[795,839]]),point_labels=np.array([1,1,0,0]),box=np.array([757,782,846,835]),multimask_output=True)
d=r/'reference/button-cap-sam';d.mkdir(exist_ok=True)
for i,a in enumerate(m):Image.fromarray((a>.5).astype('uint8')*255).save(d/f'option-{i}.png')
pts=[(760,800),(765,794),(773,789),(779,787),(784,790),(789,789),(792,785),(803,784),(816,785),(829,789),(837,795),(841,801),(842,809),(842,818),(836,823),(826,829),(814,832),(799,833),(784,832),(772,828),(763,823),(759,817),(759,808)]
box=(750,775,850,840);a=Image.new('L',(800,520));ImageDraw.Draw(a).polygon([((x-750)*8,(y-775)*8) for x,y in pts],fill=255);full=Image.new('L',im.size);full.paste(a.resize((100,65),Image.Resampling.BOX),box[:2]);full.save(r/'masks/question_for_user/button-cap.png')
(d/'parameters.json').write_text(json.dumps({'box':[757,782,846,835],'positive':[[800,805],[815,818]],'negative':[[784,778],[795,839]],'scores':s.tolist(),'refined_contour':pts,'scope':'visible pink cap and its rim only; occluded cap behind finger requires later clean plate'},indent=2))
