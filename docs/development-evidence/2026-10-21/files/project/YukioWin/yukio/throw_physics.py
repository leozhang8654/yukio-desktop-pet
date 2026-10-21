"""One convex silhouette inside one monitor, in logical units, y up, seconds.

Fixed stepping is independent of drawing. Conservative advancement uses a
Lipschitz bound including angular sweep; it cannot skip an intermediate contact.
Rotation is a bounded presentation channel and stops at contact, injecting no
translation energy. This is deliberately not a general rigid body engine.
"""
import json
import math
from dataclasses import dataclass
from pathlib import Path


def load_config(assets):
    data = json.loads((Path(assets)/'interaction/physics.json').read_text())
    if data['version'] != 1 or data['units'] != 'logical-y-up-seconds':
        raise ValueError('unsupported interaction physics')
    if not (data["step"]>0 and data["gravity"]>0 and data["friction"]>0 and data["maxSteps"]>0 and data["strengthMaxSpeed"]>data["strengthMinSpeed"] and all(0<=data[k]<1 for k in ("wallRestitution","ceilingRestitution","floorRestitution"))):
        raise ValueError("invalid interaction physics")
    return data

def strength(c,speed):
    return max(0,min(1,(speed-c["strengthMinSpeed"])/(c["strengthMaxSpeed"]-c["strengthMinSpeed"])))

def impact_duration(c,hit):
    prefix="landing" if hit.normal[1]>0 else "wall"
    return c[prefix+"MinSeconds"]+(c[prefix+"MaxSeconds"]-c[prefix+"MinSeconds"])*hit.strength


@dataclass
class Impact:
    event_id: int
    time: float
    normal: tuple
    point: tuple
    speed: float
    strength: float


