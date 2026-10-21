"""Bake local, premultiplied deformation; the trajectory stays in the solver."""
from pathlib import Path
import sys,json,hashlib,math,argparse
import cv2,numpy as np
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'motion'))
from motionlib import detect_eye
from gaze_layers import GazeRig
from blink_curves import paint_curve_blink
ROOT=Path(__file__).resolve().parents[3]; INPUT=ROOT/'sources/interaction-rig'

def rgba(p):
 a=np.clip(p[:,:,3:4],0,1); q=np.concatenate([p[:,:,:3]/np.maximum(a,1e-8),a],axis=2)
 return np.round(np.clip(q,0,1)*255).astype('uint8')
def over(b,t): return t+b*(1-t[:,:,3:4])
def smooth(t): return t*t*(3-2*t)

def main(out):
 out.mkdir(parents=True,exist_ok=True)
 src=np.array(Image.open(INPUT/'source.png').convert('RGBA')); prem=src.astype('float32')/255; prem[:,:,:3]*=prem[:,:,3:4]
 eyes=[detect_eye(prem,b) for b in [(147,98,175,119),(189,90,217,114)]]
 gaze=GazeRig(prem,eyes,[{'gaze':[1.5,.5]},{'gaze':[-1.5,-.5]}])
 curves=[(149,108,173,108,2.5),(190,99,215,100,3)]
 yy,xx=np.mgrid[:480,:384].astype('float32')
 masks={n:np.array(Image.open(INPUT/f'{n}-mask.png'))>0 for n in ['left-leg','right-leg','coat-left','coat-right']}
 # Seam-free inverse warp of the connected original. There is no detached part
 # revealing unseen anatomy: upper body translates rigidly, knees absorb motion.
 # Store explicit base/foreground even though this deformation reveals no cavity.
 np.savez_compressed(INPUT/'composition.npz',base=prem,foreground=np.zeros_like(prem))
 allowed=np.zeros(src.shape[:2],'uint8'); allowed[src[:,:,3]>0]=255
 Image.fromarray(allowed).save(INPUT/'allowed-mask.png')
 descriptions={'airborne':(1,True),'wall-impact':(7,False),'landing-impact':(12,False),'dizzy-intro':(7,False),'dizzy-loop':(45,True),'recover':(21,False)}
 descriptions.update({'wall-impact_light':(7,False),'wall-impact_medium':(7,False),'landing-impact_light':(12,False),'landing-impact_medium':(12,False)})
 states=[]; allposes={}; contacts=[]; allowed_output=np.zeros((528,432),bool)
 for name,(count,loop) in descriptions.items():
  frames=[]; poses=[]; hits=[]
  kind=name.split("_")[0]; intensity=.375 if name.endswith("_light") else .6875 if name.endswith("_medium") else 1.
  for i in range(count):
   t=i*.02; u=i/max(1,count-1)
   bend=close=gx=gy=sway=stars=0.
   if kind=='wall-impact': close=math.sin(math.pi*u)**.6; bend=2*intensity*math.sin(math.pi*u)
   if kind=='landing-impact': bend=8*intensity*math.sin(math.pi*u)**1.4; close=math.sin(math.pi*u)**.55
   if kind=='dizzy-intro': close=.55*smooth(u); stars=smooth(u); bend=2*smooth(u)
   if kind=='dizzy-loop':
    phase=2*math.pi*i/count; sway=3*math.sin(phase); gx=1.4*math.sin(phase+.6); gy=.4*math.cos(phase); close=.55; stars=1; bend=2+.7*math.sin(phase)
   if kind=='recover': close=.55*(1-smooth(u)); stars=1-smooth(u); bend=2*(1-smooth(u))
   face=paint_curve_blink(gaze.render(gx,gy),eyes,close,curves,cover_margin=1.3,warm_skin_only=True,eye_apertures=gaze.eyes)
   # Vertical displacement is constant above knees, tapering smoothly to zero
   # at each planted boot. Face/neck retain their shape and relationship.
   weight=1-smooth(np.clip((yy-280)/180,0,1))
   # Left boot is higher in the approved pose: its local ankle remains fixed.
   weight=np.where(masks['left-leg'],1-smooth(np.clip((yy-285)/132,0,1)),weight)
   dx=np.zeros_like(xx)
   for n,sign in [('left-leg',-1),('right-leg',1)]:
    dx+=masks[n]*sign*bend*.45*np.sin(np.pi*np.clip((yy-290)/160,0,1))
   # Extend the coordinate field smoothly around the cutout; do not use alpha
   # compositing of moved copies, which would leave residual legs behind.
   for n,sign in [('coat-left',-1),('coat-right',1)]:
    dx += masks[n]*sign*bend*.3*np.clip((yy-220)/100,0,1)*math.sin(math.pi*u+.4)
   dx=cv2.GaussianBlur(dx,(15,15),3)
   moved=cv2.remap(face,xx-dx,yy-bend*weight,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
   canvas=np.zeros((528,432,4),'float32'); canvas[24:504,24:408]=moved
   # Whole-body balance around the visible lower boot. No independent head turn.
   if abs(sway)>.001:
    matrix=cv2.getRotationMatrix2D((249,484),sway,1)
    canvas=cv2.warpAffine(canvas,matrix,(432,528),flags=cv2.INTER_LINEAR)
   hit=[]
   for row in range(canvas.shape[0]):
    line=np.pad(canvas[row,:,3]>.094,(1,1)); edges=np.flatnonzero(line[1:]!=line[:-1])
    for start,end in zip(edges[::2],edges[1::2]): hit.append([row,int(start),int(end)])
   hits.append(hit)
   # Three stars orbit with rear half occluded by the actual head alpha.
   if stars>0:
    back=Image.new('RGBA',(432,528)); front=Image.new('RGBA',(432,528))
    for k in range(3):
     a=2*math.pi*((0 if kind=='dizzy-intro' else t/.9)+k/3); x=216+66*math.cos(a); y=53+14*math.sin(a)
     target=front if math.sin(a)>0 else back; draw=ImageDraw.Draw(target)
     points=[(x+(.0+7 if j%2==0 else 3)*math.sin(j*math.pi/5),y-(7 if j%2==0 else 3)*math.cos(j*math.pi/5)) for j in range(10)]
     draw.polygon(points,fill=(255,218,104,int(255*stars)),outline=(115,83,42,int(255*stars)))
    def pre(im):
     a=np.array(im).astype('float32')/255; a[:,:,:3]*=a[:,:,3:4]; return a
    canvas=over(pre(back),canvas); canvas=over(canvas,pre(front))
   allowed_output |= canvas[:,:,3]>0
   frame=Image.fromarray(rgba(canvas)); frames.append(frame)
   poses.append({'timeMs':i*20,'bendPixels':bend,'eyeClosure':close,'gaze':[gx,gy],'balanceDegrees':sway,'starOpacity':stars})
  # Keep small atlases bounded; 8 columns, deduplicate exact frames.
  unique=[]; uniquehits=[]; seq=[]; hashes={}
  for frame,hit in zip(frames,hits):
   digest=hashlib.sha256(frame.tobytes()).hexdigest()
   if digest not in hashes: hashes[digest]=len(unique);unique.append(frame);uniquehits.append(hit)
   seq.append(hashes[digest])
  cols=min(8,len(unique)); atlas=Image.new('RGBA',(cols*432,math.ceil(len(unique)/cols)*528))
  for j,f in enumerate(unique):atlas.paste(f,(j%cols*432,j//cols*528))
  atlas.save(out/f'{name}.webp','WEBP',lossless=True,quality=100,method=3,exact=True)
  with Image.open(out/f'{name}.webp') as decoded: assert decoded.convert('RGBA').tobytes()==atlas.tobytes()
  states.append({'id':'interaction_'+name,'asset':name+'.webp','frameWidth':216,'frameHeight':264,'pixelScale':2,'sequence':seq,'durationsMs':[1000 if count==1 else 20]*count,'loop':loop,'loopStart':0,'hitRuns':uniquehits})
  if kind=='airborne':
   patches=Image.new('RGBA',(76*6,38))
   for level in range(1,7):
    blink=paint_curve_blink(prem,eyes,level/6,curves,cover_margin=1.3,warm_skin_only=True,eye_apertures=gaze.eyes)
    patches.paste(Image.fromarray(rgba(blink)).crop((142,85,218,123)),((level-1)*76,0))
   patches.save(out/'airborne-eyes.webp','WEBP',lossless=True,quality=100,method=3,exact=True)
   states[-1]['blink']={'asset':'airborne-eyes.webp','x':166,'y':109,'width':76,'height':38,'levels':6,'frames':[[0,1,2,3,4,5]],'seed':17071}
  allposes[name]=poses
  contacts.append(frames[count//2])
 Image.fromarray(allowed_output.astype('uint8')*255).save(INPUT/'allowed-output-mask.png')
 manifest={'version':1,'sourceSha256':hashlib.sha256((INPUT/'source.png').read_bytes()).hexdigest(),'contentOrigin':[12,12],'center':[108.52944371463218,116.131783043654],'foot':[124.5,242],'collider':'physics.json','states':states}
 (out/'interaction.json').write_text(json.dumps(manifest,indent=2)+'\n')
 (INPUT/'curves.json').write_text(json.dumps({'eyes':[(147,98,175,119),(189,90,217,114)],'closedCurves':curves,'poses':allposes,'pivotPixels':[249,484],'deformation':'connected inverse map; rigid face/neck; no exposed hidden regions'},indent=2))
 sheet=Image.new('RGBA',(432*3,558*math.ceil(len(contacts)/3)),'#eeeeee'); draw=ImageDraw.Draw(sheet)
 for j,f in enumerate(contacts): sheet.alpha_composite(f,(j%3*432,j//3*558+30));draw.text((j%3*432+8,j//3*558+8),list(descriptions)[j],fill='black')
 sheet.convert('RGB').save(out/'contact-sheet.png')
 print(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True); main(p.parse_args().out)
