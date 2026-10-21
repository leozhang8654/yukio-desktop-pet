import Foundation

public struct ThrowVector: Codable, Equatable, Sendable {
    public var x: Double
    public var y: Double
    public init(_ x: Double, _ y: Double) { self.x=x; self.y=y }
    public static let zero = ThrowVector(0,0)
}

/// The only tuning source is Assets/interaction/physics.json, shared with Windows.
public struct ThrowConfig: Decodable, Sendable {
    public let version: Int
    public let units: String
    public let step: Double, maxSteps: Int, pauseGap: Double, gravity: Double
    public let pointerGain: Double, lowSpeed: Double, maxSpeed: Double
    public let throwMinSpeed: Double?
    public var minimumThrowSpeed: Double { throwMinSpeed ?? 650 }
    public let wallRestitution: Double, ceilingRestitution: Double, floorRestitution: Double
    public let bounceThreshold: Double, friction: Double, settleSpeed: Double, settleSeconds: Double
    public let maxAngle: Double, recoverSeconds: Double
    public let strengthMinSpeed: Double, strengthMaxSpeed: Double, dizzyMinSeconds: Double, dizzyMaxSeconds: Double
    public let landingMinSeconds: Double, landingMaxSeconds: Double, wallMinSeconds: Double, wallMaxSeconds: Double, dizzyIntroSeconds: Double
    public func strength(_ speed: Double) -> Double { max(0,min(1,(speed-strengthMinSpeed)/(strengthMaxSpeed-strengthMinSpeed))) }
    public func impactDuration(_ hit: ThrowImpact) -> Double {
        hit.normal.y > 0 ? landingMinSeconds+(landingMaxSeconds-landingMinSeconds)*hit.strength : wallMinSeconds+(wallMaxSeconds-wallMinSeconds)*hit.strength
    }
    public let center: [Double], foot: [Double], frame: [Double], hull: [[Double]]
    public static func load(from url: URL) throws -> Self {
        let c = try JSONDecoder().decode(Self.self, from: Data(contentsOf: url))
        guard c.version == 1, c.units == "logical-y-up-seconds", c.hull.count >= 3,
              c.hull.allSatisfy({ $0.count == 2 && $0.allSatisfy(\.isFinite) }), c.step > 0,
              c.gravity > 0, c.friction > 0, c.maxSteps > 0, c.center.count == 2, c.center.allSatisfy(\.isFinite),
              c.minimumThrowSpeed.isFinite, c.minimumThrowSpeed > 0,
              c.strengthMaxSpeed > c.strengthMinSpeed, c.dizzyMinSeconds > 0, c.dizzyMaxSeconds >= c.dizzyMinSeconds,
              [c.wallRestitution,c.ceilingRestitution,c.floorRestitution].allSatisfy({ $0 >= 0 && $0 < 1 }) else {
            throw CatalogError.invalid("interaction physics")
        }
        return c
    }
}

public struct ThrowImpact: Sendable {
    public let eventID: Int, time: Double, normal: ThrowVector, point: ThrowVector, speed: Double, strength: Double
}

/// Convex silhouette against four planes. Conservative advancement bounds both
/// translation and angular sweep; unverified remaining motion is never applied.
public struct ThrowPhysics: Sendable {
    public enum Phase: String, Sendable { case airborne, held, dizzy, recover, normal }
    public let config: ThrowConfig
    public let room: ThrowVector, screenID: String, sessionID: Int
    public private(set) var position: ThrowVector, velocity: ThrowVector
    public private(set) var angle: Double, rate: Double, scale: Double
    public private(set) var phase: Phase = .airborne
    public private(set) var time = 0.0, phaseTime = 0.0, accumulator = 0.0, droppedTime = 0.0
    public private(set) var ground = false, degraded = false
    public private(set) var events: [ThrowImpact] = [], lastImpact: ThrowImpact?
    public private(set) var eventCount = 0, exhaustions = 0
    private var stableTime = 0.0, peakLanding = 0.0
    public private(set) var dizzyDuration = 0.75
    private var lastLandingTime = -Double.infinity
    private var lastLandingDuration = 0.0
    private var previous: (ThrowVector,Double)

