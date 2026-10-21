import Foundation
import Testing
@testable import YukioCore

private let throwRoot = URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
private func config() throws -> ThrowConfig { try ThrowConfig.load(from:throwRoot.appendingPathComponent("YukioPlayer/Resources/Assets/interaction/physics.json")) }
@Suite struct ThrowPhysicsTests {
    @Test func ordinaryPlacementIsNotAThrow() throws {
        let c = try config()
        for v in [ThrowVector.zero, ThrowVector(180, 150), ThrowVector(-420, 0), ThrowVector(.nan, 0)] {
            #expect(!DragVelocityTracker.shouldThrow(pointer: v, config: c))
        }
        for v in [ThrowVector(850, 0), ThrowVector(-850, 0), ThrowVector(0, -850), ThrowVector(500, 500)] {
            #expect(DragVelocityTracker.shouldThrow(pointer: v, config: c))
        }
        var tracker = DragVelocityTracker()
        for i in 0...10 { tracker.add(time: Double(i)*0.01, x: Double(i)*12, y: 0) }
        #expect(DragVelocityTracker.shouldThrow(pointer: tracker.velocity(at: 0.1), config: c))
        tracker.add(time: 0.25, x: 120, y: 0)
        #expect(!DragVelocityTracker.shouldThrow(pointer: tracker.velocity(at: 0.25), config: c))
        // A large residual swing still cannot turn a stopped hand into a throw.
        #expect(hypot(DragVelocityTracker.release(pointer: .zero, tangent: ThrowVector(900, 0), config: c).x, 0) > 0)
        #expect(!DragVelocityTracker.shouldThrow(pointer: .zero, config: c))
    }
    @Test func matchesSharedWindowsSolverFixtures() throws {
        let cases = try JSONSerialization.jsonObject(with:Data(contentsOf:throwRoot.appendingPathComponent("tests/interaction/scenarios.json"))) as! [String:Any]
        let traces = try JSONSerialization.jsonObject(with:Data(contentsOf:throwRoot.appendingPathComponent("tests/interaction/python-traces.json"))) as! [String:Any]
        let expected = traces["cases"] as! [[String:Any]]
        for (j,c) in (cases["cases"] as! [[String:Any]]).enumerated() {
            func v(_ name:String) -> ThrowVector { let a=c[name] as! [Double]; return ThrowVector(a[0],a[1]) }
            var p=ThrowPhysics(config:try config(),room:v("room"),position:v("position"),velocity:v("velocity"),angle:c["angle"] as? Double ?? 0,rate:c["rate"] as? Double ?? 0,scale:c["scale"] as? Double ?? 1)
            let rows=expected[j]["rows"] as! [[String:Any]], impacts=expected[j]["events"] as! [[String:Any]]
            var eventIndex=0
            for step in 1...960 {
                p.advance(1.0/120)
                let b=p.bounds()
                #expect(min(p.position.x+b.0,p.position.y+b.1,p.room.x-p.position.x-b.2,p.room.y-p.position.y-b.3) >= -0.0001)
                if (step-1)%4==0 {
                    let r=rows[(step-1)/4]
                    #expect(abs(p.position.x-(r["x"] as! Double))<0.00001)
                    #expect(abs(p.position.y-(r["y"] as! Double))<0.00001)
                    #expect(p.phase.rawValue==r["phase"] as! String)
                }
                for e in p.events {
                    #expect(eventIndex<impacts.count)
                    if eventIndex<impacts.count {
                        #expect(abs(e.time-(impacts[eventIndex]["time"] as! Double))<1.0/120)
                        #expect(abs(e.speed-(impacts[eventIndex]["speed"] as! Double))<0.001)
                    }
                    eventIndex+=1
                }
            }
            #expect(eventIndex==impacts.count); #expect(p.exhaustions==0)
        }
    }
    @Test func analyticFreeFallAndStoppedPointer() throws {
        var p=ThrowPhysics(config:try config(),room:ThrowVector(1440,900),position:ThrowVector(600,650))
        for _ in 0..<24 { p.advance(1.0/120) }
        #expect(abs(p.position.y-602)<1e-8)
        var t=DragVelocityTracker()
        for i in 0...10 { t.add(time:Double(i)*0.01,x:Double(i)*10,y:0) }
        #expect(abs(t.velocity(at:0.1).x-1000)<1e-6)
        t.add(time:0.25,x:100,y:0); #expect(t.velocity(at:0.25) == .zero)
    }
}
