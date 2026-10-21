from pathlib import Path
from PIL import Image
r=Path(__file__).resolve().parents[1];parts=sorted((r/'masks').glob('*/iris-*.png'))
for k in range(0,22,6):
 ims=[Image.open(r/'review'/p.parent.name/p.stem/'four-backgrounds-200.png') for p in parts[k:k+6]];cw=max(x.width for x in ims);ch=max(x.height for x in ims);out=Image.new('RGB',(cw*3,ch*2),'#888888')
 for i,im in enumerate(ims):out.paste(im,((i%3)*cw,(i//3)*ch))
 out.save(r/'review'/f'eye-background-page-{k//6+1}.png')
ims=[]
for p in parts:
 a=Image.open(r/'review'/p.parent.name/p.stem/'overlay-200.png');b=Image.open(r/'review'/p.parent.name/p.stem/'contour-200.png');im=Image.new('RGB',(a.width+b.width,max(a.height,b.height)),'#888888');im.paste(a,(0,0));im.paste(b,(a.width,0));ims.append(im)
cw=max(x.width for x in ims);ch=max(x.height for x in ims);out=Image.new('RGB',(cw*3,ch*8),'#888888')
for i,im in enumerate(ims):out.paste(im,((i%3)*cw,(i//3)*ch))
out.save(r/'review'/'eye-overlay-contours-200.png')
