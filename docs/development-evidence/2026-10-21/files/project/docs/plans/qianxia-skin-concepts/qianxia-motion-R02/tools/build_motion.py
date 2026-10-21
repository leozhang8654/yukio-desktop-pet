"""Candidate-only Qianxia R08 animation renderer. No production asset writes."""
from pathlib import Path
import argparse, json, hashlib, math
import cv2
import numpy as np
from PIL import Image, ImageDraw
from eyes import Eyes, smooth

R=Path(__file__).resolve().parents[1]
W,H=384,416
FPS=30
STATES=['idle','thinking','read_file','view_image','write_file','verify','read_web','default_work','respond','task_complete','question_for_user','failed']
DURATIONS=[14,8,6,6,3.4,4.8,6,5.4,1.2,3,1.1,.9]
PIVOTS={'idle':{'touching-hand':[390,790],'orb':[566,765]},'view_image':{'hand-and-stylus':[394,760]},'write_file':{'left-hand':[404,742],'right-hand':[793,748]},'verify':{'hand-and-probe':[393,707]},'read_web':{'pointing-hand':[411,682]},'default_work':{'trackball-hand':[365,796]},'respond':{'hand-and-card':[390,752]},'failed':{'hand-and-card':[367,725]},'question_for_user':{'pressing-hand':[750,728],'button-cap':[800,834]}}
ONCE={'respond','failed','question_for_user'}
def prem(a):
    a=np.array(a.convert('RGBA')).astype('float32')/255;a[:,:,:3]*=a[:,:,3:4];return a
def byte(a):
    a=np.clip(a,0,1);b=a.copy();b[:,:,:3]/=np.maximum(b[:,:,3:4],1e-8);b[b[:,:,3]==0]=0
    return np.clip(b*255+.5,0,255).astype('uint8')
def resize(a):return cv2.resize(a,(W,H),interpolation=cv2.INTER_AREA)
def over(b,t):return t+b*(1-t[:,:,3:4])
def pulse(t,a,b,c,d):return float(smooth((t-a)/(b-a))*(1-smooth((t-c)/(d-c))))
def key(t,values):
    if t<=values[0][0]:return np.array(values[0][1:],dtype=float)
    for left,right in zip(values,values[1:]):
        if t<=right[0]:
            k=float(smooth((t-left[0])/(right[0]-left[0])))
            return np.array(left[1:])*(1-k)+np.array(right[1:])*k
    return np.array(values[-1][1:],dtype=float)
