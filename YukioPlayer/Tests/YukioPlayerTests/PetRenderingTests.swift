import AppKit
import Testing
@testable import YukioPlayer

@Suite @MainActor
struct PetRenderingTests {
    private func bitmap(width: Int, height: Int) -> CGContext {
        CGContext(data: nil, width: width, height: height, bitsPerComponent: 8,
                  bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    }

    private func frame() -> SpriteLibrary.Frame {
        let context = bitmap(width: 20, height: 20)
        context.setFillColor(CGColor(red: 1, green: 0, blue: 0, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: 20, height: 20))
        return .init(image: context.makeImage()!, width: 20, height: 20,
                     alpha: Array(repeating: 255, count: 400))
    }

    private func draw(_ view: PetView, into context: CGContext) {
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(cgContext: context, flipped: false)
        view.draw(view.bounds)
        NSGraphicsContext.restoreGraphicsState()
    }

    private func alpha(_ context: CGContext, _ x: Int, _ y: Int) -> UInt8 {
        context.data!.assumingMemoryBound(to: UInt8.self)[y * context.bytesPerRow + x * 4 + 3]
    }

    @Test func paintsBothEdgesAtEverySupportedSizeAndBackingScale() {
        let sprite = frame()
        let view = PetView(frame: .zero)
        for size in [NSSize(width: 96, height: 104), NSSize(width: 240, height: 260),
                     NSSize(width: 384, height: 416)] {
            view.setFrameSize(size)
            view.show(sprite, .filling(view.bounds))
            for backingScale in [1, 2] {
                let width = Int(size.width) * backingScale
                let height = Int(size.height) * backingScale
                let context = bitmap(width: width, height: height)
                context.scaleBy(x: CGFloat(backingScale), y: CGFloat(backingScale))
                draw(view, into: context)
                for (x, y) in [(1, 1), (width - 2, 1), (1, height - 2), (width - 2, height - 2)] {
                    #expect(alpha(context, x, y) == 255)
                }
            }
        }
    }

    @Test func clearsOldSilhouetteWhenFrameMoves() {
        let view = PetView(frame: NSRect(x: 0, y: 0, width: 80, height: 80))
        let context = bitmap(width: 80, height: 80)
        let sprite = frame()
        view.show(sprite, .filling(view.bounds))
        draw(view, into: context)
        #expect(alpha(context, 10, 10) == 255)
        view.show(sprite, SpritePlacement(rect: NSRect(x: 30, y: 30, width: 20, height: 20),
                                          pivot: NSPoint(x: 40, y: 40), angle: 0))
        draw(view, into: context)
        #expect(alpha(context, 10, 10) == 0)
        #expect(alpha(context, 40, 40) == 255)
        #expect(alpha(context, 70, 70) == 0)
    }

    @Test func swingPixelsMatchClickThroughGeometry() {
        let view = PetView(frame: NSRect(x: 0, y: 0, width: 100, height: 100))
        for angle in [-CGFloat.pi / 9, CGFloat.pi / 9] {
            let context = bitmap(width: 100, height: 100)
            view.show(frame(), SpritePlacement(rect: NSRect(x: 40, y: 20, width: 20, height: 40),
                                               pivot: NSPoint(x: 50, y: 75), angle: angle))
            draw(view, into: context)
            var count = 0, sumX = 0
            for y in 0..<100 {
                for x in 0..<100 where alpha(context, x, y) > 250 {
                    // Bitmap rows are top-down; view/hit-test coordinates are bottom-up.
                    let point = NSPoint(x: CGFloat(x) + 0.5, y: 100 - CGFloat(y) - 0.5)
                    #expect(view.isOpaque(at: point))
                    count += 1
                    sumX += x
                }
            }
            #expect(count > 600)
            #expect((Double(sumX) / Double(max(count, 1)) - 49.5) * Double(angle) > 0)
        }
    }

    @Test func backingStoreIncludesWholeSpriteAfterWindowResize() throws {
        _ = NSApplication.shared
        let view = PetView(frame: NSRect(x: 0, y: 0, width: 80, height: 80))
        let panel = PetPanel(size: view.frame.size)
        panel.contentView = view
        defer { panel.close() }
        let sprite = frame()
        // Reuse the same CGImage through grow/shrink cycles, as happens when
        // dragging, dropping, and resizing a held or paused animation.
        for size in [NSSize(width: 80, height: 80), NSSize(width: 200, height: 240),
                     NSSize(width: 100, height: 100)] {
            panel.setContentSize(size)
            view.show(sprite, .filling(view.bounds))
            view.viewDidChangeBackingProperties()
            let bitmap = try #require(view.bitmapImageRepForCachingDisplay(in: view.bounds))
            view.cacheDisplay(in: view.bounds, to: bitmap)
            for (x, y) in [(1, 1), (bitmap.pixelsWide - 2, bitmap.pixelsHigh - 2)] {
                let color = try #require(bitmap.colorAt(x: x, y: y))
                #expect(color.alphaComponent > 0.99)
            }
        }
    }
}
