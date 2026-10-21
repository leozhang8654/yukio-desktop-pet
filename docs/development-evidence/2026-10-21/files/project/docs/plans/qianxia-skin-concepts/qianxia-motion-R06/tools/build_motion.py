"""Candidate-only Qianxia R06 animation renderer (motion timing rework of R05).

Same approved R08 inputs, masks, clean plates and eye rig as R05. Only the
timing curves, amplitudes and the transform model changed. No production
asset writes.
"""
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
DURATIONS=[14,8,6.6,6.4,4.4,5,6.4,5.6,1.5,3,1.4,1.3]
# read_web now pivots at the wrist/sleeve junction so the fingertip itself
# travels; R05 pinned the fingertip and bent the back of the hand instead.
PIVOTS={'idle':{'touching-hand':[390,790],'orb':[566,765]},'view_image':{'hand-and-stylus':[394,760]},'write_file':{'left-hand':[354,746],'right-hand':[846,748]},'verify':{'hand-and-probe':[400,730]},'read_web':{'pointing-hand':[338,668]},'default_work':{'trackball-hand':[365,796]},'respond':{'hand-and-card':[390,752]},'failed':{'hand-and-card':[382,744]},'question_for_user':{'pressing-hand':[750,728],'button-cap':[800,834]}}
ONCE={'respond','failed','question_for_user'}
# Timelines below are written in 192x208 display points; D converts to the
# 1205-wide source pixels the rig works in (source scale 0.3187 at 2x).
D=2/(W/1205)
def prem(a):
    a=np.array(a.convert('RGBA')).astype('float32')/255;a[:,:,:3]*=a[:,:,3:4];return a
def byte(a):
    a=np.clip(a,0,1);b=a.copy();b[:,:,:3]/=np.maximum(b[:,:,3:4],1e-8);b[b[:,:,3]==0]=0
    return np.clip(b*255+.5,0,255).astype('uint8')
def resize(a):return cv2.resize(a,(W,H),interpolation=cv2.INTER_AREA)
def over(b,t):return t+b*(1-t[:,:,3:4])
def opaque_plate(clean,original):
    """The generated clean plates are partly see-through (alpha 0-0.98) inside
    the body. Wherever the approved drawing is opaque the plate must be too,
    otherwise the stage shows through as a grey trail when a hand moves.
    Unreliable colour (alpha < 0.5) is filled from its neighbours."""
    a=clean[:,:,3];body=original[:,:,3]>.98
    straight=clean[:,:,:3]/np.maximum(a[:,:,None],1e-4)
    weak=body&(a<.5)
    if weak.any():
        s8=(np.clip(straight,0,1)*255+.5).astype('uint8')
        filled=cv2.inpaint(s8,weak.astype('uint8'),5,cv2.INPAINT_TELEA).astype('float32')/255
        straight[weak]=filled[weak]
    target=np.where(body,1.,a).astype('float32')
    return np.concatenate([np.clip(straight,0,1)*target[:,:,None],target[:,:,None]],2)

# Easing per segment instead of one symmetric smoothstep everywhere.
# 'sacc' is an eye jump (fast start, soft landing); 'in' accelerates into a
# contact; 'out' decelerates on arrival; 'io3' is a purposeful hand move.
EASE={'lin':lambda u:u,'io':lambda u:u*u*(3-2*u),'io3':lambda u:4*u**3 if u<.5 else 1-(2-2*u)**3/2,
      'out':lambda u:1-(1-u)**3,'out2':lambda u:1-(1-u)**2,'in':lambda u:u**3,'in2':lambda u:u*u,
      'sacc':lambda u:1-(1-u)**4}
def frame_of(t):return int(round(t*FPS))
def track(f,keys):
    """keys: (seconds, values, ease[, arc]) — ease/arc describe the segment
    arriving at that key. Times snap to the 30 fps grid so repeated poses are
    bit-identical and deduplicate in the atlas."""
    ks=[(frame_of(k[0]),np.array(k[1],float),k[2] if len(k)>2 else 'io',np.array(k[3],float) if len(k)>3 else None) for k in keys]
    if f<=ks[0][0]:return ks[0][1].copy()
    for (f0,v0,_,_),(f1,v1,e,arc) in zip(ks,ks[1:]):
        if f<=f1:
            if f1==f0:return v1.copy()
            k=EASE[e]((f-f0)/(f1-f0));v=v0*(1-k)+v1*k
            if arc is not None:v=v+arc*4*k*(1-k)
            return v
    return ks[-1][1].copy()

