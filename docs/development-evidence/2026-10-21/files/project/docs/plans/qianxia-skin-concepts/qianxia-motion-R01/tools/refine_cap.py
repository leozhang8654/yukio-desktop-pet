from pathlib import Path
import numpy as np,cv2,json
from PIL import Image
r=Path(__file__).resolve().parents[1];p=r/'rigs/question_for_user';src=np.array(Image.open(r/'inputs/source/11-question_for_user.png'));h,w=src.shape[:2]
# Measured outer ink boundary, source coordinates. SAM options retain colour but omit upper ink.
segments=[[(750.7,807),(749,799),(756,791),(770,785)],[(770,785),(782,780.4),(796,780),(806,780.5)],[(806,780.5),(826,781),(844,789),(847.5,800)],[(847.5,800),(849,808),(849,816),(847,822)],[(847,822),(837,833),(814,836),(797,835)],[(797,835),(775,834),(756,829),(751,821)],[(751,821),(750,818),(750,812),(750.7,807)]]
pts=[]
for seg in segments:
 a,b,c,d=np.array(seg)
 for t in np.linspace(0,1,50):pts.append((1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d)
s=8;box=(745,775,855,840);m=np.zeros(((box[3]-box[1])*s,(box[2]-box[0])*s),'uint8');poly=(np.array(pts)-box[:2])*s;cv2.fillPoly(m,[np.round(poly).astype('int32')],255);small=cv2.resize(m,(box[2]-box[0],box[3]-box[1]),interpolation=cv2.INTER_AREA);mask=np.zeros((h,w),'uint8');mask[box[1]:box[3],box[0]:box[2]]=small
Image.fromarray(mask).save(p/'button-cap-motion-mask.png')
a=src.copy();a[mask>0,:3]=(a[mask>0,:3]*.6+[0,100,40]).clip(0,255);Image.fromarray(a).crop((735,765,865,850)).resize((780,510)).save(r/'review/cap-refined-overlay.png')
(p/'cap-segmentation/refinement.json').write_text(json.dumps({'reason':'SAM and R08 visible colour masks omit outer ink needed for motion','curve_segments_source_coords':segments,'sam_initial':'option-2.png','new_mask':'../button-cap-motion-mask.png'},indent=2))