class ThrowPhysics:
    def __init__(self, config, room, position, velocity=(0,0), angle=0, rate=0,
                 scale=1, screen_id='', session_id=1):
        self.c = config
        self.room = tuple(room)
        self.x,self.y = position
        self.vx,self.vy = velocity
        self.angle = max(-config['maxAngle'],min(config['maxAngle'],angle))
        self.rate = max(-2.0,min(2.0,rate))
        self.scale = scale
        self.screen_id, self.session_id = screen_id,session_id
        self.phase = 'airborne'
        self.time = self.phase_time = self.accumulator = self.dropped_time = 0.0
        self.ground = False
        self.stable_time = self.peak_landing = 0.0
        self.last_landing_time=-math.inf; self.last_landing_duration=0.
        self.events = []
        self.last_impact = None
        self.event_count = self.exhaustions = 0
        self.degraded = False
        self.previous = (self.x,self.y,self.angle)
        self._fit()
        self._recover_inside()
        self.previous = (self.x,self.y,self.angle)

    def bounds(self, angle=None):
        a = self.angle if angle is None else angle
        co,si = math.cos(a),math.sin(a)
        pts = [(self.scale*(x*co-y*si), self.scale*(x*si+y*co)) for x,y in self.c['hull']]
        return min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)

    def _fit(self):
        # Preserve aspect ratio if even the silhouette cannot fit this monitor.
        b=self.bounds(); w,h=self.room
        ratio=min(1,(w-2)/max(b[2]-b[0],1),(h-2)/max(b[3]-b[1],1))
        if ratio < 1:
            self.scale *= max(0.001,ratio); self.degraded=True

    def _recover_inside(self):
        l,b,r,t=self.bounds(); w,h=self.room
        self.x=max(-l,min(w-r,self.x)); self.y=max(-b,min(h-t,self.y))
        if self.x <= -l+1e-6: self.vx=max(0,self.vx)
        if self.x >= w-r-1e-6: self.vx=min(0,self.vx)
        if self.y >= h-t-1e-6: self.vy=min(0,self.vy)

    def _angle_at(self,t):
        return max(-self.c['maxAngle'],min(self.c['maxAngle'],self.angle+self.rate*(1-math.exp(-4*t))/4))

    def _gaps(self,t):
        l,b,r,top=self.bounds(self._angle_at(t))
        x=self.x+self.vx*t; y=self.y+self.vy*t-0.5*self.c['gravity']*t*t
        w,h=self.room
        return (x+l,w-x-r,y+b,h-y-top)

    def _toi(self,h):
        radius=max(math.hypot(*p) for p in self.c['hull'])*self.scale
        bound=max(abs(self.vx),abs(self.vy)+self.c['gravity']*h)+radius*abs(self.rate)+1e-9
        t=0.0
        for _ in range(96):
            gaps=self._gaps(t)
            # A supported/separating contact at t=0 must not keep firing.
            eligible=[]
            for i,gap in enumerate(gaps):
                vn=(self.vx,-self.vx,self.vy-self.c['gravity']*t,-self.vy+self.c['gravity']*t)[i]
                if gap <= 1e-7 and (vn < -1e-7 or abs(self.rate)>1e-7 or (i==2 and vn<=0)):
                    eligible.append(i)
            if eligible: return t,eligible
            positive=[gap for gap in gaps if gap>1e-7]
            dt=max(1e-9,min(positive,default=bound*h)/bound*0.9)
            if t+dt > h: return None
            t+=dt
        # Never apply an unverified remaining sweep.
        return t,[-1]

    def _move(self,h):
        self.x+=self.vx*h; self.y+=self.vy*h-0.5*self.c['gravity']*h*h
        self.vy-=self.c['gravity']*h
        self.angle=self._angle_at(h); self.rate*=math.exp(-4*h)

    def _impact(self,i,speed,at):
        normal=((1,0),(-1,0),(0,1),(0,-1))[i]
        l,b,r,t=self.bounds()
        point=((self.x+l,self.y),(self.x+r,self.y),(self.x,self.y+b),(self.x,self.y+t))[i]
        self.event_count+=1
        event=Impact(self.event_count,at,normal,point,speed,strength(self.c,speed))
        self.events.append(event); self.last_impact=event
        if i==2:
            self.peak_landing=max(self.peak_landing,speed)
            self.last_landing_time=at; self.last_landing_duration=impact_duration(self.c,event)

    def step(self):
        h=self.c['step']; self.previous=(self.x,self.y,self.angle)
        if self.phase in ('held','normal'): return
        self.phase_time+=h
        if self.phase != 'airborne':
            self.time+=h
            if self.phase=='dizzy' and self.phase_time >= self.dizzy_duration:
                self.phase='recover'; self.phase_time=0
            elif self.phase=='recover' and self.phase_time >= self.c['recoverSeconds']:
                self.phase='normal'; self.phase_time=0
            return
        if self.ground:
            speed=abs(self.vx); stop=min(h,speed/self.c['friction'])
            sign=1 if self.vx>=0 else -1
            self.x+=self.vx*stop-sign*0.5*self.c['friction']*stop*stop
            self.vx=sign*max(0,speed-self.c['friction']*h); self.vy=0
            self.rate=0; self._recover_inside()
            self.stable_time=self.stable_time+h if abs(self.vx)<self.c['settleSpeed'] else 0
            if self.stable_time+1e-9 >= self.c['settleSeconds'] and self.time+h-self.last_landing_time>=self.last_landing_duration:
                self.phase='dizzy'; self.phase_time=0
                q=strength(self.c,self.peak_landing)
                self.dizzy_duration=self.c['dizzyMinSeconds']+(self.c['dizzyMaxSeconds']-self.c['dizzyMinSeconds'])*q
            self.time+=h
            return
        left=h
        for _ in range(8):
            contact=self._toi(left)
            if contact is None:
                self._move(left); left=0; break
            t,indices=contact
            self._move(t); left-=t
            if indices==[-1]:
                self.exhaustions+=1; self.vx=self.vy=self.rate=0; left=0; break
            self.rate=0
            for i in indices:
                vn=(self.vx,-self.vx,self.vy,-self.vy)[i]
                speed=max(0,-vn)
                if speed>1e-6 or (i==2 and self.peak_landing==0): self._impact(i,speed,self.time+h-left)
                e=(self.c['wallRestitution'],self.c['wallRestitution'],self.c['floorRestitution'],self.c['ceilingRestitution'])[i]
                if speed<self.c['bounceThreshold']: e=0
                if i<2: self.vx=abs(self.vx)*e*(1 if i==0 else -1)
                else: self.vy=abs(self.vy)*e*(1 if i==2 else -1)
                if i==2 and self.vy < self.c['bounceThreshold']:
                    self.vy=0; self.ground=True; left=0
            self._recover_inside()
            if left<=1e-10: break
        if left>1e-10:
            self.exhaustions+=1; self.vx=self.vy=self.rate=0
        self.time+=h

    def advance(self,dt):
        self.events=[]
        if not math.isfinite(dt) or dt<=0 or self.phase=='held': return
        if dt>self.c['pauseGap']:
            self.dropped_time+=dt+self.accumulator; self.accumulator=0; return
        self.accumulator+=dt
        n=min(int((self.accumulator+1e-10)/self.c['step']),self.c['maxSteps'])
        for _ in range(n): self.step()
        self.accumulator-=n*self.c['step']
        if self.accumulator>=self.c['step']:
            drop=math.floor(self.accumulator/self.c['step'])*self.c['step']
            self.dropped_time+=drop; self.accumulator-=drop

    def grab(self):
        self.phase='held'; self.events=[]; self.vx=self.vy=self.rate=0; self.accumulator=0

    @property
    def display_position(self):
        f=max(0,min(1,self.accumulator/self.c['step']))
        if self.phase!='airborne': return self.x,self.y,self.angle
        return tuple(a+(b-a)*f for a,b in zip(self.previous,(self.x,self.y,self.angle)))
