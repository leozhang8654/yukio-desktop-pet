import AppKit

// Finder uses this at its native 720 × 460 size behind the draggable icons.
let size = NSSize(width: 720, height: 460)
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 1440, pixelsHigh: 920,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
bitmap.size = size
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
NSColor(calibratedRed: 0.95, green: 0.97, blue: 0.99, alpha: 1).setFill()
NSRect(origin: .zero, size: size).fill()

func text(_ value: String, x: CGFloat, y: CGFloat, size: CGFloat,
          color: NSColor = .labelColor, weight: NSFont.Weight = .regular) {
    (value as NSString).draw(at: NSPoint(x: x, y: y), withAttributes: [
        .font: NSFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color
    ])
}
let ink = NSColor(calibratedRed: 0.13, green: 0.20, blue: 0.29, alpha: 1)
let muted = NSColor(calibratedRed: 0.38, green: 0.45, blue: 0.54, alpha: 1)
text("安装 Yukio", x: 48, y: 382, size: 30, color: ink, weight: .semibold)
text("将左侧图标拖到右侧「应用程序」即可安装", x: 48, y: 348, size: 17, color: ink)
text("Drag Yukio into Applications to install.", x: 48, y: 322, size: 13, color: muted)

NSColor.white.setFill()
NSBezierPath(roundedRect: NSRect(x: 48, y: 134, width: 624, height: 161),
             xRadius: 24, yRadius: 24).fill()
let arrow = NSBezierPath()
arrow.move(to: NSPoint(x: 326, y: 224))
arrow.line(to: NSPoint(x: 394, y: 224))
arrow.move(to: NSPoint(x: 381, y: 237))
arrow.line(to: NSPoint(x: 394, y: 224))
arrow.line(to: NSPoint(x: 381, y: 211))
arrow.lineWidth = 3
arrow.lineCapStyle = .round
arrow.lineJoinStyle = .round
NSColor(calibratedRed: 0.36, green: 0.58, blue: 0.80, alpha: 1).setStroke()
arrow.stroke()

text("安装后，从「应用程序」打开 Yukio，然后推出此磁盘。", x: 48, y: 108, size: 14, color: ink)
text("首次打开若被阻止：系统设置 → 隐私与安全性 → 仍要打开", x: 48, y: 82, size: 12, color: muted)
text("更新前请先退出 Yukio。仅在信任下载来源时允许打开。", x: 48, y: 60, size: 12, color: muted)
NSGraphicsContext.restoreGraphicsState()
// TIFF records the logical size so Finder displays the 2× artwork at 720 × 460.
try bitmap.representation(using: .tiff, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
