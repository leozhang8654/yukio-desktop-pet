import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor
struct TaskBubbleScalingTests {
    @Test func bubbleFillsItsScaledWindowAtEverySize() {
        _ = NSApplication.shared
        let layout = BubbleLayout(StatusLine(title: "Task", current: "Working", progress: nil))
        let view = BubbleView(frame: .zero)
        view.layout = layout

        for scale in [CGFloat(0.5), 1, 2] {
            let width = Int(layout.size.width * scale)
            let height = Int(layout.size.height * scale)
            view.scale = scale
            view.setFrameSize(NSSize(width: width, height: height))
            let context = CGContext(data: nil, width: width + 4, height: height,
                                    bitsPerComponent: 8, bytesPerRow: (width + 4) * 4,
                                    space: CGColorSpaceCreateDeviceRGB(),
                                    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(cgContext: context, flipped: false)
            view.draw(view.bounds)
            NSGraphicsContext.restoreGraphicsState()
            let pixels = context.data!.assumingMemoryBound(to: UInt8.self)
            let row = (height / 2) * context.bytesPerRow
            #expect(pixels[row + (width - 4) * 4 + 3] > 100)
            #expect(pixels[row + (width + 1) * 4 + 3] == 0)
        }
    }

    @Test func cardHitRegionsFollowTheRenderedScale() {
        let card = ActivityCard(session: "work", title: "Task", subtitle: "Working",
                                status: .running, quietMs: 0)
        let layout = CardStackLayout(cards: [card], expanded: true)
        let view = CardStackView(frame: .zero)
        view.layout = layout
        let points = CardStackLayout.probePoints(layout, in: NSRect(origin: .zero, size: layout.size))

        for scale in [CGFloat(0.5), 1, 2] {
            view.scale = scale
            view.setFrameSize(NSSize(width: layout.size.width * scale,
                                     height: layout.size.height * scale))
            let body = points[0].1
            let close = points[1].1
            #expect(view.hit(at: NSPoint(x: body.x * scale, y: body.y * scale)) == .card(0))
            #expect(view.hit(at: NSPoint(x: close.x * scale, y: close.y * scale)) == .dismiss(0))
        }
    }
}
