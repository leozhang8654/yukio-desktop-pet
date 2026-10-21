from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,shutil
r=Path(__file__).resolve().parents[1];data=json.loads((r/'reference/manual-contours.json').read_text());paths=data['contours']
# Reject the ink-snapping experiment: neighbouring sleeve ink caused outward spikes.
patches={
'read_web/pointing-hand':{(434,660):(424,660),(440,667):(429,667),(442,676):(431,675),(438,685):(428,683),(431,691):(424,689),(422,694):(420,690)},
'respond/hand-and-card':{(322,637):(329,637),(320,625):(328,625),(321,617):(332,617),(326,612):(337,613),(337,608):(343,611),(368,603):(368,606),(405,600):(405,601),(444,595):(444,596),(480,590):(480,591),(498,587):(498,588),(507,589):(506,590),(515,594):(513,595),(519,602):(517,602),(521,619):(520,619),(526,650):(525,650),(531,680):(530,680),(534,695):(531,695),(532,703):(528,702),(527,711):(524,706),(518,716):(517,709),(489,720):(489,714),(456,724):(456,719),(423,728):(423,724),(398,731):(398,728),(388,732):(388,729)},
'view_image/hand-and-stylus':{(491,702):(488,702),(499,708):(493,709),(500,715):(494,715),(497,725):(490,725),(494,730):(488,730),(501,746):(496,746),(509,764):(505,764),(514,779):(512,779),(519,796):(517,796),(520,812):(519,810)},
'write_file/left-hand':{(449,741):(446,741),(457,746):(452,746),(465,754):(458,754),(469,765):(461,765),(471,781):(466,781),(475,790):(468,790),(474,797):(467,798),(468,801):(462,802)},
'verify/hand-and-probe':{(381,632):(383,632),(383,625):(385,627),(504,762):(500,762),(505,776):(501,776),(500,782):(499,778),(496,781):(496,776)}
}
for key,pts in paths.items():
 pts=[patches.get(key,{}).get(tuple(pt),pt) for pt in pts];paths[key]=pts;state,name=key.split('/');im=Image.open(next((r/'source').glob('*-'+state+'.png')));w,h=im.size
 x0=min(x for x,y in pts)-2;y0=min(y for x,y in pts)-2;x1=max(x for x,y in pts)+3;y1=max(y for x,y in pts)+3
 m=Image.new('L',((x1-x0)*8,(y1-y0)*8));ImageDraw.Draw(m).polygon([((x-x0)*8,(y-y0)*8) for x,y in pts],fill=255);full=Image.new('L',(w,h));full.paste(m.resize((x1-x0,y1-y0),Image.Resampling.BOX),(x0,y0));a=np.array(full);a[np.array(im)[:,:,3]==0]=0
 # A single enclosed zero caused by two contour segments touching is corrected only for trackball hand.
 if state=='default_work':
  import cv2
  c,_=cv2.findContours((a>0).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);fill=np.zeros_like(a);cv2.drawContours(fill,c,-1,255,cv2.FILLED);yy,xx=np.nonzero((fill>0)&(a==0));assert len(xx)<=1;a[yy,xx]=255
 Image.fromarray(a).save(r/'masks'/state/(name+'.png'))
(r/'reference/final-hand-contours.json').write_text(json.dumps(data,indent=2))
