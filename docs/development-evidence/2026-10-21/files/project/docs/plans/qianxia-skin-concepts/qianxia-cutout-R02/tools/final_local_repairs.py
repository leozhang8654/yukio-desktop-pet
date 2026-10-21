from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,cv2
r=Path(__file__).resolve().parents[1]
def render(pts,size):
 p=np.array(pts,float);out=[]
 for i in range(len(p)):
  a,b,c,d=p[(i-1)%len(p)],p[i],p[(i+1)%len(p)],p[(i+2)%len(p)];t=np.linspace(0,1,80,endpoint=False)[:,None];out.extend((2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*(c-a)*.25+(-2*t**3+3*t*t)*c+(t**3-t*t)*(d-b)*.25)
 out=np.array(out);lo=np.floor(out.min(0)-2).astype(int);hi=np.ceil(out.max(0)+3).astype(int);im=Image.new('L',tuple((hi-lo)*8));ImageDraw.Draw(im).polygon([tuple(q) for q in (out-lo)*8],fill=255);full=Image.new('L',size);full.paste(im.resize(tuple(hi-lo),Image.Resampling.BOX),tuple(lo));return np.array(full)
patches={
'failed/hand-and-card':[((346,591,425,644),[(372,642),(368,638),(365,620),(365,615),(370,609),(385,605),(420,597),(450,590),(450,650),(350,660)])],
'verify/hand-and-probe':[((474,732,516,786),[(465,722),(498,720),(502,732),(505,741),(506,750),(507,761),(508,769),(507,774),(505,778),(502,779),(499,776),(496,770),(492,762),(486,748),(480,738)]),((379,602,424,648),[(384,644),(384,636),(385,630),(390,625),(396,617),(412,610),(450,596),(450,655),(379,655)])],
'read_web/pointing-hand':[((406,630,437,667),[(401,626),(412,628),(417,636),(420,644),(421,650),(421,655),(420,658),(425,661),(429,666),(432,675),(403,677)])],
'write_file/right-hand':[((735,771,759,807),[(752,765),(763,771),(763,795),(757,800),(750,799),(744,796),(743,791),(746,780)])]
}
records=[]
for key,items in patches.items():
 state,name=key.split('/');p=r/'masks'/state/(name+'.png');im=Image.open(p);a=np.array(im)
 for box,pts in items:
  x0,y0,x1,y1=box;pa=render(pts,im.size);a[y0:y1,x0:x1]=pa[y0:y1,x0:x1]
 if state=='failed':
  # The exposed card top is a straight sloped ink edge, excluding the intersecting hair/jaw.
  y,x=np.indices(a.shape);coverage=np.clip((y+.5-(689.5-.225*x))*2+.5,0,1);box=(x>=375)&(x<425)&(y>=591)&(y<614);a[box]=(a[box]*coverage[box]).round().astype('uint8')
 Image.fromarray(a).save(p);records.append({'part':key,'patches':items})
# Tiny keyboard-color wedges are outside the finger ink. Exclude only the two documented tips.
p=r/'masks/write_file/left-hand.png';a=np.array(Image.open(p));src=np.array(Image.open(next((r/'source').glob('*-write_file.png')))).astype(float)
for x0,y0,x1,y1 in [(369,799,380,812),(398,804,410,817)]:
 R,G,B=src[y0:y1,x0:x1,:3].transpose(2,0,1);poll=np.clip((B-G-5)/12,0,1)*np.clip((R-G-12)/30,0,1);a[y0:y1,x0:x1]=(a[y0:y1,x0:x1]*(1-poll)).round().astype('uint8')
Image.fromarray(a).save(p)
(r/'reference/final-local-repairs.json').write_text(json.dumps(records,indent=2))
