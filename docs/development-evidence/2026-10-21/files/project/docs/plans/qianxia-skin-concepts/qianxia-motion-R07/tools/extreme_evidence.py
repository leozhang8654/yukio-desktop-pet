"""Maker evidence from the encoded atlases: source vs the two most displaced
decoded frames, cropped around the moving parts at 4x, on the stage colour."""
from pathlib import Path
import json, sys
import numpy as np
from PIL import Image, ImageDraw
R=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]) if len(sys.argv)>1 else R/'review'
def tile(im,n,w,h,c):return im.crop((n%c*w,n//c*h,(n%c+1)*w,(n//c+1)*h))
def comp(im,bg='#303040'):b=Image.new('RGBA',im.size,bg);b.alpha_composite(im);return b.convert('RGB')
BOX={'idle':(110,215,215,275),'view_image':(110,200,195,275),'write_file':(95,215,290,270),'verify':(105,175,180,260),'read_web':(90,180,150,235),'default_work':(100,220,155,265),'respond':(90,170,185,255),'question_for_user':(225,215,290,275),'failed':(95,170,175,250)}
for rnd in ['R06','R07']:
    base=R.parent/f'qianxia-motion-{rnd}'
    m=json.loads((base/'motion/motion.json').read_text())
    for s in m['states']:
        if s['id'] not in BOX:continue
        atlas=Image.open(base/'motion'/s['asset']).convert('RGBA');src=Image.open(R/f"rigs/{s['id']}/source-2x.png").convert('RGBA')
        tl=json.loads((base/f"rigs/{s['id']}/timeline.json").read_text()) if (base/f"rigs/{s['id']}/timeline.json").exists() else None
        n=max(s['sequence'])+1;frames=[tile(atlas,i,384,416,s['columns']) for i in range(n)]
        box=BOX[s['id']];a=np.array(src).astype(float)
        energy=[np.abs(np.array(f).astype(float)-a)[box[1]:box[3],box[0]:box[2]].sum() for f in frames]
        order=np.argsort(energy)[::-1][:2]
        views=[('source',src)]+[(f'frame {i}',frames[i]) for i in order]
        z=4;w=(box[2]-box[0])*z;h=(box[3]-box[1])*z
        sheet=Image.new('RGB',(w*3,h+22),'#202030');d=ImageDraw.Draw(sheet)
        for j,(label,im) in enumerate(views):
            sheet.paste(comp(im.crop(box)).resize((w,h),Image.Resampling.LANCZOS),(j*w,22));d.text((j*w+6,5),f"{rnd} {s['id']} {label}",fill='white')
        sheet.save(out/f"{rnd}-{s['id']}-extremes.png")
print('ok')
