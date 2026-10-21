from pathlib import Path
from PIL import Image,ImageDraw
import json,numpy as np
r=Path(__file__).resolve().parents[1];out=r/'rigs/question_for_user/pressing-hand/refinement-05';out.mkdir(exist_ok=True)
# Manual exterior tracing on the original pixel coordinate system; grid evidence in review/button-source-grid.png.
# Keep the ink outline with the hand, excluding sleeve, button and the original false pink island.
points=[(714,752),(718,741),(723,733),(731,725),(739,720),(746,718),(751,718),(760,721),(766,720),(773,720),(781,722),(790,726),(797,732),(801,741),(803,750),(803,756),(801,761),(797,766),(791,771),(789,775),(790,781),(790,786),(787,789),(783,790),(778,788),(773,784),(770,781),(766,778),(764,781),(763,785),(759,788),(754,789),(748,788),(743,790),(736,790),(730,788),(723,783),(718,778),(714,771),(712,765),(712,759)]
source=Image.open(r/'source/11-question_for_user.png').convert('RGBA');w,h=source.size
# A small 8x ROI avoids changing the source resolution or its alpha.
box=(700,705,820,805);ss=8;local=Image.new('L',((box[2]-box[0])*ss,(box[3]-box[1])*ss));ImageDraw.Draw(local).polygon([((x-box[0])*ss,(y-box[1])*ss) for x,y in points],fill=255)
mask=Image.new('L',(w,h));mask.paste(local.resize((box[2]-box[0],box[3]-box[1]),Image.Resampling.BOX),box[:2]);a=np.array(mask);a[np.array(source)[:,:,3]==0]=0;Image.fromarray(a).save(out/'candidate-mask.png')
(out/'parameters.json').write_text(json.dumps({'method':'manual exterior contour traced after SAM candidate visual review','points_xy':points,'supersample':ss,'source_modified':False,'reason':'SAM omitted thick outline and included pink sleeve around fingertip; solid visible hand exterior traced locally','status':'static candidate; no moving-frame acceptance'},indent=2))
