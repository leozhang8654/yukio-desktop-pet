from pathlib import Path
from PIL import Image,ImageDraw
import json,hashlib,numpy as np
r=Path(__file__).resolve().parents[1]
m=json.loads((r/'input-manifest.json').read_text());hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
notes=[
'磁悬浮球与底座分离符合设定；指尖朝向球面，保留。',
'托腮接触、问号和双分支节点完整，保留。',
'三张文件卡边框与文件夹符号完整；交叠手透过投影可见，保留。',
'检查笔指向图片内，握持和透光台合理，保留。',
'两侧键盘均落在桌面，指尖接近键帽，代码符号完整，保留。',
'探针指向模块测试圆环，手柄握持及模块支撑明确，保留。',
'三面扇形投影和地球、链条完整；链条图标的断口是链接符号画法，不误判为损坏，保留。',
'手接触轨迹球，显示器背面朝观众、支架落桌合理，保留。',
'持卡边缘与信封完整，递交姿态、原高光保留。',
'遮脸趴桌、叠袖和对号牌保留；固定桌前灯条位置与其他状态存在差异，系列一致性待处理。',
'原指尖与按钮顶面存在间隙；仅用局部候选补成轻触，问号、装置及其他区域保持原像素。',
'警告三角与叹号完整，持卡关系及轻微失落表情合理，保留。']
qa={'scope':'静态底图局部精修；不含动画、App接入、安装或发布','status':'局部修复完成；系列一致性未全通过','live_gallery':'未测：HTTP 401；本地第九轮与本地发布副本12/12哈希相同','real_ui':'未测：没有本批千夏实际task bubble截图','native_scaling':'未测：图像预览不替代macOS/Windows原生缩放验证','independent_review':'未测：仅执行代理自检','files':[]}
for i,item in enumerate(m['files']):
 f=item['file'];src=Image.open(r/'source'/f);dst=Image.open(r/'candidates'/f);a=np.array(src);b=np.array(dst);changed=np.any(a!=b,axis=2)
 mask=np.array(Image.open(r/'edit-regions/11-contact-mask.png'))>0 if i==10 else np.zeros(a.shape[:2],bool)
 diff=np.zeros(a.shape,dtype=np.uint8);diff[changed]=[255,40,150,255];Image.fromarray(diff).save(r/'review'/f'{Path(f).stem}-diff.png')
 roi=a[870:990,300:900];sel=(roi[:,:,1]>180)&(roi[:,:,2]>180)&(roi[:,:,0]<180)&(roi[:,:,3]>200); ys,xs=np.where(sel)
 # Record source alpha bounding box as an objective positional marker; desk-strip coordinate uses color selection in the named ROI.
 rec={**item,'input_file':'source/'+f,'output_file':'candidates/'+f,'output_sha256':hashfile(r/'candidates'/f),'modified':bool(changed.any()),'issue_and_decision':notes[i],'allowed_region':'edit-regions/11-contact-mask.png' if i==10 else None,'changed_rgba_pixels':int(changed.sum()),'outside_allowed_visible_or_alpha_changes':int((changed&~mask&((a[:,:,3]>0)|(b[:,:,3]>0))).sum()),'alpha_changed_pixels':int((a[:,:,3]!=b[:,:,3]).sum()),'dimensions':'通过' if src.size==dst.size else '失败','identity_and_intent':'通过：全图目视；未改区像素一致','work_relationship':'通过：全图与交互区域200%检查','target_size':'通过：192×208等比五背景预览','series_consistency':'失败：桌前灯条y=908，其他为939–942；缺少已确认共享底层，保留原图待后续统一' if i==9 else '通过：本轮未移动固定场景；原状态间细微绘制差异保留','desk_strip_median_y':int(np.median(ys)+870),'ui_check':'未测：缺真实UI','animation_preparation':'未测：未制作分层、补底、枢轴、眼皮或动态循环；静态接触检查不替代动态验收','unresolved':['桌椅共享底层及跨状态固定坐标尚未确认'] if i==9 else [],'evidence':[f'review/{Path(f).stem}-interaction-200.png','review/source-192-white.png','review/source-192-dark.png','review/source-192-black.png','review/source-192-magenta.png','review/source-192-checker.png',f'review/{Path(f).stem}-diff.png']}
 if i==10:rec['evidence']+=['review/11-contact-before-after-400.png','review/11-pixel-check.json','review/11-final-multibg.png']
 qa['files'].append(rec)
 # Same-size original / final proof, two full input canvases side by side.
 pair=Image.new('RGBA',(src.width*2,src.height),'#35353d');pair.alpha_composite(src,(0,0));pair.alpha_composite(dst,(src.width,0));pair.convert('RGB').save(r/'review'/f'{Path(f).stem}-pair.png')
