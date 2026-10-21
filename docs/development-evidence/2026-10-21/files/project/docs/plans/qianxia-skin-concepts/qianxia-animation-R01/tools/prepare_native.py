from pathlib import Path
from PIL import Image,ImageOps
import json,shutil,hashlib
r=Path(__file__).resolve().parents[1];src=r.parent/'qianxia-refine-R02/candidates';out=r/'native/Assets'
for sub in ['activities','base','motion']:(out/sub).mkdir(parents=True,exist_ok=True)
states=[];manifest=[]
for p in sorted(src.glob('[0-9][0-9]-*.png')):
 shutil.copy2(p,r/'source'/p.name);im=Image.open(p).convert('RGBA');display=ImageOps.contain(im,(768,832),Image.Resampling.LANCZOS);frame=Image.new('RGBA',(768,832));offset=((768-display.width)//2,(832-display.height)//2);frame.paste(display,offset);sid=p.stem.split('-',1)[1];frame.save(out/'motion'/f'{sid}.png');states.append({'id':sid,'asset':f'{sid}.png','frameWidth':192,'frameHeight':208,'pixelScale':4,'sequence':[0],'durationsMs':[1000],'loop':True,'loopStart':0});manifest.append({'state_id':sid,'source':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_size':list(im.size),'preview_size':[768,832],'fitted_size':list(display.size),'offset':offset})
(out/'activities/activities.json').write_text(json.dumps({'states':[]}));(out/'motion/motion.json').write_text(json.dumps({'version':4,'states':states},indent=2))
# Required catalog slot; diagnostics only, not a designed held interaction.
shutil.copy2(out/'motion/idle.png',out/'base/held-diagnostic-only.png');(out/'base/base-animations.json').write_text(json.dumps({'animations':[{'id':'held','asset':'held-diagnostic-only.png','frameWidth':192,'frameHeight':208,'frameCount':1,'pixelScale':4,'nativeDurationsMs':[1000],'grip':{'x':96,'y':0,'headTop':0}}]}))
(r/'input-manifest.json').write_text(json.dumps({'source_round':'R02','files':manifest,'held_slot':'diagnostic catalog placeholder only; no held interaction delivered'},indent=2));print(out.resolve())
