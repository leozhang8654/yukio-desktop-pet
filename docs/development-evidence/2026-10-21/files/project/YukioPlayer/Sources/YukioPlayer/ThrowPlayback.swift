import AppKit
import YukioCore

/// Pure physics plus a bounded native presentation. No task/answer state lives here.
final class ThrowPlayback {
    var physics: ThrowPhysics
    let room: NSRect
    var caught = false
    var frozen: (SpriteLibrary.Frame, SpritePlacement)?
    var lastTime = ProcessInfo.processInfo.systemUptime
    private(set) var bodyBounds = NSRect.zero
    private var carry: SpriteLibrary.Frame?
    private var hullImage: CGImage?
    private var hullPoints: [NSPoint] = []

    init(config: ThrowConfig, room: NSRect, center: NSPoint, velocity: ThrowVector,
         angle: Double, rate: Double, scale: CGFloat, carry: SpriteLibrary.Frame? = nil, sessionID: Int = 1) {
        self.room=room; self.carry=carry
        physics=ThrowPhysics(config:config,room:ThrowVector(room.width,room.height),
                             position:ThrowVector(center.x-room.minX,center.y-room.minY),velocity:velocity,
                             angle:angle,rate:rate,scale:scale,screenID:NSStringFromRect(room),sessionID:sessionID)
    }
    func advance() {
        let now=ProcessInfo.processInfo.systemUptime, dt=now-lastTime; lastTime=now
        if !caught { physics.advance(dt) }
    }
    var worldCenter: NSPoint {
        let p=physics.displayPosition.0
        return NSPoint(x:room.minX+p.x,y:room.minY+p.y)
    }
    var canvasSize: NSSize { NSSize(width:360*physics.scale,height:360*physics.scale) }
    func pose(catalog: AnimationCatalog) -> (String,Int) {
        var name="airborne", seconds=physics.time
        if physics.phase == .dizzy {
            name=physics.phaseTime<physics.config.dizzyIntroSeconds ? "dizzy-intro" : "dizzy-loop"
            seconds=physics.phaseTime
            if name=="dizzy-loop" {
                let span=max(0.1,physics.dizzyDuration-physics.config.dizzyIntroSeconds)
                let loops=max(1,floor(span/0.9+0.5))
                seconds=(physics.phaseTime-physics.config.dizzyIntroSeconds)*loops*0.9/span
            }
        } else if physics.phase == .recover {
            name="recover"; seconds=physics.phaseTime
        } else if let hit=physics.lastImpact {
            let age=physics.time-hit.time
            if age < physics.config.impactDuration(hit) {
                name=hit.normal.y>0 ? "landing-impact" : "wall-impact"
                if hit.strength < 1.0/3 { name += "_light" } else if hit.strength < 2.0/3 { name += "_medium" }
                seconds=age*(hit.normal.y>0 ? 0.24 : 0.14)/physics.config.impactDuration(hit)
            }
        }
        let id="interaction_"+name
        guard let spec=catalog.specs[id] else { return (AnimationCatalog.heldID,0) }
        var timeline=SpriteTimeline(spec:spec,now:0); timeline.advance(to:max(0,seconds)*1000)
        return (id,timeline.frame)
    }
    func frame(catalog: AnimationCatalog, library: SpriteLibrary, blinkLevel: Int = 0) -> (SpriteLibrary.Frame,SpritePlacement) {
        if caught, let frozen { return frozen }
        let (id,index)=pose(catalog:catalog), c=physics.config, s=physics.scale
        let spec=catalog.specs[id]!
        let isInteraction=id.hasPrefix("interaction_")
        let pad=isInteraction ? 12.0 : 0.0
        let size=canvasSize, pivot=NSPoint(x:size.width/2,y:size.height/2)
        let rect=NSRect(x:pivot.x-(c.center[0]+pad)*s,
                        y:pivot.y-(Double(spec.frameHeight)-c.center[1]-pad)*s,
                        width:Double(spec.frameWidth)*s,height:Double(spec.frameHeight)*s)
        var a=physics.displayPosition.1
        // Ease inherited tilt back around the planted foot; the collider remains
        // authoritative for the ground baseline, including transparent padding.
        if physics.phase == .dizzy { a *= max(0,1-physics.phaseTime/physics.config.dizzyIntroSeconds) }
        if physics.phase == .recover { a=0 }
        var shift=0.0
        if physics.ground { shift=physics.bounds().1-physics.bounds(angle:a).1 }
        var placement=SpritePlacement(rect:rect.offsetBy(dx:0,dy:shift),pivot:NSPoint(x:pivot.x,y:pivot.y+shift),angle:a)
        if physics.phase == .airborne, let hit=physics.lastImpact, hit.normal.y<=0 {
            let u=(physics.time-hit.time)/c.impactDuration(hit)
            if u>=0 && u<1 {
                let pulse=1.5*s*hit.strength*sin(.pi*u)
                placement.rect=placement.rect.offsetBy(dx:hit.normal.x*pulse,dy:hit.normal.y*pulse)
            }
        }
        let image=(id=="interaction_airborne" ? carry : nil) ?? library.frame(id,index,blinkLevel:blinkLevel)
        if hullImage !== image.image {
            hullImage=image.image; hullPoints=[]
            if carry == nil, let runs=spec.hitRuns, runs.indices.contains(index) {
                for r in runs[index] {
                    hullPoints.append(NSPoint(x:Double(r[1])/Double(image.width),y:1-Double(r[0]+1)/Double(image.height)))
                    hullPoints.append(NSPoint(x:Double(r[2])/Double(image.width),y:1-Double(r[0])/Double(image.height)))
                }
            } else { for y in 0..<image.height {
                let xs=(0..<image.width).filter { image.alpha[y*image.width+$0]>24 }
                if let l=xs.first, let r=xs.last {
                    hullPoints.append(NSPoint(x:Double(l)/Double(image.width),y:1-Double(y+1)/Double(image.height)))
                    hullPoints.append(NSPoint(x:Double(r+1)/Double(image.width),y:1-Double(y)/Double(image.height)))
                }
            }
        }
        }
        var minX=Double.infinity,minY=minX,maxX = -minX,maxY = -minX
        for p in hullPoints {
            let dx=placement.rect.minX+p.x*placement.rect.width-placement.pivot.x
            let dy=placement.rect.minY+p.y*placement.rect.height-placement.pivot.y
            let x=placement.pivot.x+dx*cos(a)-dy*sin(a), y=placement.pivot.y+dx*sin(a)+dy*cos(a)
            minX=min(minX,x);maxX=max(maxX,x);minY=min(minY,y);maxY=max(maxY,y)
        }
        let origin=NSPoint(x:worldCenter.x-size.width/2,y:worldCenter.y-size.height/2)
        let correctionX=max(room.minX-origin.x-minX,min(0,room.maxX-origin.x-maxX))
        let correctionY=physics.ground ? room.minY-origin.y-minY : max(room.minY-origin.y-minY,min(0,room.maxY-origin.y-maxY))
        placement.rect=placement.rect.offsetBy(dx:correctionX,dy:correctionY)
        placement.pivot.x+=correctionX;placement.pivot.y+=correctionY
        bodyBounds=NSRect(x:minX+correctionX,y:minY+correctionY,width:maxX-minX,height:maxY-minY)
        return (image,placement)
    }
}
