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
    /// 点了“还有 N 条 / 收起”。
    var onToggleExpand: (() -> Void)?
    /// 点了“自动：谁要紧跟谁”。
    var onPickAuto: (() -> Void)?
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
        case .auto: onPickAuto?()
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
///
/// 平时（收起）只有头顶那张气泡，这里画的仅仅是气泡上面一条“还有 N 条”的小条；
/// 点一下展开，才把别的聊天一条一张摊出来，每张点一下就把她换到那条聊天上。
/// 每张卡就是气泡那张卡的样子：上行聊天名（淡色小字），下行在做什么（深色粗字）。
struct CardStackLayout {
    enum Hit: Equatable {
        /// 选这条聊天当主题聊天。
        case card(Int)
        /// 只收起这一张提醒。
        case dismiss(Int)
        /// 回到自动（谁要紧跟谁）。
        case auto
        /// 展开／收起整摞。
        case expand
    }

    /// 和气泡同宽，叠起来是一摞齐的。
    static let width = CardLook.maxWidth
    /// 展开后最多摊几张。
    static let maxExpanded = 8
    private static let gap = CardLook.stackGap
    private static let stripe: CGFloat = 3
    private static let stripeGap: CGFloat = 5
    private static let closeBox: CGFloat = 15
    private static let rowHeight: CGFloat = 20
    /// 两条胶囊各自往里缩多少：画和命中用同一个数。
    private static let autoInset: CGFloat = 10
    private static let pillInset: CGFloat = 26

    static func color(for status: ActivityCard.Status) -> NSColor {
        switch status {
        case .waiting: return NSColor(srgbRed: 0.93, green: 0.62, blue: 0.16, alpha: 1)
        case .failed: return NSColor(srgbRed: 0.84, green: 0.31, blue: 0.29, alpha: 1)
        case .ready: return NSColor(srgbRed: 0.22, green: 0.68, blue: 0.44, alpha: 1)
        case .running: return CardLook.accent
        }
    }

    /// 摊出来的卡（收起时是空的）。
    let shown: [ActivityCard]
    /// 收起时折着的张数。
    let hidden: Int
    let expanded: Bool
    /// 展开时是否给一条“回到自动”。
    let showsAuto: Bool
    let size: NSSize
    /// 每张卡的矩形（左下原点，第 0 张在最下面、挨着气泡）。
    private let cardRects: [NSRect]
    private let autoRect: NSRect?
    private let pillRect: NSRect?

    /// maxHeight：气泡上面还剩多少地方。摊开后放不下就少摊几张（先扔最不要紧的，
    /// 也就是离气泡最远那几张），绝不压到气泡上。
    init(cards: [ActivityCard], expanded: Bool, pinned: Bool = false, maxHeight: CGFloat = .infinity) {
        self.expanded = expanded
        showsAuto = expanded && pinned
        let cardHeight = 2 * CardLook.padY + CardLook.lineHeight(CardLook.titleFont)
            + CardLook.lineGap + CardLook.lineHeight(CardLook.currentFont)
        var room = Self.maxExpanded
        if expanded, maxHeight.isFinite {
            var left = maxHeight - Self.rowHeight                      // “收起”那条
            if showsAuto { left -= Self.rowHeight + Self.gap }
            room = max(1, Int(floor((left + Self.gap) / (cardHeight + Self.gap))))
        }
        shown = expanded ? Array(cards.prefix(min(Self.maxExpanded, room))) : []
        hidden = cards.count - shown.count

        var rects: [NSRect] = []
        var y: CGFloat = 0
        for _ in shown {
            rects.append(NSRect(x: 0, y: y, width: Self.width, height: cardHeight))
            y += cardHeight + Self.gap
        }
        cardRects = rects
        if showsAuto {
            autoRect = NSRect(x: 0, y: y, width: Self.width, height: Self.rowHeight)
            y += Self.rowHeight + Self.gap
        } else {
            autoRect = nil
        }
        // 收起时只剩这一条；展开时它是“收起”。没有别的聊天就整个不画。
        if expanded || hidden > 0 {
            pillRect = NSRect(x: 0, y: y, width: Self.width, height: Self.rowHeight)
            y += Self.rowHeight
        } else {
            pillRect = nil
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
        // 只认画出来的那颗胶囊；两侧的透明边照旧穿透过去。
        if let a = autoRect, Self.pill(a.offsetBy(dx: bounds.minX, dy: bounds.minY), inset: Self.autoInset).contains(point) {
            return .auto
        }
        if let p = pillRect, Self.pill(p.offsetBy(dx: bounds.minX, dy: bounds.minY), inset: Self.pillInset).contains(point) {
            return .expand
        }
        return nil
    }

    func draw(in bounds: NSRect) {
        for (i, card) in shown.enumerated() {
            draw(card, in: cardRects[i].offsetBy(dx: bounds.minX, dy: bounds.minY))
        }
        if let a = autoRect?.offsetBy(dx: bounds.minX, dy: bounds.minY) {
            drawRow(tr("Auto", "自动"), in: a, inset: Self.autoInset)
        }
        if let p = pillRect?.offsetBy(dx: bounds.minX, dy: bounds.minY) {
            drawRow(expanded ? tr("Collapse", "收起") : tr("\(hidden) more", "还有 \(hidden) 条"), in: p, inset: Self.pillInset)
        }
    }

    /// 一条胶囊的实际矩形（画与命中共用）。
    private static func pill(_ rect: NSRect, inset: CGFloat) -> NSRect {
        NSRect(x: rect.minX + inset, y: rect.minY + 1, width: rect.width - 2 * inset, height: rect.height - 2)
    }

    private func drawRow(_ text: String, in rect: NSRect, inset: CGFloat) {
        let pill = Self.pill(rect, inset: inset)
        CardLook.box(pill, radius: pill.height / 2)
        let h = CardLook.lineHeight(CardLook.titleFont)
        CardLook.draw(text, CardLook.titleFont, CardLook.muted,
                      in: NSRect(x: pill.minX, y: pill.midY - h / 2, width: pill.width, height: h), center: true)
    }

    /// 自查用：给出几个代表点（每张卡的正文、✕，自动那条，收起那条）。
    static func probePoints(_ layout: CardStackLayout, in bounds: NSRect) -> [(String, NSPoint)] {
        var out: [(String, NSPoint)] = []
        for (i, rect) in layout.cardRects.enumerated() {
            let r = rect.offsetBy(dx: bounds.minX, dy: bounds.minY)
            out.append(("第\(i)张正文", NSPoint(x: r.midX, y: r.midY)))
            out.append(("第\(i)张的✕", NSPoint(x: closeRect(r).midX, y: closeRect(r).midY)))
        }
        if let a = layout.autoRect { out.append(("自动", NSPoint(x: a.midX, y: a.midY))) }
        if let p = layout.pillRect { out.append(("收起/还有N条", NSPoint(x: p.midX, y: p.midY))) }
        out.append(("空白处", NSPoint(x: bounds.minX + 2, y: bounds.maxY - 1)))
        return out
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
