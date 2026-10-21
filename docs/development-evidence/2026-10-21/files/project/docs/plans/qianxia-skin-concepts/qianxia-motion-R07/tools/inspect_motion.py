from build_motion import *
sheet=Image.new('RGB',(1200,660),'#303040');d=ImageDraw.Draw(sheet)
for i,s in enumerate(STATES):
 rig=Rig(s);closed,_=rig.render(0,6);image=Image.fromarray(closed).crop((110,140,240,195)).resize((520,220));image.thumbnail((290,220));x=i%4*300;y=i//4*220;sheet.paste(image,(x,y+25),image);d.text((x+5,y+5),s,fill='white')
 if rig.names:
  params=json.loads((R/'rigs'/s/'timeline.json').read_text());t=params['samples'][params['peak_sample']]['time'];f,_=rig.render(t);ms=np.maximum.reduce([rig.masks[n] for n in rig.names]);ys,xs=np.where(ms>0);box=(max(0,xs.min()-5),max(0,ys.min()-5),min(W,xs.max()+6),min(H,ys.max()+6));src=Image.open(R/'rigs'/s/'source-2x.png');a=Image.fromarray(f);parts=Image.new('RGB',((box[2]-box[0])*8,(box[3]-box[1])*4),'#303040')
  for j,im in enumerate([src,a]):c=im.crop(box).resize(((box[2]-box[0])*4,(box[3]-box[1])*4));parts.paste(c,(j*c.width,0),c)
  parts.save(R/f'review/{s}-motion-detail.png')
 # Each six-stage eye pose, including all fixed corners and skin boundary.
 eye=Image.new('RGB',(6*210,200),'#303040')
 for lev in range(1,LID_LEVELS+1):
  f,_=rig.render(0,lev*6/LID_LEVELS);im=Image.fromarray(f).crop((115,145,242,190)).resize((210,75));eye.paste(im,((lev-1)%6*210,20+(lev-1)//6*90),im)
 eye.save(R/f'review/{s}-lids.png')
sheet.save(R/'review/closed-eyes-all.png')