def pose(s,t):
    p={n:[0.,0.,0.] for n in PIVOTS.get(s,{})};g=[0.,0.]
    if s=='idle':
        v=pulse(t,1.2,1.7,1.75,2.1);p['touching-hand']=[7*v,-1*v,0]
        z=max(0,t-1.6);ball=math.sin(z*8)*math.exp(-z*3)*7 if 1.6<t<2.9 else 0
        p['orb']=[ball,-abs(ball)*.25,0]
    elif s=='thinking':g=key(t,[(0,0,0),(1.8,0,0),(2.05,2.5,-1),(3.6,2.5,-1),(3.9,0,0),(6,0,0),(6.3,-1.5,1),(7.7,-1.5,1),(8,0,0)])
    elif s=='read_file':g=key(t,[(0,-2,1),(1.2,-2,1),(1.45,0,1),(2.75,0,1),(3,2.5,1),(4.5,2.5,1),(4.8,-2,1),(6,-2,1)])
    elif s=='view_image':
        p['hand-and-stylus']=key(t,[(0,0,0,0),(.8,0,0,0),(1.3,3,-6,-.3),(2.5,3,-6,-.3),(3.1,8,-4,.5),(4.6,8,-4,.5),(5.2,0,0,0),(6,0,0,0)]).tolist()
        g=key(t,[(0,0,1),(.6,0,1),(1.1,1,1),(2.3,1,1),(2.9,2.5,1),(4.5,2.5,1),(5,0,1),(6,0,1)])
    elif s=='write_file':
        for n,starts in [('left-hand',[.15,.72,1.89]),('right-hand',[.39,1.56,2.16])]:
            v=sum(pulse(t,a,a+.08,a+.10,a+.21) for a in starts);p[n]=[0,5.6*v,0]
        g=[0,1]
    elif s=='verify':
        p['hand-and-probe']=key(t,[(0,-3,-6,0),(.6,-3,-6,0),(1.05,0,0,0),(2.3,0,0,0),(2.65,-5,-10,0),(3.9,-5,-10,0),(4.3,-3,-6,0),(4.8,-3,-6,0)]).tolist();g=[-.5,1]
    elif s=='read_web':
        v=pulse(t,1.1,1.45,1.46,1.7);p['pointing-hand']=[3*v,-4*v,0]
        g=key(t,[(0,-1,0),(4,-1,0),(4.3,2,-.5),(5.7,2,-.5),(6,-1,0)])
    elif s=='default_work':
        p['trackball-hand']=key(t,[(0,0,0,0),(.8,0,0,0),(1.5,6,0,.5),(2.9,6,0,.5),(3.4,2,0,-.2),(4.7,2,0,-.2),(5.1,0,0,0),(5.4,0,0,0)]).tolist();g=[2,0]
    elif s=='respond':
        v=float(smooth(t/.8));p['hand-and-card']=[-11*v,-7*v,-.5*v];g=[1.5*v,-.5*v]
    elif s=='question_for_user':
        v=pulse(t,.15,.4,.6,.85);p['pressing-hand']=[0,5*v,0];p['button-cap']=[0,5*v,0];g=key(t,[(0,1,1),(.85,1,1),(1.1,0,0)])
    elif s=='failed':
        v=float(smooth(t/.65));p['hand-and-card']=[0,-5*v,-.2*v];g=[0,0]
    return p,[float(x) for x in g]

