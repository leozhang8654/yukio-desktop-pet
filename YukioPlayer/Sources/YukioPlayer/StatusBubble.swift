import AppKit
import YukioCore

/// 头顶小气泡：上行大任务（标题），下行当前任务或活动；有任务清单时右侧显示进度，底部一条细进度条。
/// 独立的透明子窗口：点击穿透，随雪绪移动，没有任务时淡出。
final class BubblePanel: NSPanel {
    let bubbleView = BubbleView(frame: NSRect(x: 0, y: 0, width: 80, height: 30))

    init() {
        super.init(contentRect: NSRect(x: 0, y: 0, width: 80, height: 30),
                   styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        isMovable = false
        ignoresMouseEvents = true
        alphaValue = 0
        contentView = bubbleView
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

final class BubbleView: NSView {
    var layout: BubbleLayout? {
        didSet { needsDisplay = true }
    }

    override var isOpaque: Bool { false }

    override func draw(_ dirtyRect: NSRect) {
        layout?.draw(in: bounds)
    }
}

/// 头顶那摞卡片的统一外观。最下面一张是这个气泡（当前那条聊天），
/// 上面叠的“别的聊天”用同一套圆角、描边、字号和颜色，不另起一套样子。
enum CardLook {
    static let maxWidth: CGFloat = 180
    static let minWidth: CGFloat = 64
    static let padX: CGFloat = 8
    static let padY: CGFloat = 5
    static let lineGap: CGFloat = 1
    static let radius: CGFloat = 7
    /// 叠起来时两张卡之间的缝。
    static let stackGap: CGFloat = 4

    static let titleFont = NSFont.systemFont(ofSize: 10, weight: .medium)
    static let currentFont = NSFont.systemFont(ofSize: 11.5, weight: .semibold)
    static let smallFont = NSFont.monospacedDigitSystemFont(ofSize: 10, weight: .medium)
    /// 制服的深蓝与眼睛的蓝。
    static let ink = NSColor(srgbRed: 0.12, green: 0.16, blue: 0.27, alpha: 1)
    static let muted = NSColor(srgbRed: 0.38, green: 0.44, blue: 0.56, alpha: 1)
    static let accent = NSColor(srgbRed: 0.24, green: 0.58, blue: 0.90, alpha: 1)

    /// 卡片的底：半透明白 + 一圈淡描边。
    static func box(_ rect: NSRect, radius: CGFloat = radius) {
        let path = NSBezierPath(roundedRect: rect.insetBy(dx: 0.5, dy: 0.5), xRadius: radius, yRadius: radius)
        NSColor(white: 1, alpha: 0.94).setFill()
        path.fill()
        ink.withAlphaComponent(0.16).setStroke()
        path.lineWidth = 1
        path.stroke()
    }

    /// 用含中文的样本量行高：中文字形来自后备字体，行高比西文字体的上下伸部大。
    static func lineHeight(_ font: NSFont) -> CGFloat {
        ceil(("雪绪Ag" as NSString).size(withAttributes: [.font: font]).height)
    }

    static func width(_ s: String, _ font: NSFont) -> CGFloat {
        (s as NSString).size(withAttributes: [.font: font]).width
    }

    static func draw(_ s: String, _ font: NSFont, _ color: NSColor, in rect: NSRect, center: Bool = false) {
        let para = NSMutableParagraphStyle()
        para.lineBreakMode = .byTruncatingTail
        if center { para.alignment = .center }
        (s as NSString).draw(in: rect, withAttributes: [.font: font, .foregroundColor: color, .paragraphStyle: para])
    }

    static func singleLine(_ s: String) -> String {
        s.split(whereSeparator: \.isNewline).joined(separator: " ")
    }
}

/// 气泡的排版与绘制，与窗口无关（--bubble 快照也用它）。这也是头顶那摞卡片里最下面的一张。
struct BubbleLayout {
    static let maxWidth = CardLook.maxWidth
    static let minWidth = CardLook.minWidth
    private static let padX = CardLook.padX
    private static let padY = CardLook.padY
    private static let lineGap = CardLook.lineGap
    private static let barHeight: CGFloat = 2.5
    private static let barGap: CGFloat = 4
    private static let progressGap: CGFloat = 6
    private static let radius = CardLook.radius

    private static let titleFont = CardLook.titleFont
    private static let currentFont = CardLook.currentFont
    private static let progressFont = CardLook.smallFont
    private static let ink = CardLook.ink
    private static let muted = CardLook.muted
    private static let accent = CardLook.accent

    let title: String?
    let current: String
    let progress: StatusLine.Progress?
    let size: NSSize
    /// 进度数字的宽度。排版与绘制用同一个取整后的值，避免小数舍入把本来放得下的字截掉。
    private let progressWidth: CGFloat

    init(_ line: StatusLine) {
        title = line.title.map(Self.singleLine)
        current = Self.singleLine(line.current)
        progress = line.progress
        progressWidth = line.progress.map { ceil(Self.width(Self.progressText($0), Self.progressFont)) } ?? 0
        let titleW = title.map { ceil(Self.width($0, Self.titleFont)) + 1 } ?? 0
        var currentW = ceil(Self.width(current, Self.currentFont)) + 1
        if progress != nil { currentW += Self.progressGap + progressWidth }
        let w = min(Self.maxWidth, max(Self.minWidth, max(titleW, currentW) + 2 * Self.padX))
        var h = 2 * Self.padY + Self.lineHeight(Self.currentFont)
        if title != nil { h += Self.lineHeight(Self.titleFont) + Self.lineGap }
        if progress != nil { h += Self.barGap + Self.barHeight }
        size = NSSize(width: w, height: ceil(h))
    }

    /// 气泡左下角：水平居中于雪绪，底边贴在头顶线上方。headTop：人物最高点距窗口顶的点数（已乘缩放）。
    static func origin(size: NSSize, petFrame pet: NSRect, headTop: CGFloat) -> NSPoint {
        NSPoint(x: (pet.midX - size.width / 2).rounded(), y: (pet.maxY - headTop + 3).rounded())
    }

    func draw(in bounds: NSRect) {
        CardLook.box(bounds)

        let x = bounds.minX + Self.padX
        let innerW = bounds.width - 2 * Self.padX
        var top = bounds.maxY - Self.padY
        if let title {
            let h = Self.lineHeight(Self.titleFont)
            top -= h
            Self.draw(title, Self.titleFont, Self.muted, in: NSRect(x: x, y: top, width: innerW, height: h))
            top -= Self.lineGap
        }
        let h = Self.lineHeight(Self.currentFont)
        top -= h
        var textW = innerW
        if let p = progress {
            let ph = Self.lineHeight(Self.progressFont)
            Self.draw(Self.progressText(p), Self.progressFont, Self.muted,
                      in: NSRect(x: bounds.maxX - Self.padX - progressWidth, y: top + (h - ph) / 2,
                                 width: progressWidth, height: ph))
            textW -= progressWidth + Self.progressGap
        }
        Self.draw(current, Self.currentFont, Self.ink, in: NSRect(x: x, y: top, width: textW, height: h))
        if let p = progress, p.total > 0 {
            top -= Self.barGap + Self.barHeight
            let r = Self.barHeight / 2
            Self.ink.withAlphaComponent(0.10).setFill()
            NSBezierPath(roundedRect: NSRect(x: x, y: top, width: innerW, height: Self.barHeight), xRadius: r, yRadius: r).fill()
            let done = innerW * CGFloat(min(p.done, p.total)) / CGFloat(p.total)
            if done > 0 {
                Self.accent.setFill()
                NSBezierPath(roundedRect: NSRect(x: x, y: top, width: max(done, Self.barHeight), height: Self.barHeight),
                             xRadius: r, yRadius: r).fill()
            }
        }
    }

    private static func singleLine(_ s: String) -> String { CardLook.singleLine(s) }

    private static func progressText(_ p: StatusLine.Progress) -> String { "\(p.done)/\(p.total)" }

    private static func lineHeight(_ font: NSFont) -> CGFloat { CardLook.lineHeight(font) }

    private static func width(_ s: String, _ font: NSFont) -> CGFloat { CardLook.width(s, font) }

    private static func draw(_ s: String, _ font: NSFont, _ color: NSColor, in rect: NSRect) {
        CardLook.draw(s, font, color, in: rect)
    }
}