    public init(config: ThrowConfig, room: ThrowVector, position: ThrowVector, velocity: ThrowVector = .zero,
                angle: Double = 0, rate: Double = 0, scale: Double = 1, screenID: String = "", sessionID: Int = 1) {
        self.config=config; self.room=room; self.position=position; self.velocity=velocity
        self.angle=max(-config.maxAngle,min(config.maxAngle,angle)); self.rate=max(-2,min(2,rate))
        self.scale=scale; self.screenID=screenID; self.sessionID=sessionID
        previous=(position,self.angle)
        let b=bounds()
        let ratio=min(1,(room.x-2)/max(b.2-b.0,1),(room.y-2)/max(b.3-b.1,1))
        if ratio<1 { self.scale *= max(0.001,ratio); degraded=true }
        recoverInside()
        previous=(self.position,self.angle)
    }

    public func bounds(angle a: Double? = nil) -> (Double,Double,Double,Double) {
        let a=a ?? angle, co=cos(a), si=sin(a)
        var l=Double.infinity,b=l,r = -l,t = -l
        for p in config.hull {
            let x=scale*(p[0]*co-p[1]*si), y=scale*(p[0]*si+p[1]*co)
            l=min(l,x); b=min(b,y); r=max(r,x); t=max(t,y)
        }
        return (l,b,r,t)
    }
    private mutating func recoverInside() {
        let (l,b,r,t)=bounds()
        position.x=max(-l,min(room.x-r,position.x)); position.y=max(-b,min(room.y-t,position.y))
        if position.x <= -l+1e-6 { velocity.x=max(0,velocity.x) }
        if position.x >= room.x-r-1e-6 { velocity.x=min(0,velocity.x) }
        if position.y >= room.y-t-1e-6 { velocity.y=min(0,velocity.y) }
    }
    private func angleAt(_ t: Double) -> Double {
        max(-config.maxAngle,min(config.maxAngle,angle+rate*(1-exp(-4*t))/4))
    }
    private func gaps(_ t: Double) -> [Double] {
        let (l,b,r,top)=bounds(angle:angleAt(t))
        let x=position.x+velocity.x*t, y=position.y+velocity.y*t-0.5*config.gravity*t*t
        return [x+l,room.x-x-r,y+b,room.y-y-top]
    }
    private func toi(_ h: Double) -> (Double,[Int])? {
        let radius=(config.hull.map { hypot($0[0],$0[1]) }.max() ?? 0)*scale
        let bound=max(abs(velocity.x),abs(velocity.y)+config.gravity*h)+radius*abs(rate)+1e-9
        var t=0.0
        for _ in 0..<96 {
            let gaps=gaps(t), vy=velocity.y-config.gravity*t
            let vn=[velocity.x,-velocity.x,vy,-vy]
            let hits=(0..<4).filter { gaps[$0]<=1e-7 && (vn[$0] < -1e-7 || abs(rate)>1e-7 || ($0==2 && vn[$0]<=0)) }
            if !hits.isEmpty { return (t,hits) }
            let dt=max(1e-9,(gaps.filter { $0>1e-7 }.min() ?? bound*h)/bound*0.9)
            if t+dt>h { return nil }
            t+=dt
        }
        return (t,[-1])
    }
    private mutating func move(_ h: Double) {
        position.x+=velocity.x*h; position.y+=velocity.y*h-0.5*config.gravity*h*h
        velocity.y-=config.gravity*h
        angle=angleAt(h); rate*=exp(-4*h)
    }
    private mutating func impact(_ i: Int, speed: Double, at: Double) {
        let normals=[ThrowVector(1,0),ThrowVector(-1,0),ThrowVector(0,1),ThrowVector(0,-1)]
        let (l,b,r,t)=bounds()
        let points=[ThrowVector(position.x+l,position.y),ThrowVector(position.x+r,position.y),
                    ThrowVector(position.x,position.y+b),ThrowVector(position.x,position.y+t)]
        eventCount+=1
        let e=ThrowImpact(eventID:eventCount,time:at,normal:normals[i],point:points[i],speed:speed,strength:config.strength(speed))
        events.append(e); lastImpact=e
        if i==2 { peakLanding=max(peakLanding,speed); lastLandingTime=at; lastLandingDuration=config.impactDuration(e) }
    }
    public mutating func step() {
        let h=config.step; previous=(position,angle)
        if phase == .held || phase == .normal { return }
        phaseTime+=h
        if phase != .airborne {
            time+=h
            if phase == .dizzy && phaseTime>=dizzyDuration { phase = .recover; phaseTime=0 }
            else if phase == .recover && phaseTime>=config.recoverSeconds { phase = .normal; phaseTime=0 }
            return
        }
        if ground {
            let speed=abs(velocity.x), stop=min(h,speed/config.friction), sign=velocity.x>=0 ? 1.0 : -1.0
            position.x+=velocity.x*stop-sign*0.5*config.friction*stop*stop
            velocity.x=sign*max(0,speed-config.friction*h); velocity.y=0; rate=0
            recoverInside()
            stableTime=abs(velocity.x)<config.settleSpeed ? stableTime+h : 0
            if stableTime+1e-9>=config.settleSeconds && time+h-lastLandingTime>=lastLandingDuration {
                phase = .dizzy; phaseTime=0; dizzyDuration=config.dizzyMinSeconds+(config.dizzyMaxSeconds-config.dizzyMinSeconds)*config.strength(peakLanding)
            }
            time+=h; return
        }
        var left=h
        for _ in 0..<8 {
            guard let (t,indices)=toi(left) else { move(left); left=0; break }
            move(t); left-=t
            if indices == [-1] { exhaustions+=1; velocity = .zero; rate=0; left=0; break }
            rate=0
            for i in indices {
                let vn=[velocity.x,-velocity.x,velocity.y,-velocity.y][i], speed=max(0,-vn)
                if speed>1e-6 || (i==2 && peakLanding==0) { impact(i,speed:speed,at:time+h-left) }
                var e=[config.wallRestitution,config.wallRestitution,config.floorRestitution,config.ceilingRestitution][i]
                if speed<config.bounceThreshold { e=0 }
                if i<2 { velocity.x=abs(velocity.x)*e*(i==0 ? 1 : -1) }
                else { velocity.y=abs(velocity.y)*e*(i==2 ? 1 : -1) }
                if i==2 && velocity.y<config.bounceThreshold { velocity.y=0; ground=true; left=0 }
            }
            recoverInside()
            if left<=1e-10 { break }
        }
        if left>1e-10 { exhaustions+=1; velocity = .zero; rate=0 }
        time+=h
    }
    public mutating func advance(_ dt: Double) {
        events=[]
        guard dt.isFinite, dt>0, phase != .held else { return }
        if dt>config.pauseGap { droppedTime+=dt+accumulator; accumulator=0; return }
        accumulator+=dt
        let n=min(Int((accumulator+1e-10)/config.step),config.maxSteps)
        for _ in 0..<n { step() }
        accumulator-=Double(n)*config.step
        if accumulator>=config.step {
            let drop=floor(accumulator/config.step)*config.step
            droppedTime+=drop; accumulator-=drop
        }
    }
    public mutating func grab() { phase = .held; events=[]; velocity = .zero; rate=0; accumulator=0 }
    public var displayPosition: (ThrowVector,Double) {
        guard phase == .airborne else { return (position,angle) }
        let f=max(0,min(1,accumulator/config.step))
        return (ThrowVector(previous.0.x+(position.x-previous.0.x)*f,previous.0.y+(position.y-previous.0.y)*f),previous.1+(angle-previous.1)*f)
    }
}