class Rig:
    def __init__(self,s):
        self.state=s
        sp=next((R/'inputs/source').glob('*-'+s+'.png'));original=prem(Image.open(sp));self.scale=W/original.shape[1]
        self.src=resize(original);self.original=original
        rawm={p.stem:np.array(Image.open(p)).astype('float32')/255 for p in (R/'inputs/masks'/s).glob('*.png')}
        if s=='question_for_user':rawm['button-cap']=np.array(Image.open(R/'rigs/question_for_user/button-cap-motion-mask.png')).astype('float32')/255
        self.masks={n:resize(m) for n,m in rawm.items()};self.names=list(PIVOTS.get(s,{}))
        # Ball is behind the hand. Button cap is also behind the pressing finger.
        if s=='idle':self.names=['orb','touching-hand']
        if s=='question_for_user':self.names=['button-cap','pressing-hand']
        self.layers={n:resize(original*rawm[n][:,:,None]) for n in self.names}
        self.base=self.src.copy();self.allowed=np.zeros((H,W),bool)
        self.yy,self.xx=np.mgrid[:H,:W].astype('float32')
        if self.names:
            combined=np.maximum.reduce([rawm[n] for n in self.names])
            crops=json.loads((R/'reference/cleanplate-crops.json').read_text())
            if s=='question_for_user':box=[660,690,890,850];gen=Image.open(R/'generated/button-empty.png')
            else:box=crops[s];gen=Image.open(R/f'generated/{s}-cleanplate.png')
            if s=='write_file':
                # Image generator letterboxed the extra-wide crop; remove only
                # the exterior all-transparent rows before coordinate mapping.
                a=np.array(gen.convert('RGBA'))[:,:,3];ys=np.flatnonzero((a>240).mean(1)>.2);gen=gen.crop((0,int(ys.min()),gen.width,int(ys.max()+1)))
            donor=cv2.resize(prem(gen),(box[2]-box[0],box[3]-box[1]),interpolation=cv2.INTER_AREA)
            clean=original.copy();clean[box[1]:box[3],box[0]:box[2]]=donor
            # A cutout from flattened artwork contains background in its soft
            # edge RGB. Recover a valid premultiplied foreground instead of
            # adding it back over the original edge (which creates a ghost).
            supports={n:cv2.dilate((rawm[n]>0).astype('uint8'),np.ones((3,3),'uint8')).astype(bool) for n in self.names}
            for n in self.names:
                if n=='hand-and-card':
                    # The luminous card rim has a cyan/pink fringe beyond the
                    # opaque static cutout. It belongs to the travelling card.
                    rgb=original[:,:,:3]
                    coloured=((rgb[:,:,2]-rgb[:,:,0]>.035)&(rgb[:,:,1]-rgb[:,:,0]>.02))|((rgb[:,:,0]-rgb[:,:,1]>.15)&(rgb[:,:,2]-rgb[:,:,1]>.08))
                    if s=='respond':coloured=(rgb[:,:,2]-rgb[:,:,0]>.035)&(rgb[:,:,1]-rgb[:,:,0]>.02)
                    halo=cv2.dilate((rawm[n]>0).astype('uint8'),np.ones((17,17),'uint8'))>0
                    supports[n]|=halo&coloured
            erase=np.maximum.reduce(list(supports.values())).astype('float32')
            for n in self.names:
                a=rawm[n].copy();bg=clean[:,:,:3];rgb=original[:,:,:3]
                lower=np.where(rgb<bg,1-rgb/np.maximum(bg,1e-5),(rgb-bg)/np.maximum(1-bg,1e-5)).max(2)
                a=np.maximum(a,np.clip(lower,0,1))*supports[n]
                # The source alpha still controls outside transparent edges.
                layer=np.concatenate([rgb-bg*(1-a[:,:,None]),a[:,:,None]],2)
                layer[:,:,:3]=np.minimum(np.maximum(layer[:,:,:3],0),layer[:,:,3:4])
                layer[~supports[n]]=0
                self.layers[n]=resize(layer)
                fd=R/'rigs'/s;fd.mkdir(exist_ok=True)
                Image.fromarray((a*255+.5).clip(0,255).astype('uint8')).save(fd/f'{n}-motion-matte.png')
            self.base=resize(original*(1-erase[:,:,None])+clean*erase[:,:,None])
            # Allowed support includes the actual travel and interpolation kernel.
            self.allowed=cv2.dilate((resize(combined)>.001).astype('uint8'),np.ones((13,13),'uint8'))>0
        self.neutral=self.base.copy()
        for n in self.names:self.neutral=over(self.neutral,self.layers[n])
        self.eyes=Eyes(self.src,self.masks,self.scale);self.allowed|=self.eyes.allowed
        self.fixed=np.zeros((H,W),bool)
        if s=='question_for_user':
            self.fixed=(self.yy>=833*self.scale)|((self.yy>=799*self.scale)&((self.xx<757*self.scale)|(self.xx>847*self.scale)))
        if s=='write_file':self.fixed=self.yy>=821*self.scale
        if s=='verify':self.fixed=self.yy>=784*self.scale
        if s=='view_image':self.fixed=self.yy>=818*self.scale
        if s=='default_work':self.fixed=self.yy>=821*self.scale
        self.allowed&=~self.fixed
        folder=R/'rigs'/s;folder.mkdir(exist_ok=True)
        Image.fromarray(byte(self.src)).save(folder/'source-2x.png')
        Image.fromarray(byte(self.base)).save(folder/'cleanplate-2x.png')
        Image.fromarray(self.allowed.astype('uint8')*255).save(folder/'allowed-mask-2x.png')
        Image.fromarray(self.eyes.allowed.astype('uint8')*255).save(folder/'eyes-allowed-2x.png')
        np.savez_compressed(folder/'composition-2x.npz',base=self.base,source=self.src,**self.layers)

    def render(self,t,level=0):
        transforms,gaze=pose(self.state,t);frame=self.base.copy();maxdisp=0
        for n in self.names:
            dx,dy,ang=transforms[n];dx*=self.scale;dy*=self.scale
            pivot=np.array(PIVOTS[self.state][n])*self.scale
            distance=np.hypot(self.xx-pivot[0],self.yy-pivot[1]);weight=smooth(distance/(45*self.scale))
            if self.state=='respond':weight=smooth(distance/(90*self.scale))
            if n=='orb':weight=np.ones_like(weight)
            if n in {'left-hand','right-hand','pressing-hand'}:weight=smooth((self.yy-pivot[1])/(45*self.scale))
            rad=math.radians(ang);cx=self.xx-pivot[0];cy=self.yy-pivot[1]
            sx=pivot[0]+cx*math.cos(rad)+cy*math.sin(rad)-dx*weight
            sy=pivot[1]-cx*math.sin(rad)+cy*math.cos(rad)-dy*weight
            if n=='button-cap':
                sx=self.xx;bottom=834*self.scale;sy=bottom-(bottom-self.yy)/(1-dy/(50*self.scale))
            moved=cv2.remap(self.layers[n],sx.astype('float32'),sy.astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
            frame=over(frame,moved)
            selected=self.masks[n]>.05
            if selected.any():maxdisp=max(maxdisp,float(np.hypot(sx-self.xx,sy-self.yy)[selected].max()/2))
        if self.names:
            frame=np.clip(frame,0,1)
            if all(sum(abs(v) for v in value)<1e-7 for value in transforms.values()):frame=self.src.copy()
        else:frame=self.src.copy()
        # Each eye receives exactly the same offset, with one conservative gain.
        frame=self.eyes.paint(frame,(gaze[0]*self.scale,gaze[1]*self.scale),level)
        frame[~self.allowed]=self.src[~self.allowed]
        frame[self.fixed]=self.src[self.fixed]
        frame[:,:,:3]=np.minimum(frame[:,:,:3],frame[:,:,3:4])
        out=byte(frame);original_bytes=byte(self.src);out[~self.allowed]=original_bytes[~self.allowed];out[self.fixed]=original_bytes[self.fixed]
        return out,maxdisp

def atlas(frames,path):
    h,w=frames[0].shape[:2];cols=min(12,len(frames));rows=math.ceil(len(frames)/cols)
    sheet=Image.new('RGBA',(cols*w,rows*h))
    for i,f in enumerate(frames):sheet.paste(Image.fromarray(f),(i%cols*w,i//cols*h))
    sheet.save(path,lossless=True,exact=True,method=4)
    decoded=Image.open(path).convert('RGBA');assert np.array_equal(np.array(decoded),np.array(sheet))
    # Native review uses this exact decoded image, never pre-encode memory data.
    decoded.save(path.with_suffix('.decoded.png'))
    return cols

def export(s):
    rig=Rig(s);duration=DURATIONS[STATES.index(s)];steps=round(duration*FPS)
    times=np.linspace(0,duration,steps+1)
    frames=[];seen={};seq=[];samples=[];peak=0;peak_i=0;poses=[]
    for i,t in enumerate(times):
        f,d=rig.render(t);k=hashlib.sha256(f.tobytes()).hexdigest()
        if k not in seen:seen[k]=len(frames);frames.append(f);samples.append(float(t))
        seq.append(seen[k]);poses.append({'time':float(t),'transforms':pose(s,t)[0],'gaze':pose(s,t)[1],'maximum_displacement_display_px':d})
        if d>peak:peak=d;peak_i=i
    durations=[round(1000/FPS)]*len(seq);durations[-1]=33
    loop_start=len(seq)-1 if s in ONCE else 0
    if s=='task_complete':seq=[0];durations=[3000];loop_start=0
    elif s in ONCE:durations[-1]=5000
    else:assert seq[-1]==seq[0],(s,'loop seam')
    # Merge equal consecutive frames into explicit holds, preserving event tail.
    compact=[];ds=[];ls=None
    for i,(f,d) in enumerate(zip(seq,durations)):
        if i==loop_start:ls=len(compact)
        if compact and compact[-1]==f and i!=loop_start:ds[-1]+=d
        else:compact.append(f);ds.append(d)
    if s in ONCE:ls=len(compact)-1
    else:ls=0
    cols=atlas(frames,R/f'motion/{s}.webp')
    blink=None
    if rig.eyes.layers:
        x0,y0,x1,y1=rig.eyes.roi;patches=[];lookup={};mapping=[]
        for t in samples:
            row=[]
            for level in range(1,7):
                f,_=rig.render(t,level);patch=f[y0:y1,x0:x1];k=hashlib.sha256(patch.tobytes()).hexdigest()
                if k not in lookup:lookup[k]=len(patches);patches.append(patch)
                row.append(lookup[k])
            mapping.append(row)
        bcols=atlas(patches,R/f'motion/{s}-eyes.webp')
        blink=dict(asset=f'{s}-eyes.webp',decodedAsset=f'{s}-eyes.decoded.png',x=x0,y=y0,width=x1-x0,height=y1-y0,levels=6,frames=mapping,columns=bcols,seed=130+STATES.index(s),minIntervalMs=2800,maxIntervalMs=7000)
    spec=dict(id=s,asset=f'{s}.webp',decodedAsset=f'{s}.decoded.png',frameWidth=192,frameHeight=208,pixelScale=2,columns=cols,sequence=compact,durationsMs=ds,loop=True,loopStart=ls,mode='enter_then_hold' if s in ONCE else ('static' if s=='task_complete' else 'loop'),blink=blink)
    folder=R/'rigs'/s
    (folder/'timeline.json').write_text(json.dumps({'duration_seconds':duration,'samples':poses,'display_size':[192,208],'source_scale':rig.scale,'pivots_source_px':PIVOTS.get(s,{}),'maximum_displacement_display_px':peak,'peak_sample':peak_i},indent=2))
    baseline=byte(rig.src);changed=np.any(np.stack(frames)!=baseline,axis=3)
    # Head, neck and scene are independently checked outside eye and hand support.
    protected=np.ones((H,W),bool);protected[rig.allowed]=False
    report={'state':s,'unique_body_frames':len(frames),'steps':len(compact),'outside_allowed_changed':int(changed[:,protected].sum()),'maximum_displacement_display_px':peak,'loop_seam_equal':bool(np.array_equal(frames[compact[-1]],frames[compact[ls]])),'fully_static':len(frames)==1 if s=='task_complete' else None,'decoded_exact':True,'visual':'pending','independent':'pending'}
    (R/f'review/{s}-machine.json').write_text(json.dumps(report,indent=2))
    # Source, maximum motion, fully closed eye and visible difference diagnostic.
    extreme=frames[seq[min(peak_i,len(seq)-1)]];closed,_=rig.render(samples[0],6)
    sheet=Image.new('RGB',(W*4,H),'#303040')
    for k,f in enumerate([baseline,extreme,closed]):
        im=Image.fromarray(f);bg=Image.new('RGBA',(W,H),'#303040');bg.alpha_composite(im);sheet.paste(bg.convert('RGB'),(W*k,0))
    diff=np.any(extreme!=baseline,2);heat=baseline.copy();heat[diff]=[255,40,50,255];sheet.paste(Image.fromarray(heat).convert('RGB'),(W*3,0));sheet.save(R/f'review/{s}-keyframes.png')
    print(s,len(frames),'frames','maximum display motion',round(peak,2),flush=True)
    return spec

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--only',nargs='*');args=ap.parse_args()
    entries=[export(s) for s in (args.only or STATES)]
    path=R/'motion/motion.json'
    old=json.loads(path.read_text())['states'] if path.exists() else []
    merged={s['id']:s for s in old+entries}
    path.write_text(json.dumps({'version':4,'candidate':True,'character':'qianxia','states':[merged[s] for s in STATES if s in merged]},indent=2))
