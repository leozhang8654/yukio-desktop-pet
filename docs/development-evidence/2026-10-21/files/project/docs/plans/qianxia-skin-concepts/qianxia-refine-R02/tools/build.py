from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,hashlib,shutil,zipfile
r=Path(__file__).resolve().parents[1];prev=r.parent/'qianxia-refine-R01';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();dy=31
prior=json.loads((prev/'qa.json').read_text());manifest={'round':'R02','baseline':'R01 after user-reported button rim correction','baseline_directory':str(prev),'online_latest':'unverified: previous access HTTP401','files':[]};qa={'scope':'static art only','status':'pending_visual_review','files':[]}
shutil.copy2(prev/'task.md',r/'task.md');shutil.copy2(prev/'source/character-reference.png',r/'source/character-reference.png')
for item in prior['files']:
 f=item['file'];inp=prev/'candidates'/f;shutil.copy2(inp,r/'source'/f);im=Image.open(inp).convert('RGBA');a=np.array(im);out=im.copy()
 if f=='10-task_complete.png':
  assert not np.any(a[-dy:,:,3]>0),'Translation would clip source content'
  out=Image.new('RGBA',im.size,(0,0,0,0));out.paste(im,(0,dy))
  allowed=(a[:,:,3]>0);shifted=np.zeros_like(allowed);shifted[dy:]=allowed[:-dy];allowed|=shifted
  Image.fromarray((allowed*255).astype('uint8')).save(r/'edit-regions/10-translation-mask.png')
  out.save(r/'candidates'/f)
 else:
  allowed=np.zeros(a.shape[:2],bool);shutil.copy2(inp,r/'candidates'/f)
 b=np.array(Image.open(r/'candidates'/f));change=np.any(a!=b,axis=2);visible=(a[:,:,3]>0)|(b[:,:,3]>0)
 entry={'state_id':item['state_id'],'file':f,'input_sha256':sha(inp),'output_sha256':sha(r/'candidates'/f),'round09_sha256':item['sha256'],'size':list(im.size),'mode':'RGBA','source_file':'source/'+f,'output_file':'candidates/'+f,'input_alpha_bbox':im.getchannel('A').getbbox(),'output_alpha_bbox':Image.open(r/'candidates'/f).getchannel('A').getbbox()};manifest['files'].append(entry)
 rec={**entry,'changed_vs_R01':bool(change.any()),'decision':'whole composition integer translation (0,+31), to align furniture consensus; preserve all internal relationships' if f.startswith('10-') else 'byte-for-byte retained, including corrected question_for_user','changed_visible_or_alpha_pixels':int((change&visible).sum()),'outside_allowed_visible_or_alpha_changes':int((change&visible&~allowed).sum()),'allowed_region':'edit-regions/10-translation-mask.png' if f.startswith('10-') else None,'ui':'未测','native_playback':'未测','independent_review':'未测','layers_and_motion':'未制作'}
 if f.startswith('10-'):
  rec.update({'translation':[0,dy],'transported_rgba_mismatches':int(np.any(a[:-dy]!=b[dy:],axis=2).sum()),'clipped_visible_pixels':int((a[-dy:,:,3]>0).sum()),'input_alpha_sum':int(a[:,:,3].sum()),'output_alpha_sum':int(b[:,:,3].sum()),'input_visible_pixels':int((a[:,:,3]>0).sum()),'output_visible_pixels':int((b[:,:,3]>0).sum()),'post_cyan_y':939.5,'post_apron_bottom_y':1010,'remaining_variation':'Original drawing variations remain; desk foot bottom y=1268 versus other-state median1265. This is not a shared-layer asset or pixel-identical furniture.'})
 qa['files'].append(rec)
 diff=np.zeros_like(a);diff[change&visible]=[255,50,150,255];Image.fromarray(diff).save(r/'review'/f'{Path(f).stem}-diff.png')
