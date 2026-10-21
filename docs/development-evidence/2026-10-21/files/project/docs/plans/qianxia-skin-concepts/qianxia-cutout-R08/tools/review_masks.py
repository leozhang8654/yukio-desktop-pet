from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np,cv2,json,hashlib,importlib.util
r=Path(__file__).resolve().parents[1];mod=importlib.util.spec_from_file_location('maskqa','/Users/developer/.codex/skills/cutout-animation-qa/scripts/check_masks.py');qa=importlib.util.module_from_spec(mod);mod.loader.exec_module(qa)
records=[];thumbs=[];eyeimgs=[]
for p in sorted((r/'masks').glob('*/*.png')):
 state=p.parent.name;part=p.stem;src=next((r/'source').glob('*-'+state+'.png'));im=Image.open(src).convert('RGBA');a=np.array(im);mask=np.array(Image.open(p));report,contours=qa.inspect(a,mask,1,0);bbox=report['bbox'];report.update(state=state,part=part,source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),mask_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),visual_review='pending',user_approval='pending');
 # Detect partially transparent internal seams as well as alpha=0 holes.
 n,labels,stats,_=cv2.connectedComponentsWithStats((mask<255).astype('uint8'),8)
 enclosed=[]
 for x,y,w,h,area in stats[1:]:
  if x>0 and y>0 and x+w<mask.shape[1] and y+h<mask.shape[0]:enclosed.append({'bbox':[int(x),int(y),int(x+w),int(y+h)],'pixels':int(area)})
 report['enclosed_nonopaque_mask_components']=enclosed
 report['passed']=report['passed'] and not enclosed
 records.append(report)
 if bbox is None:continue
 x0,y0,x1,y1=bbox;box=(max(0,x0-12),max(0,y0-12),min(im.width,x1+12),min(im.height,y1+12));cw=box[2]-box[0];ch=box[3]-box[1]
 cut=a.copy();cut[:,:,3]=((a[:,:,3].astype(np.uint16)*mask.astype(np.uint16)+127)//255).astype('uint8');out=r/'parts'/state;out.mkdir(exist_ok=True);Image.fromarray(cut).save(out/(part+'.png'))
 d=r/'review'/state/part;d.mkdir(parents=True,exist_ok=True);im.crop(box).save(d/'source-100.png')
 yy,xx=np.indices((ch,cw));check=np.repeat(np.where(((xx//12+yy//12)%2)[...,None],220,245).astype('uint8'),3,2);sheet=Image.new('RGB',(cw*4,ch*4+48),'#555555');draw=ImageDraw.Draw(sheet)
 for i,(name,color) in enumerate([('checker',None),('black','#000000'),('white','#ffffff'),('magenta','#ff00ff')]):
  bg=Image.fromarray(check).convert('RGBA') if color is None else Image.new('RGBA',(cw,ch),color);bg.alpha_composite(Image.fromarray(cut).crop(box));x=(i%2)*cw*2;y=(i//2)*(ch*2+24);draw.text((x+3,y+4),name,fill='white');sheet.paste(bg.convert('RGB').resize((cw*2,ch*2),Image.Resampling.NEAREST),(x,y+24))
 sheet.save(d/'four-backgrounds-200.png')
 bg=Image.new('RGBA',im.size,'#888890');bg.alpha_composite(im);tint=Image.new('RGBA',im.size,(0,230,100,0));tint.putalpha(Image.fromarray(((mask.astype(float)/255)*100).astype('uint8')));bg.alpha_composite(tint);bg.crop(box).resize((cw*2,ch*2),Image.Resampling.NEAREST).save(d/'overlay-200.png')
 plain=np.array(im);cv2.drawContours(plain,contours,-1,(255,70,0,255),1);Image.fromarray(plain).crop(box).resize((cw*2,ch*2),Image.Resampling.NEAREST).save(d/'contour-200.png')
 card=Image.new('RGB',(400,280),'#dedee3');di=ImageDraw.Draw(card);di.text((5,5),state+' / '+part,fill='black');crop=Image.fromarray(cut).crop(box);crop.thumbnail((186,246))
 for i,col in enumerate(['#ffffff','#262633']):
  bg=Image.new('RGBA',(194,252),col);bg.alpha_composite(crop,((194-crop.width)//2,(252-crop.height)//2));card.paste(bg.convert('RGB'),(i*200+3,25))
 (eyeimgs if part.startswith('iris') else thumbs).append(card)
for name,items in [('hands',thumbs),('eyes',eyeimgs)]:
 if not items:continue
 sheet=Image.new('RGB',(400*3,280*((len(items)+2)//3)),'#dedee3')
 for i,im in enumerate(items):sheet.paste(im,((i%3)*400,(i//3)*280))
 sheet.save(r/'review'/(name+'-contact-sheet.png'))
(r/'review/mask-report.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));print('masks',len(records),'structural passed',sum(x['passed'] for x in records))
