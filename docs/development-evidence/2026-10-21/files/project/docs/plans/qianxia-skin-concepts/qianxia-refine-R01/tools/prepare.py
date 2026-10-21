from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,hashlib,shutil
r=Path(__file__).resolve().parents[1]; base=r.parent; src=base/'selected-315331434243-round09'
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'basis':'local round09; live gallery HTTP 401, latest remote revision unverified','files':[]}
for p in sorted(src.glob('[0-9][0-9]-*.png')):
 im=Image.open(p); a=np.array(im)[:,:,3]
 for d in ['source','candidates']:shutil.copy2(p,r/d/p.name)
 web=base/'latest-website/assets'/p.name
 manifest['files'].append({'state_id':p.stem.split('-',1)[1],'file':p.name,'original_path':str(p),'sha256':hashfile(p),'size':list(im.size),'mode':im.mode,'alpha_extrema':[int(a.min()),int(a.max())],'transparent_pixels':int((a==0).sum()),'partial_alpha_pixels':int(((a>0)&(a<255)).sum()),'alpha_bbox':im.getchannel('A').getbbox(),'local_gallery_matches':hashfile(web)==hashfile(p)})
 # key interaction region, displayed at 200% without interpolating pixels
 crop=im.crop((270,600,950,900)); bg=Image.new('RGBA',crop.size,'#35353d'); bg.alpha_composite(crop)
 bg.convert('RGB').resize((1360,600),Image.Resampling.NEAREST).save(r/'review'/f'{p.stem}-interaction-200.png')
shutil.copy2(base/'character-reference.png',r/'source/character-reference.png')
shutil.copy2('/Users/developer/.codex/visualizations/2026/10/10/09dfcfd4-03a3-5f26-4209-736259697121/qianxia-design-v2/给AI_千夏十二状态动画底图优化任务书.md',r/'task.md')
manifest['reference']={'file':'character-reference.png','sha256':hashfile(r/'source/character-reference.png')}
(r/'input-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
for bgname,color in [('white','#ffffff'),('dark','#33333d'),('black','#000000'),('magenta','#ff00ff'),('checker',None)]:
 sheet=Image.new('RGB',(4*216,3*246),'#e5e5e9'); draw=ImageDraw.Draw(sheet)
 for i,item in enumerate(manifest['files']):
  tile=Image.new('RGBA',(192,208),color or '#eeeeee')
  if color is None:
   td=ImageDraw.Draw(tile)
   for y in range(0,208,8):
    for x in range(0,192,8):
     if (x//8+y//8)%2:td.rectangle((x,y,x+7,y+7),fill='#cccccc')
  im=Image.open(r/'source'/item['file']); im.thumbnail((192,208),Image.Resampling.LANCZOS);tile.alpha_composite(im,((192-im.width)//2,(208-im.height)//2))
  x=(i%4)*216+12;y=(i//4)*246+25;sheet.paste(tile.convert('RGB'),(x,y));draw.text((x,y-18),item['state_id'],fill='black')
 sheet.save(r/'review'/f'source-192-{bgname}.png')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
