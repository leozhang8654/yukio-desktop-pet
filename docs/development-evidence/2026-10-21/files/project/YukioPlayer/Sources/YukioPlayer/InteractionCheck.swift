import AppKit
import YukioCore

/// Deterministic replay through the actual native decoder and compositor.
func runInteractionCheck(path: String) -> Never {
    let (catalog,root)=loadCatalogOrExit()
    do {
        let library=try SpriteLibrary(catalog:catalog,assetsRoot:root)
        let config=try ThrowConfig.load(from:root.appendingPathComponent("interaction/physics.json"))
        let out=URL(fileURLWithPath:path)
        try FileManager.default.createDirectory(at:out,withIntermediateDirectories:true)
        let room=NSRect(x:20,y:20,width:920,height:660)
        var timings:[Double]=[], rows:[[String:Any]]=[]
        var escaped=0, viewportEscapes=0
        for (name,velocity) in [("light",ThrowVector(0,0)),("medium",ThrowVector(500,250)),("heavy",ThrowVector(2400,1800))] {
            let start=NSPoint(x:480,y:name=="light" ? 170 : 430)
            let flight=ThrowPlayback(config:config,room:room,center:start,velocity:velocity,angle:0.18,rate:0.4,scale:1)
            var seen=Set<String>(), phases:[String]=[]
            var viewportCenter=flight.worldCenter
            for i in 0..<420 {
                let began=ProcessInfo.processInfo.systemUptime
                flight.physics.advance(1.0/60)
                if flight.physics.phase == .normal { break }
                let (frame,p)=flight.frame(catalog:catalog,library:library,blinkLevel:(i%180)<6 ? i%6 : 0)
                let center=flight.worldCenter, size=flight.canvasSize
                if abs(center.x-viewportCenter.x)>24*flight.physics.scale || abs(center.y-viewportCenter.y)>24*flight.physics.scale { viewportCenter=center }
                let visible=flight.bodyBounds.offsetBy(dx:center.x-viewportCenter.x,dy:center.y-viewportCenter.y)
                if visible.minX < -0.5 || visible.minY < -0.5 || visible.maxX > size.width+0.5 || visible.maxY > size.height+0.5 { viewportEscapes+=1 }
                guard let ctx=CGContext(data:nil,width:960,height:700,bitsPerComponent:8,bytesPerRow:960*4,
                                        space:CGColorSpace(name:CGColorSpace.sRGB)!,bitmapInfo:CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
                let dx=center.x-size.width/2,dy=center.y-size.height/2
                ctx.saveGState();ctx.translateBy(x:dx+p.pivot.x,y:dy+p.pivot.y);ctx.rotate(by:p.angle)
                ctx.translateBy(x:-p.pivot.x,y:-p.pivot.y);ctx.draw(frame.image,in:p.rect);ctx.restoreGState()
                timings.append((ProcessInfo.processInfo.systemUptime-began)*1000)
                // Diagnose significant visible pixels outside the full room.
                if let data=ctx.data {
                    let bytes=data.assumingMemoryBound(to:UInt8.self)
                    for y in 0..<700 {
                        let columns = (y<18 || y>=682) ? Array(0..<960) : Array(0..<18)+Array(942..<960)
                        for x in columns where bytes[y*960*4+x*4+3]>200 { escaped+=1 }
                    }
                }
                let phase=flight.physics.phase.rawValue
                if phases.last != phase { phases.append(phase) }
                let pose=flight.pose(catalog:catalog).0
                if !seen.contains(pose) || i%90==0 {
                    seen.insert(pose)
                    ctx.setStrokeColor(NSColor.systemCyan.cgColor);ctx.setLineWidth(1);ctx.stroke(room)
                    NSGraphicsContext.saveGraphicsState();NSGraphicsContext.current=NSGraphicsContext(cgContext:ctx,flipped:false)
                    let diagnostic="\(name) · \(pose) · \(phase) · t=\(String(format:"%.3f",flight.physics.time)) s · v=(\(Int(flight.physics.velocity.x)),\(Int(flight.physics.velocity.y))) · events=\(flight.physics.eventCount)"
                    diagnostic.draw(at:NSPoint(x:30,y:680),withAttributes:[.font:NSFont.monospacedSystemFont(ofSize:11,weight:.regular),.foregroundColor:NSColor.black])
                    NSGraphicsContext.restoreGraphicsState()
                    _=savePNG(ctx,to:out.appendingPathComponent("\(name)-\(i)-\(pose).png").path)
                }
            }
            rows.append(["case":name,"phases":phases,"events":flight.physics.eventCount,"solverExhaustions":flight.physics.exhaustions])
        }
        timings.sort()
        let info:[String:Any]=["cases":rows,"nativeFrames":timings.count,"p95Ms":timings[Int(Double(timings.count-1)*0.95)],"maxMs":timings.last!,"escapedBeyond2PointsPixels":escaped,"bodyOutsideOverscanViewportFrames":viewportEscapes,"os":ProcessInfo.processInfo.operatingSystemVersionString,"date":ISO8601DateFormatter().string(from:Date()),"note":"Native decoder and offscreen CoreGraphics compositor; desktop input, Dock occlusion and Windows still need separate native checks."]
        let data=try JSONSerialization.data(withJSONObject:info,options:[.prettyPrinted,.sortedKeys]);try data.write(to:out.appendingPathComponent("native-report.json"))
        print(String(decoding:data,as:UTF8.self));exit(escaped==0 && viewportEscapes==0 ? 0 : 1)
    } catch { print(error);exit(1) }
}