# Round02 comparison matrix: all twelve at actual target frame size, before/after each state.
for bg,col in [('white','white'),('dark','#35353d'),('black','black'),('magenta','#ff00ff'),('checker',None)]:
 sheet=Image.new('RGB',(4*416,3*250),'#e5e5e9');d=ImageDraw.Draw(sheet)
 for i,item in enumerate(manifest['files']):
  for j,folder in enumerate(['source','candidates']):
   tile=Image.new('RGBA',(192,208),col or '#ddd')
   if col is None:
    td=ImageDraw.Draw(tile)
    for yy in range(0,208,8):
     for xx in range(0,192,8):
      if (xx//8+yy//8)%2:td.rectangle((xx,yy,xx+7,yy+7),fill='#aaa')
   im=Image.open(r/folder/item['file']);im.thumbnail((192,208),Image.Resampling.LANCZOS);tile.alpha_composite(im,((192-im.width)//2,(208-im.height)//2));x=(i%4)*416+j*202+8;y=(i//4)*250+32;sheet.paste(tile.convert('RGB'),(x,y));d.text((x,y-22),item['state_id']+(' / R01' if j==0 else ' / R02'),fill='black')
 sheet.save(r/'review'/f'12-state-pairs-192-{bg}.png')
# Same-size whole-image pair, and a 200% actual source-pixel crop of the contact.
a=Image.open(r/'source/10-task_complete.png');b=Image.open(r/'candidates/10-task_complete.png')
pair=Image.new('RGBA',(a.width*2,a.height),'#35353d');pair.alpha_composite(a);pair.alpha_composite(b,(a.width,0));pair.convert('RGB').save(r/'review/10-full-pair.png')
c=a.crop((260,640,1080,850));c.resize((1640,420),Image.Resampling.NEAREST).save(r/'review/10-contact-original-200.png')
c=b.crop((260,671,1080,881));c.resize((1640,420),Image.Resampling.NEAREST).save(r/'review/10-contact-aligned-200.png')
# Fixed screen coordinates illustrate the eliminated furniture jump using an independent state.
sheet=Image.new('RGB',(1200,448),'#35353d');d=ImageDraw.Draw(sheet)
for i,(label,path) in enumerate([('thinking / context reference only',r/'source/02-thinking.png'),('task_complete / R01',r/'source/10-task_complete.png'),('task_complete / R02 +31px',r/'candidates/10-task_complete.png')]):
 im=Image.open(path);im.thumbnail((384,416),Image.Resampling.LANCZOS);tile=Image.new('RGBA',(384,416),'#35353d');tile.alpha_composite(im,((384-im.width)//2,(416-im.height)//2));sheet.paste(tile.convert('RGB'),(i*400+8,30));d.text((i*400+8,7),label,fill='white');d.line((i*400+8,330,i*400+392,330),fill='#edb753',width=1)
sheet.save(r/'review/10-position-comparison.png')
(r/'input-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));(r/'qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
(r/'edit-regions/10-translation.json').write_text(json.dumps({'operation':'integer translation of the complete composition','offset':[0,31],'why':'desk cyan strip 908.5 vs eleven-state median940; apron bottom979 vs median1010; multiple furniture matching medians31–34','no_resampling':True,'no_redraw':True,'no_new_imagegen_call':True,'allowed_mask':'union of input and translated nonzero-alpha support; prepared before comparison','canvas':'unchanged','task_complete_pose':'head, sleeves, device, table, chair, boxes and legs translate together to preserve contacts'},ensure_ascii=False,indent=2))
(r/'prompts/operations.md').write_text('本轮无图像模型调用。依照任务书的确定性合成要求，只将完成状态整个RGBA图层向下整数平移31像素。不缩放、不插值、不重绘；其他11张逐字节复制自修正后的R01。测量与复现脚本见tools/。\n')
print(json.dumps(qa['files'][9],ensure_ascii=False,indent=2))
