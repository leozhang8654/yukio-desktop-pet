import AppKit
import YukioCore

/// 头顶那摞卡片里“别的聊天”那几张：一条聊天一张，叠在气泡上面，点一张就去那条聊天。
///
/// 外观就是头顶气泡那张卡（`CardLook`）：同样的圆角、描边、字号和两行排版，
/// 只多了一条状态色和一个 ✕。独立的透明子窗口，跟着雪绪走；
/// 只有卡片本身接收点击，卡与卡之间的缝隙照样穿透。
final class CardStackPanel: NSPanel {
    let stackView = CardStackView(frame: NSRect(x: 0, y: 0, width: 10, height: 10))

    init() {
        super.init(contentRect: NSRect(x: 0, y: 0, width: 10, height: 10),
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
        contentView = stackView
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

final class CardStackView: NSView {
    var layout: CardStackLayout? {
        didSet { needsDisplay = true }
    }

    /// 点了第几张卡的正文（去那条聊天）。
    var onOpen: ((Int) -> Void)?
    /// 点了第几张卡的 ✕（只收起这张）。
    var onDismiss: ((Int) -> Void)?
    /// 点了“还有 N 条”。
    var onToggleExpand: (() -> Void)?
    /// 在第几张卡上右键（静音那条聊天）。
    var onContextMenu: ((Int, NSEvent) -> Void)?

    override var isOpaque: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        layout?.draw(in: bounds)
    }

    /// 窗口内坐标（左下原点）上有没有可点的东西。
    func hit(at point: NSPoint) -> CardStackLayout.Hit? {
        layout?.hit(at: point, in: bounds)
    }

    override func mouseDown(with event: NSEvent) {
        // 和点雪绪一样，在 mouseUp 里处理。
    }

    override func mouseUp(with event: NSEvent) {
        switch hit(at: convert(event.locationInWindow, from: nil)) {
        case .card(let i): onOpen?(i)
        case .dismiss(let i): onDismiss?(i)
        case .expand: onToggleExpand?()
        case nil: break
        }
    }

    override func rightMouseDown(with event: NSEvent) {
        if case .card(let i)? = hit(at: convert(event.locationInWindow, from: nil)) {
            onContextMenu?(i, event)
        }
    }
}

/// 这摞卡的排版与绘制，与窗口无关（`--cards` 快照也用它）。
/// 每张卡就是气泡那张卡的样子：上行聊天名（淡色小字），下行在做什么（深色粗字）。
struct CardStackLayout {
    enum Hit: Equatable {
        case card(Int)
        case dismiss(Int)
        case expand
    }

    /// 和气泡同宽，叠起来是一摞齐的。
    static let width = CardLook.maxWidth
    /// 收起时最多显示几张，其余折进“还有 N 条”。
    static let collapsedCount = 3
    private static let gap = CardLook.stackGap
    private static let stripe: CGFloat = 3
    private static let stripeGap: CGFloat = 5
    private static let closeBox: CGFloat = 15
    private static let moreHeight: CGFloat = 18

    static func color(for status: ActivityCard.Status) -> NSColor {
        switch status {
        case .waiting: return NSColor(srgbRed: 0.93, green: 0.62, blue: 0.16, alpha: 1)
        case .failed: return NSColor(srgbRed: 0.84, green: 0.31, blue: 0.29, alpha: 1)
        case .ready: return NSColor(srgbRed: 0.22, green: 0.68, blue: 0.44, alpha: 1)
        case .running: return CardLook.accent
        }
    }

    /// 这摞里显示出来的卡（收起时是前几张）。
    let shown: [ActivityCard]
    /// 折进“还有 N 条”的张数。
    let hidden: Int
    let expanded: Bool
    let size: NSSize
    /// 每张卡的矩形（左下原点，第 0 张在最下面、离气泡最近）。
    private let cardRects: [NSRect]
    private let moreRect: NSRect?

    init(cards: [ActivityCard], expanded: Bool) {
        self.expanded = expanded
        let limit = expanded ? cards.count : min(Self.collapsedCount, cards.count)
        shown = Array(cards.prefix(limit))
        hidden = cards.count - shown.count
        let cardHeight = 2 * CardLook.padY + CardLook.lineHeight(CardLook.titleFont)
            + CardLook.lineGap + CardLook.lineHeight(CardLook.currentFont)

        var rects: [NSRect] = []
        var y: CGFloat = 0
        for _ in shown {
            rects.append(NSRect(x: 0, y: y, width: Self.width, height: cardHeight))
            y += cardHeight + Self.gap
        }
        cardRects = rects
        if hidden > 0 || expanded {
            moreRect = NSRect(x: 0, y: y, width: Self.width, height: Self.moreHeight)
            y += Self.moreHeight
        } else {
            moreRect = nil
            if y > 0 { y -= Self.gap }
        }
        size = NSSize(width: Self.width, height: max(0, ceil(y)))
    }

    /// 这摞卡的左下角：和气泡同一竖线上居中，压在气泡上面往上长。
    /// bubbleTop 是气泡的上边（没有气泡时传头顶线），留一条缝接着叠。
    static func origin(size: NSSize, petFrame pet: NSRect, bubbleTop: CGFloat, visible: NSRect) -> NSPoint {
        var x = (pet.midX - size.width / 2).rounded()
        x = min(max(x, visible.minX + 4), visible.maxX - size.width - 4)
        var y = (bubbleTop + CardLook.stackGap).rounded()
        y = min(max(y, visible.minY + 4), visible.maxY - size.height - 4)
        return NSPoint(x: x, y: y)
    }

    func hit(at point: NSPoint, in bounds: NSRect) -> Hit? {
        for (i, rect) in cardRects.enumerated() {
            let r = rect.offsetBy(dx: bounds.minX, dy: bounds.minY)
            guard r.contains(point) else { continue }
            return Self.closeRect(r).contains(point) ? .dismiss(i) : .card(i)
        }
        if let m = moreRect, m.offsetBy(dx: bounds.minX, dy: bounds.minY).contains(point) { return .expand }
        return nil
    }

    func draw(in bounds: NSRect) {
        for (i, card) in shown.enumerated() {
            draw(card, in: cardRects[i].offsetBy(dx: bounds.minX, dy: bounds.minY))
        }
        guard let m = moreRect?.offsetBy(dx: bounds.minX, dy: bounds.minY) else { return }
        let pill = NSRect(x: m.minX + 30, y: m.minY + 1, width: m.width - 60, height: m.height - 2)
        CardLook.box(pill, radius: pill.height / 2)
        let h = CardLook.lineHeight(CardLook.titleFont)
        CardLook.draw(expanded ? "收起" : "还有 \(hidden) 条", CardLook.titleFont, CardLook.muted,
                      in: NSRect(x: pill.minX, y: pill.midY - h / 2, width: pill.width, height: h), center: true)
    }

    private static func closeRect(_ card: NSRect) -> NSRect {
        NSRect(x: card.maxX - closeBox - 1, y: card.maxY - closeBox - 1, width: closeBox, height: closeBox)
    }

    private func draw(_ card: ActivityCard, in rect: NSRect) {
        CardLook.box(rect)
        // 左边一条状态色：橙＝等你回答，红＝出错，绿＝答完了，蓝＝在跑。
        let bar = NSBezierPath(roundedRect: NSRect(x: rect.minX + 4, y: rect.minY + 5,
                                                   width: Self.stripe, height: rect.height - 10),
                               xRadius: Self.stripe / 2, yRadius: Self.stripe / 2)
        Self.color(for: card.status).setFill()
        bar.fill()

        let x = rect.minX + 4 + Self.stripe + Self.stripeGap
        let right = rect.maxX - CardLook.padX
        var top = rect.maxY - CardLook.padY

        // 上行：聊天名（和气泡上行一样的淡色小字），右边让出 ✕。
        let th = CardLook.lineHeight(CardLook.titleFont)
        top -= th
        CardLook.draw(CardLook.singleLine(card.title), CardLook.titleFont, CardLook.muted,
                      in: NSRect(x: x, y: top, width: max(10, right - x - Self.closeBox), height: th))
        drawClose(in: Self.closeRect(rect))

        // 下行：在做什么（和气泡下行一样的深色粗字），右边一个短状态标签。
        top -= CardLook.lineGap
        let ch = CardLook.lineHeight(CardLook.currentFont)
        top -= ch
        let label = card.status.label
        let labelW = ceil(CardLook.width(label, CardLook.smallFont)) + 1
        let lh = CardLook.lineHeight(CardLook.smallFont)
        CardLook.draw(label, CardLook.smallFont, Self.color(for: card.status).shadow(withLevel: 0.25) ?? CardLook.muted,
                      in: NSRect(x: right - labelW, y: top + (ch - lh) / 2, width: labelW, height: lh))
        CardLook.draw(CardLook.singleLine(card.subtitle), CardLook.currentFont, CardLook.ink,
                      in: NSRect(x: x, y: top, width: max(10, right - x - labelW - 6), height: ch))
    }

    private func drawClose(in box: NSRect) {
        let cross = NSBezierPath()
        let inset: CGFloat = 5
        cross.move(to: NSPoint(x: box.minX + inset, y: box.minY + inset))
        cross.line(to: NSPoint(x: box.maxX - inset, y: box.maxY - inset))
        cross.move(to: NSPoint(x: box.minX + inset, y: box.maxY - inset))
        cross.line(to: NSPoint(x: box.maxX - inset, y: box.minY + inset))
        cross.lineWidth = 1.2
        cross.lineCapStyle = .round
        CardLook.muted.withAlphaComponent(0.7).setStroke()
        cross.stroke()
    }
}

extension Array {
    /// 这摞卡的内容随时在变，按下标取时宁可拿到 nil 也不要越界。
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
