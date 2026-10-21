from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,cv2,json
r=Path(__file__).resolve().parents[1];before=r.parent/'qianxia-cutout-R01'
def curve(points,tension=.35):
 p=np.asarray(points,float);out=[]
 for i in range(len(p)):
  a,b,c,d=p[(i-1)%len(p)],p[i],p[(i+1)%len(p)],p[(i+2)%len(p)]
  t=np.linspace(0,1,max(8,int(np.linalg.norm(c-b)*4)),endpoint=False)[:,None]
  out.extend((2*t**3-3*t*t+1)*b+(t**3-2*t*t+t)*(c-a)*tension+(-2*t**3+3*t*t)*c+(t**3-t*t)*(d-b)*tension)
 return np.array(out)
def render(points,size):
 pts=curve(points);lo=np.floor(pts.min(0)-2).astype(int);hi=np.ceil(pts.max(0)+3).astype(int);m=Image.new('L',tuple((hi-lo)*8));ImageDraw.Draw(m).polygon([tuple(x) for x in ((pts-lo)*8)],fill=255);full=Image.new('L',size);full.paste(m.resize(tuple(hi-lo),Image.Resampling.BOX),tuple(lo));return np.array(full)
records=[]
for p in sorted((before/'masks').glob('*/iris-*.png')):
 raw=np.array(Image.open(p));cs,_=cv2.findContours((raw>127).astype('uint8'),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);c=max(cs,key=cv2.contourArea);pts=cv2.approxPolyDP(c,.65,True)[:,0,:].astype(float)
 # Subpixel contour fit follows each sampled SAM boundary; no raster blur or morphology.
 full=render(pts,Image.open(p).size);dst=r/'masks'/p.parent.name/p.name;Image.fromarray(full).save(dst)
 records.append({'part':str(p.relative_to(before/'masks')),'control_points':pts.tolist(),'method':'per-contour cubic fit, 8x coverage, no source repaint'})
(r/'reference/eye-contour-fit.json').write_text(json.dumps(records,indent=2))
# Individually traced visible outer ink, avoiding adjacent sleeve/key/hair lines.
paths={
'idle/touching-hand':[(387,790),(393,775),(405,760),(421,748),(440,740),(459,736),(480,735),(507,737),(521,740),(526,746),(525,753),(520,758),(512,761),(489,760),(478,758),(483,767),(485,778),(482,786),(475,792),(466,794),(465,801),(460,807),(452,810),(447,810),(445,816),(438,821),(429,822),(422,819),(420,816),(414,823),(405,825),(397,823),(389,818),(386,808),(385,801)],
'write_file/left-hand':[(354,787),(359,772),(369,760),(385,750),(404,741),(419,740),(431,741),(441,741),(451,746),(458,757),(462,771),(468,790),(467,797),(461,801),(453,800),(444,793),(437,780),(430,764),(431,784),(431,798),(428,806),(420,810),(411,809),(404,805),(401,792),(399,779),(398,799),(395,806),(388,809),(381,808),(377,804),(375,790),(374,782),(372,796),(368,803),(361,802),(356,797)],
'verify/hand-and-probe':[(382,642),(381,635),(384,627),(390,621),(395,615),(412,608),(438,599),(457,591),(464,591),(471,596),(476,606),(485,633),(495,661),(497,670),(500,685),(500,698),(498,706),(501,718),(501,727),(496,735),(499,750),(500,764),(499,774),(496,773),(489,762),(480,746),(475,738),(469,735),(463,725),(454,723),(448,716),(444,718),(436,729),(422,736),(408,738),(395,735),(384,727),(376,714),(372,699),(373,681),(378,660)],
'respond/hand-and-card':[(329,637),(329,625),(334,617),(344,612),(374,607),(421,601),(467,594),(495,590),(504,591),(512,597),(516,606),(520,631),(525,663),(529,693),(526,701),(519,707),(488,713),(450,719),(414,724),(389,728),(391,739),(392,749),(388,759),(379,768),(367,774),(353,774),(339,770),(326,762),(317,751),(310,736),(305,719),(304,705),(309,692),(316,683),(318,679),(313,675),(313,666),(316,658),(322,653),(323,647)],
'failed/hand-and-card':[(367,643),(363,624),(363,614),(369,609),(383,604),(423,595),(463,586),(482,582),(491,586),(496,595),(503,630),(508,654),(513,675),(511,682),(506,686),(480,693),(450,700),(418,707),(414,709),(417,718),(414,726),(408,732),(401,737),(398,745),(391,752),(380,754),(367,752),(354,746),(342,734),(335,719),(332,704),(332,686),(337,669),(346,656),(357,648)]
}
for key,pts in paths.items():
 state,name=key.split('/');im=Image.open(next((r/'source').glob('*-'+state+'.png')));full=render(pts,im.size);full[np.array(im)[:,:,3]==0]=0;Image.fromarray(full).save(r/'masks'/state/(name+'.png'))
(r/'reference/retraced-contours.json').write_text(json.dumps({'coordinate_system':'original source pixels','method':'individual outer ink trace, cubic curve, 8x area coverage','paths':paths},indent=2))
