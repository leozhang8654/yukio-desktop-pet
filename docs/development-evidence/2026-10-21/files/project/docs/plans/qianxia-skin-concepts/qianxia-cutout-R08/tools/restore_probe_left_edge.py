from pathlib import Path
from PIL import Image
import numpy as np,json
r=Path(__file__).resolve().parents[1];p=r/'masks/verify/hand-and-probe.png';a=np.array(Image.open(r.parent/'qianxia-cutout-R07/masks/verify/hand-and-probe.png'));before=a.copy()
box=(470,738,500,770);knots=[(738,474),(740,475),(742,476),(745,477.8),(750,481),(755,484.6),(760,488.3),(764,491.8),(768,495.3),(770,496.7)];x0,y0,x1,y1=box;y,x=np.mgrid[y0:y1,x0:x1];edge=np.interp(y,*np.array(knots).T);coverage=np.rint(np.clip(x+.5-edge,0,1)*255).astype('uint8');a[y0:y1,x0:x1]=np.maximum(a[y0:y1,x0:x1],coverage);Image.fromarray(a).save(p)
(r/'reference/probe-left-edge.json').write_text(json.dumps({'part':'verify/hand-and-probe','source_coordinate_roi':box,'left_boundary_y_x':knots,'operation':'restore cropped source-visible bevel below collar; mask alpha union only, source RGBA unchanged','changed_pixels':int(np.sum(a!=before))},indent=2));print('changed',int(np.sum(a!=before)))
