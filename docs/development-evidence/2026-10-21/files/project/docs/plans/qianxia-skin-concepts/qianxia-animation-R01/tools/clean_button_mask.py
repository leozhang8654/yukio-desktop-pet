from pathlib import Path
import cv2,numpy as np,json,hashlib
from PIL import Image
r=Path(__file__).resolve().parents[1];d=r/'rigs/question_for_user/pressing-hand';a=np.array(Image.open(d/'initial-candidate-mask.png'));n,l,s,c=cv2.connectedComponentsWithStats(a,8)
# Component at (805,777), 12x5 is the pink sleeve/button-side paint, not a finger.
assert s[2].tolist()==[805,777,12,5,41]
b=a.copy();b[l==2]=0
# No erosion, dilation, hole fill or blur. Preserve the complete primary hand selection.
out=d/'refinement-03';out.mkdir(exist_ok=True);Image.fromarray(b).save(out/'candidate-mask.png')
(out/'parameters.json').write_text(json.dumps({'source_mask_sha256':hashlib.sha256((d/'initial-candidate-mask.png').read_bytes()).hexdigest(),'edit':'remove visually identified extraneous pink fragment at x805..816,y777..781','removed_pixels':int(((a>0)&(b==0)).sum()),'added_pixels':0,'status':'candidate, boundary and motion checks still required'},indent=2))
