from PIL import Image,ImageDraw,ImageFilter
from pathlib import Path
import numpy as np,json
r=Path(__file__).resolve().parents[1]
src=Image.open(r/'source/11-question_for_user.png').convert('RGBA')
raw=Image.open(r/'candidates/experiments/11-contact-raw.png').convert('RGBA'); print('raw',raw.size)
# The requested square context is 512 px. Normalize only the generated patch, never the source.
patch=raw.resize((512,512),Image.Resampling.LANCZOS)
# Limit the patch to the distal pointing finger and its contact; place transition inside the original finger/sleeve.
m=Image.new('L',src.size,0);d=ImageDraw.Draw(m)
d.polygon([(750,742),(771,738),(792,766),(796,781),(793,788),(784,792),(774,785),(763,769),(754,755)],fill=255)
m=m.filter(ImageFilter.GaussianBlur(1))
# Keep generated finger pixels only. Follow its contour rather than cutting a
# rectangle across the shifted generated button rim (the cause of the old step).
scale=8
cap=Image.new('L',(src.width*scale,src.height*scale),0)
cd=ImageDraw.Draw(cap)
contour=[(0,0),(src.width,0),(src.width,770),(791,770),
         (791,776),(791,783),(790,786),(788,788),(785,790),
         (780,792),(775,791),(770,790),(0,790)]
cd.polygon([(round(x*scale),round(y*scale)) for x,y in contour],fill=255)
cap=cap.resize(src.size,Image.Resampling.LANCZOS)
ma=np.minimum(np.array(m),np.array(cap))
ma[775:,793:]=0 # protected original rim, beyond the finger contour
m=Image.fromarray(ma)
m.save(r/'edit-regions/11-contact-mask.png')
full=src.copy();full.paste(patch,(577,526));out=Image.composite(full,src,m);out.putalpha(src.getchannel('A'));out.save(r/'candidates/11-question_for_user.png')
a=np.array(src);b=np.array(out);change=np.any(a!=b,axis=2);mask=np.array(m)>0
ys,xs=np.where(change)
report={'raw_size':list(raw.size),'patch_registration_offset':[-3,-4],'patch_size':[512,512],'changed_pixels':int(change.sum()),'changed_bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)],'outside_mask_rgba_changes':int((change&~mask).sum()),'protected_button_rim_roi':[793,775,855,833],'protected_button_rim_changed_pixels':int(change[775:833,793:855].sum()),'mask_nonzero_bbox':list(m.getbbox()),'method':'image_gen crop candidate; patch resized to input crop dimensions; local mask composite; source outside mask copied exactly'}
(r/'review/11-pixel-check.json').write_text(json.dumps(report,indent=2));print(report)
# Focused before/after, 4x nearest-neighbor for seam inspection.
box=(730,720,830,840)
sheet=Image.new('RGB',(800,480),'#35353d')
for i,im in enumerate([src,out]):
 c=im.crop(box);bg=Image.new('RGBA',c.size,'#35353d');bg.alpha_composite(c);sheet.paste(bg.convert('RGB').resize((400,480),Image.Resampling.NEAREST),(i*400,0))
sheet.save(r/'review/11-contact-before-after-400.png')