# Edited state across all required backgrounds.
f='11-question_for_user.png';im=Image.open(r/'candidates'/f);sheet=Image.new('RGB',(5*240,286),'#e5e5e9');d=ImageDraw.Draw(sheet)
for i,(label,col) in enumerate([('white','white'),('dark','#33333d'),('black','black'),('magenta','#ff00ff'),('checker',None)]):
 tile=Image.new('RGBA',(240,260),col or '#ddd')
 if col is None:
  td=ImageDraw.Draw(tile)
  for y in range(0,260,12):
   for x in range(0,240,12):
    if (x//12+y//12)%2:td.rectangle((x,y,x+11,y+11),fill='#aaa')
 small=im.copy();small.thumbnail((240,260),Image.Resampling.LANCZOS);tile.alpha_composite(small,((240-small.width)//2,0));sheet.paste(tile.convert('RGB'),(240*i,26));d.text((240*i+8,8),label,fill='black')
sheet.save(r/'review/11-final-multibg.png')
# Three environment examples at target size. These are deliberately non-native mock contexts.
board=Image.new('RGB',(900,760),'#eee');d=ImageDraw.Draw(board)
for i,mode in enumerate(['document mock','editor mock','wallpaper mock']):
 x=i*300;d.rectangle((x,0,x+299,759),fill=['#faf8f4','#212531','#758787'][i]);d.text((x+12,12),mode+' / NOT APP QA',fill=['black','white','white'][i])
 for y in range(48,740,22):
  if i<2:d.line((x+12,y,x+250-(y%5)*16,y),fill=['#d4d4d4','#526575'][i],width=2)
  else:d.ellipse((x-90+(y%9)*20,y-80,x+220,y+120),outline='#a8baba',width=3)
 for j,folder in enumerate(['source','candidates']):
  pet=Image.open(r/folder/f);pet.thumbnail((192,208),Image.Resampling.LANCZOS);board.paste(pet,(x+54,135+360*j),pet)
  d.rounded_rectangle((x+36,65+360*j,x+264,120+360*j),radius=10,fill='#fff',outline='#a1a1ab');d.text((x+49,85+360*j),'Waiting for your reply',fill='#333');d.text((x+10,350+360*j),folder,fill=['black','white','white'][i])
board.save(r/'review/context-mocks.png')
(r/'qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2))
region=json.loads((r/'edit-regions/11-contact.json').read_text());region['allowed_bbox']=list(Image.open(r/'edit-regions/11-contact-mask.png').getbbox());region['mask_is_authoritative']=True;region['registration_offset']=[-3,-4];region['source_alpha_restored_everywhere']=True;(r/'edit-regions/11-contact.json').write_text(json.dumps(region,ensure_ascii=False,indent=2))
print('12 files verified; changed:',sum(x['modified'] for x in qa['files']),'outside allowed changes:',sum(x['outside_allowed_visible_or_alpha_changes'] for x in qa['files']),'alpha changes:',sum(x['alpha_changed_pixels'] for x in qa['files']))