# One keystroke, frame by frame: quick lift, accelerating strike, contact.
TAP=[0,.62,1,.45,0]
ENTER=[0,.35,.75,1,1,.55,0]
def taps(f,schedule):
    v=0.
    for start,profile,amp in schedule:
        i=f-frame_of(start)
        if 0<=i<len(profile):v+=profile[i]*amp
    return v

def orb_swing(t,t0):
    """Damped sway of the hovering orb after the flick; exactly zero once it
    has settled so the long idle hold deduplicates to one frame."""
    z=t-t0
    if z<=0 or z>=2.6:return 0.
    return 1.75*math.sin(2*math.pi*1.15*z)*math.exp(-1.5*z)*(1-float(smooth((z-2.0)/.6)))

def pose(s,t):
    f=frame_of(t);t=f/FPS
    p={n:[0.,0.,0.,0.] for n in PIVOTS.get(s,{})};g=np.zeros(2)
    if s=='idle':
        # Eyes reach the orb before the finger moves; finger draws back, flicks,
        # lingers on contact, then relaxes. The orb answers the flick.
        hand=track(f,[(0,(0,0,0)),(1.10,(0,0,0)),(1.30,(-.5,.15,-1.0),'io'),(1.43,(1.55,-.35,.6),'out'),(1.60,(1.55,-.35,.6)),(2.20,(0,0,0),'io3'),(14,(0,0,0))])
        x=orb_swing(t,1.38)
        p['touching-hand']=[*hand,0];p['orb']=[x,-.22*abs(x),2.2*x,0]
        orb=(-.25,.45)
        g=track(f,[(0,(0,0)),(.80,(0,0)),(.90,orb,'sacc'),(3.5,orb),(3.6,(0,0),'sacc'),(8.0,(0,0)),(8.1,orb,'sacc'),(9.2,orb),(9.3,(0,0),'sacc'),(14,(0,0))])
        g=g+np.array([.3*orb_swing(t-.08,1.38),0])
    elif s=='thinking':
        A=(-1.0,.35);B=(.9,-.35);C=(-.8,0)
        g=track(f,[(0,A),(1.1,A),(1.17,(-.75,.35),'sacc'),(2.0,(-.75,.35)),(2.11,B,'sacc'),(3.7,B),(3.81,A,'sacc'),(5.2,A),(5.3,C,'sacc'),(6.5,C),(6.57,(-.6,.15),'sacc'),(7.5,(-.6,.15)),(7.62,A,'sacc'),(8,A)])
    elif s=='read_file':
        y=.45
        g=track(f,[(0,(-1.05,y)),(.45,(-1.05,y)),(.52,(-.83,y),'sacc'),(.95,(-.83,y)),(1.02,(-.61,y),'sacc'),
                   (1.30,(-.61,y)),(1.40,(-.15,.5),'sacc'),(1.80,(-.15,.5)),(1.87,(.07,.5),'sacc'),(2.30,(.07,.5)),(2.37,(.29,.5),'sacc'),
                   (2.70,(.29,.5)),(2.80,(.8,y),'sacc'),(3.25,(.8,y)),(3.32,(1.02,y),'sacc'),(3.80,(1.02,y)),(3.87,(1.22,y),'sacc'),
                   (5.40,(1.22,y)),(5.55,(-1.05,y),'io3'),(6.6,(-1.05,y))])
    elif s=='view_image':
        P1=(1.1,-.7,-.6);P2=(2.3,-.25,.5)
        p['hand-and-stylus']=[*track(f,[(0,(0,0,0)),(.75,(0,0,0)),(1.22,(1.15,-.74,-.62),'io3',(0,-.5,0)),(1.32,P1,'out2'),(2.55,P1),
                                          (3.10,(2.38,-.27,.52),'io3',(0,-.5,0)),(3.20,P2,'out2'),(4.55,P2),(5.25,(0,0,0),'io3',(0,-.4,0)),(6.4,(0,0,0))]),0]
        G0=(.25,.55);G1=(.6,.45);G2=(.95,.5)
        g=track(f,[(0,G0),(.60,G0),(.68,G1,'sacc'),(1.80,G1),(1.86,(.75,.5),'sacc'),(2.40,(.75,.5)),(2.48,G2,'sacc'),(3.70,G2),(3.76,(.8,.55),'sacc'),(4.40,(.8,.55)),(4.50,G0,'sacc'),(6.4,G0)])
    elif s=='write_file':
        # Hands rest on the keys (the approved drawing). Short irregular bursts,
        # a pause, and a slower Enter; then the eyes read the line.
        Ls=[.20,.47,.77,1.47,1.90,2.60,2.87]
        Rs=[.33,.63,1.33,1.60,1.77,2.03,2.73]
        sched_l=[(a,TAP,1.) for a in Ls];sched_r=[(a,TAP,1.) for a in Rs]+[(3.03,ENTER,1.45)]
        p['left-hand']=[0,0,-3.4*taps(f,sched_l),0];p['right-hand']=[0,0,3.8*taps(f,sched_r),0]
        K=(0,.55)
        g=track(f,[(0,K),(3.30,K),(3.38,(-.45,.4),'sacc'),(3.62,(-.45,.4)),(3.67,(-.1,.4),'sacc'),(3.86,(-.1,.4)),(3.91,(.3,.4),'sacc'),(4.10,(.3,.4)),(4.20,K,'sacc'),(4.4,K)])
    elif s=='verify':
        # Hover above the socket, seat the tip with a small press, wait for the
        # reading, lift along the probe axis, look, return to hover.
        # Part of the lift is a wrist turn (rigid), so the hand stretches less.
        Hv=(-.55,-.55,-1.4);Lf=(-1.0,-1.05,-3.0)
        p['hand-and-probe']=[*track(f,[(0,Hv),(.45,Hv),(.80,(.05,.12,.25),'io3'),(.92,(0,0,0),'out2'),(2.20,(0,0,0)),(2.55,Lf,'io3'),(3.85,Lf),(4.35,Hv,'io'),(5,Hv)]),0]
        tip=(-.15,.55);dial=(.55,.6)
        g=track(f,[(0,tip),(1.25,tip),(1.33,dial,'sacc'),(2.05,dial),(2.13,tip,'sacc'),(2.90,tip),(2.98,dial,'sacc'),(4.10,dial),(4.18,tip,'sacc'),(5,tip)])
    elif s=='read_web':
        # Look at the panel, raise the finger, tap once, then read.
        p['pointing-hand']=[*track(f,[(0,(0,0,0)),(.95,(0,0,0)),(1.20,(.25,-1.1,-1.2),'out2'),(1.30,(.3,-1.2,-1.3),'lin'),(1.40,(.05,.2,.2),'in2'),(1.52,(0,0,0),'out2'),(6.4,(0,0,0))]),0]
        Lp=(-.7,.45);Cp=(.1,.4);Rp=(.9,.45)
        g=track(f,[(0,Lp),(1.62,Lp),(1.72,Cp,'sacc'),(2.40,Cp),(2.46,(.3,.42),'sacc'),(3.30,(.3,.42)),(3.40,Rp,'sacc'),(4.30,Rp),(4.36,(1.1,.45),'sacc'),(5.60,(1.1,.45)),(5.75,Lp,'io3'),(6.4,Lp)])
    elif s=='default_work':
        # Two short rolls of the ball, watch the screen, one finer correction.
        p['trackball-hand']=[*track(f,[(0,(0,0,0)),(.80,(0,0,0)),(1.05,(1.0,-.35,.6),'io3'),(1.25,(.75,-.25,.45),'io'),(1.45,(1.75,-.5,.9),'io3'),(1.60,(1.6,-.45,.85),'out2'),
                                         (2.95,(1.6,-.45,.85)),(3.35,(1.0,-.2,.3),'io3'),(3.50,(1.05,-.22,.32),'out2'),(4.75,(1.05,-.22,.32)),(5.15,(0,0,0),'io'),(5.6,(0,0,0))]),0]
        M=(.95,.3)
        g=track(f,[(0,M),(1.90,M),(1.96,(1.15,.38),'sacc'),(2.60,(1.15,.38)),(2.66,(.8,.3),'sacc'),(4.00,(.8,.3)),(4.06,(1.1,.35),'sacc'),(5.00,(1.1,.35)),(5.08,M,'sacc'),(5.6,M)])
    elif s=='respond':
        # Small gather, reach out with a wrist turn and a slight growth toward
        # the viewer, overshoot and settle; eyes go from the card to you.
        Fin=(-.85,-.6,-1.6,.045)
        p['hand-and-card']=list(track(f,[(0,(0,0,0,0)),(.15,(.15,.15,.5,-.006),'io'),(.60,(-1.0,-.7,-1.9,.053),'io3'),(.78,(-.78,-.55,-1.5,.042),'out2'),(.95,Fin,'io'),(1.5,Fin)]))
        g=track(f,[(0,(-.75,.35)),(.50,(-.75,.35)),(.58,(0,0),'sacc'),(1.5,(0,0))])
    elif s=='question_for_user':
        press=track(f,[(0,(0,)),(.25,(0,)),(.40,(1.6,),'in2'),(.56,(1.6,)),(.74,(.15,),'out2'),(.86,(0,),'io'),(1.4,(0,))])[0]
        p['pressing-hand']=[0,press,0,0];p['button-cap']=[0,max(0.,press),0,0]
        g=track(f,[(0,(0,0)),(.08,(.75,.55),'sacc'),(.95,(.75,.55)),(1.03,(0,0),'sacc'),(1.4,(0,0))])
    elif s=='failed':
        # Lift and hold it up toward you: small rise plus growth about the wrist.
        Fin=(.1,-1.2,.8,.035)
        p['hand-and-card']=list(track(f,[(0,(0,0,0,0)),(.12,(0,.25,0,-.004),'io'),(.50,(.12,-1.45,1.0,.042),'io3'),(.66,(.08,-1.1,.7,.032),'out2'),(.85,Fin,'io'),(1.3,Fin)]))
        g=track(f,[(0,(0,0)),(.04,(-.6,.45),'sacc'),(.70,(-.6,.45)),(.80,(0,.2),'sacc'),(1.3,(0,.2))])
    # Display points -> source pixels; angle (degrees) and scale delta unchanged.
    p={n:[float(v[0])*D,float(v[1])*D,float(v[2]),float(v[3])] for n,v in p.items()}
    return p,[float(g[0])*D,float(g[1])*D]

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
            clean=original.copy();clean[box[1]:box[3],box[0]:box[2]]=donor;clean=opaque_plate(clean,original)
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
                    if s=='failed':coloured &= np.mgrid[:original.shape[0],:original.shape[1]][0]<708
                    halo=cv2.dilate((rawm[n]>0).astype('uint8'),np.ones((17,17),'uint8'))>0
                    supports[n]|=halo&coloured
            erase=np.maximum.reduce(list(supports.values())).astype('float32')
            if s=='view_image':
                # The stylus' anti-aliased outline reaches ~2 px past its mask and
                # stayed in the plate as a thin grey line beside the moved pen.
                # Clear it along the shaft only (x>440, y>700), away from the cuff.
                gy,gx=np.mgrid[:original.shape[0],:original.shape[1]]
                tail=cv2.dilate((rawm['hand-and-stylus']>0).astype('uint8'),np.ones((7,7),'uint8')).astype(bool)&(gx>440)&(gy>700)
                erase=np.maximum(erase,tail.astype('float32'))
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
            self.allowed=cv2.dilate((resize(combined)>.001).astype('uint8'),np.ones((25,25),'uint8'))>0
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
            dx,dy,ang,ds=transforms[n];dx*=self.scale;dy*=self.scale;k=1+ds
            pivot=np.array(PIVOTS[self.state][n])*self.scale
            distance=np.hypot(self.xx-pivot[0],self.yy-pivot[1]);weight=smooth(distance/(45*self.scale))
            if self.state in {'respond','verify','failed'}:weight=smooth(distance/(90*self.scale))
            if self.state=='verify':weight=np.maximum(weight,smooth((self.xx-420*self.scale)/(25*self.scale)))
            if n=='orb':weight=np.ones_like(weight)
            if n in {'left-hand','right-hand','pressing-hand'}:weight=smooth((self.yy-pivot[1])/(45*self.scale))
            rad=math.radians(ang);cx=self.xx-pivot[0];cy=self.yy-pivot[1]
            # Rigid rotation/scale about the wrist; translation fades in from it.
            sx=pivot[0]+(cx*math.cos(rad)+cy*math.sin(rad))/k-dx*weight
            sy=pivot[1]+(-cx*math.sin(rad)+cy*math.cos(rad))/k-dy*weight
            if n=='button-cap':
                sx=self.xx;bottom=834*self.scale;sy=bottom-(bottom-self.yy)/(1-dy/(50*self.scale))
            moved=cv2.remap(self.layers[n],sx.astype('float32'),sy.astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
            frame=over(frame,moved)
            if self.state=='write_file':
                cuff=(self.yy<758*self.scale)&(self.masks[n]<.01)&(np.hypot(self.xx-pivot[0],self.yy-pivot[1])<130*self.scale)
                frame[cuff]=self.src[cuff]
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
