from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,cv2,json
out=Path(__file__).resolve().parent;root=out.parents[1]/'qianxia-cutout-R07';prev=json.loads((out.parent/'R06-hands/findings.json').read_text());ev=out/'evidence';ev.mkdir(exist_ok=True);idx=[]
for z in prev['parts']:

 if (z['state'],z['part']) not in {('write_file','left-hand'),('respond','hand-and-card'),('view_image','hand-and-stylus')}:continue
 s=Image.open(root/z['source']).convert('RGBA');m=Image.open(root/z['mask']).convert('L');p=Image.open(root/z['candidate']).convert('RGBA');box=m.getbbox();box=(box[0]-15,box[1]-15,box[2]+15,box[3]+15);sc=s.crop(box);pc=p.crop(box);ma=m.crop(box);w,h=sc.size
 def comp(im,bg):
  b=Image.new('RGBA',im.size,bg);b.alpha_composite(im);return b.convert('RGB')
 over=comp(sc,'white');green=Image.new('RGBA',(w,h),(0,255,0));green.putalpha(ma.point(lambda x:int(x*.35)));over=Image.alpha_composite(over.convert('RGBA'),green).convert('RGB');cont=comp(sc,'white');a=np.array(cont);cs,_=cv2.findContours((np.array(ma)>0).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);cv2.drawContours(a,cs,-1,(255,0,255),1);cont=Image.fromarray(a)
 cols=[comp(sc,'white'),Image.merge('RGB',(ma,ma,ma)),comp(pc,'black')];canvas=Image.new('RGB',(max(3*w+40,3*w*2+40),3*h+75),'#cccccc');d=ImageDraw.Draw(canvas)
 for i,im in enumerate(cols):canvas.paste(im,(i*(w+10),25));d.text((i*(w+10),5),['source 100%','mask 100%','candidate 100%'][i],fill='black')
 for i,im in enumerate([comp(sc,'white'),over,cont]):canvas.paste(im.resize((w*2,h*2)),(i*(w*2+10),h+65));d.text((i*(w*2+10),h+45),['source 200%','overlay 200%','contour 200%'][i],fill='black')
 ref=ev/f'{z["state"]}-{z["part"]}-reference.png';canvas.save(ref)
 # independent native 100% multi backgrounds
 bgcanvas=Image.new('RGB',(4*w+30,h+25),'#bbbbbb');bd=ImageDraw.Draw(bgcanvas)
 for i,bg in enumerate(['checker','black','white','magenta']):
  if bg=='checker':
   ba=Image.new('RGBA',(w,h),'white');dr=ImageDraw.Draw(ba)
   for y in range(0,h,8):
    for x in range(0,w,8):
     if (x//8+y//8)%2:dr.rectangle((x,y,x+7,y+7),fill='#bbbbbb')
   ba.alpha_composite(pc);im=ba.convert('RGB')
  else:im=comp(pc,bg)
  bgcanvas.paste(im,(i*(w+10),25));bd.text((i*(w+10),4),bg+' 100%',fill='black')
 bg100=ev/f'{z["state"]}-{z["part"]}-background100.png';bgcanvas.save(bg100)
 idx.append({'state':z['state'],'part':z['part'],'source':z['source'],'mask':z['mask'],'candidate':z['candidate'],'crop':box,'reference':str(ref),'background100':str(bg100),'background200':str(root/'review'/z['state']/z['part']/'four-backgrounds-200.png')})
for f in prev['findings'] + [{'id':'respond-internal','part':'respond/hand-and-card','regions_xyxy':[[350,713,384,730]]}]:
 st,part=f['part'].split('/');z=next(z for z in prev['parts'] if z['state']==st and z['part']==part);s=Image.open(root/z['source']).convert('RGBA');p=Image.open(root/z['candidate']).convert('RGBA');m=Image.open(root/z['mask']).convert('L')
 for j,b in enumerate(f['regions_xyxy']):
  w,h=b[2]-b[0],b[3]-b[1];ims=[s.crop(b).convert('RGB')]
  for bg in ['black','magenta']:
   im=Image.new('RGBA',(w,h),bg);im.alpha_composite(p.crop(b));ims.append(im.convert('RGB'))
  ims.append(m.crop(b).convert('RGB'));c=Image.new('RGB',(w*6*4+30,h*6+28),'#ccc');d=ImageDraw.Draw(c)
  for i,im in enumerate(ims):c.paste(im.resize((w*6,h*6),Image.Resampling.NEAREST),(i*(w*6+10),28));d.text((i*(w*6+10),5),['source 600%','black','magenta','mask'][i],fill='black')
  c.save(ev/f'{f["id"]}-{j+1}-roi600.png')
(out/'inspection-index.json').write_text(json.dumps(idx,ensure_ascii=False,indent=2)+'\n');print(len(idx),'parts')
