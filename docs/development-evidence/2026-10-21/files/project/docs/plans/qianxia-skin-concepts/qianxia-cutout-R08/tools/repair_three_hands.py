from pathlib import Path
from PIL import Image
import numpy as np,json
r=Path(__file__).resolve().parents[1];prev=r.parent/'qianxia-cutout-R04';rec=[]
def edge(key,box,side,knots,minimum=False):
 p=r/'masks'/(key+'.png');a=np.array(Image.open(p));x0,y0,x1,y1=box;y,x=np.mgrid[y0:y1,x0:x1];v=x if side=='bottom' else y;b=np.interp(v,*np.array(knots).T);c=np.clip(b-(y if side=='bottom' else x)+.5,0,1)*255
 if minimum:c=np.minimum(c,a[y0:y1,x0:x1])
 a[y0:y1,x0:x1]=np.rint(c).astype('uint8');Image.fromarray(a).save(p);rec.append(dict(part=key,roi=box,side=side,knots=knots,minimum=minimum))
for key in ['write_file/left-hand','view_image/hand-and-stylus','failed/hand-and-card']:(r/'masks'/(key+'.png')).write_bytes((prev/'masks'/(key+'.png')).read_bytes())
edge('failed/hand-and-card',(422,695,479,714),'bottom',[(422,707.5),(479,693.25)],True)
edge('view_image/hand-and-stylus',(443,749,464,770),'right',[(749,459),(750,457.5),(751,456),(752,454.5),(753,454),(754,454),(756,454),(758,453.3),(760,452.5),(762,450.8),(764,449.0),(765,447.5),(766,445.5),(767,444),(768,443),(769,443)],True)
# Restore the source-visible continuous lower ink boundary of all three affected fingertips.
edge('write_file/left-hand',(357,797,441,820),'bottom',[(357,800),(360,803.3),(364,806.3),(368,807.6),(371,807.5),(375,806.8),(379,805.0),(382,807.3),(386,810.3),(391,812.0),(396,812.6),(400,811.3),(404,809.3),(407,808.7),(410,810.6),(414,812.8),(419,813.4),(423,813.1),(426,812.0),(430,809.0),(433,805),(436,801),(439,797),(441,793.5)])
# Source-visible right ink side of the third finger, connecting into its rounded tip.
edge('write_file/left-hand',(426,780,441,799),'right',[(780,433.3),(784,434.0),(788,434.5),(792,435.0),(796,435.1),(798,435.0)])
(r/'reference/three-hand-repairs.json').write_text(json.dumps(rec,indent=2));print('modified3')
p=r/'masks/write_file/left-hand.png';a=np.array(Image.open(p));old=np.array(Image.open(prev/'masks/write_file/left-hand.png'))
# These dark finger separators are source-visible interior ink, not transparent gaps.
a[778:805,399:407]=255
a[780:797,369:384]=255
# Restoring the adjacent finger outline must never clip the other, already visible finger.
a[780:820,437:441]=np.maximum(a[780:820,437:441],old[780:820,437:441])
Image.fromarray(a).save(p)
edge('write_file/left-hand',(432,788,437,809),'right',[(788,434.4),(790,434.3),(792,434.2),(794,434.1),(796,434.0),(798,433.8),(800,433.3),(802,432.9),(804,432.7),(806,432.0),(808,431.0)],True)
(r/'reference/three-hand-repairs.json').write_text(json.dumps(rec,indent=2))
# Two isolated pixels at the already identified keyboard wedge, outside the hand boundary.
p=r/'masks/write_file/left-hand.png';a=np.array(Image.open(p));a[799:801,437]=0;Image.fromarray(a).save(p)
