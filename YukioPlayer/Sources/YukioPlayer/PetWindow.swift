import AppKit

/// 透明、置顶、不抢焦点的单实例窗口。
final class PetPanel: NSPanel {
    init(size: NSSize) {
        super.init(contentRect: NSRect(origin: .zero, size: size),
                   styleMask: [.borderless, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        isMovable = false
        // 默认点击穿透；鼠标移到不透明像素上时由控制器打开。
        ignoresMouseEvents = true
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

/// 一帧图在视图里的摆放：画在哪块矩形里、绕哪一点转、转了多少。
/// 平时就是铺满整个窗口；被大手拎着时图更高、还要绕抓手那一点晃，窗口也跟着放大。
struct SpritePlacement: Equatable {
    /// 视图坐标（左下原点）里图所占的矩形。
    var rect: NSRect
    /// 旋转中心，视图坐标。
    var pivot: NSPoint
    /// 弧度。正数表示脚偏向右边。
    ///
    /// 图层坐标系 y 向上，`CATransform3DMakeRotation` 的正角是逆时针。脚在抓手点**下方**，
    /// 所以让脚往右甩要用**正角**：钟面上指向 6 点的指针，顺时针是往 7、8、9（也就是往左）走，
    /// 往右是逆时针。这里曾经写成 -angle，屏幕上就成了「脚朝着移动方向甩出去」，与真实的钟摆相反。
    var angle: CGFloat

    static func filling(_ bounds: NSRect) -> SpritePlacement {
        SpritePlacement(rect: bounds, pivot: NSPoint(x: bounds.midX, y: bounds.midY), angle: 0)
    }
}

/// 只负责显示一帧并上报点击与拖动。按原始宽高比整体绘制，不做逐帧缩放。
final class PetView: NSView {
    /// 按下又松开、中间没有拖动：点了雪绪一下。
    var onClick: (() -> Void)?
    var onDragBegan: (() -> Void)?
    var onDragEnded: (() -> Void)?
    var onContextMenu: ((NSEvent) -> Void)?

    private(set) var dragging = false
    /// 拖动开始时窗口会被放大以容下摆动，控制器改完窗口后由它重新取拖动基准。
    var onDragOriginChanged: (() -> NSPoint)?
    /// 这次按下是为了弹菜单（按住 control），松手不算点击。
    private var suppressClick = false
    private var current: SpriteLibrary.Frame?
    private var placement = SpritePlacement(rect: .zero, pivot: .zero, angle: 0)
    private var mouseStart: NSPoint = .zero
    private var originStart: NSPoint = .zero
    private var lastMouse: NSPoint = .zero

    override init(frame: NSRect) {
        super.init(frame: frame)
        // Let AppKit publish one complete transparent backing surface. Updating
        // only a child CALayer bypasses view invalidation and can leave stale
        // rectangular clipping on the display after window/backing changes.
        wantsLayer = true
        layerContentsRedrawPolicy = .onSetNeedsDisplay
        placement = .filling(bounds)
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override var isOpaque: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    func show(_ frame: SpriteLibrary.Frame, _ where_: SpritePlacement) {
        let sameImage = current?.image === frame.image
        if sameImage && where_ == placement { return }
        current = frame
        placement = where_
        // Invalidate the old and new silhouette, including pixels becoming
        // transparent when an animation, blink, or swing changes.
        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        guard let context = NSGraphicsContext.current?.cgContext else { return }
        context.saveGState()
        defer { context.restoreGState() }
        context.clear(bounds)
        guard let frame = current, placement.rect.width > 0, placement.rect.height > 0 else { return }
        context.interpolationQuality = .high
        context.translateBy(x: placement.pivot.x, y: placement.pivot.y)
        context.rotate(by: placement.angle)
        context.translateBy(x: -placement.pivot.x, y: -placement.pivot.y)
        context.draw(frame.image, in: placement.rect)
    }

    override func setFrameSize(_ newSize: NSSize) {
        super.setFrameSize(newSize)
        needsDisplay = true
    }

    override func viewDidChangeBackingProperties() {
        super.viewDidChangeBackingProperties()
        needsDisplay = true
    }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        needsDisplay = true
    }

    /// point：窗口内坐标（左下原点）。晃动时先把点转回竖直状态再查像素，歪着也能准确点中。
    func isOpaque(at point: NSPoint) -> Bool {
        let rect = placement.rect
        guard let f = current, rect.width > 0, rect.height > 0 else { return false }
        // 画的时候转了 +angle，命中测试要转回 -angle。
        let dx = point.x - placement.pivot.x, dy = point.y - placement.pivot.y
        let c = cos(placement.angle), s = sin(placement.angle)
        let ux = placement.pivot.x + dx * c + dy * s
        let uy = placement.pivot.y - dx * s + dy * c
        let x = Int((ux - rect.minX) / rect.width * CGFloat(f.width))
        let y = Int((rect.maxY - uy) / rect.height * CGFloat(f.height))
        return f.isOpaque(x: x, y: y)
    }

    override func mouseDown(with event: NSEvent) {
        if event.modifierFlags.contains(.control) {
            suppressClick = true
            onContextMenu?(event)
            return
        }
        suppressClick = false
        mouseStart = NSEvent.mouseLocation
        lastMouse = mouseStart
        originStart = window?.frame.origin ?? .zero
        dragging = false
    }

    override func mouseDragged(with event: NSEvent) {
        let m = NSEvent.mouseLocation
        let dx = m.x - mouseStart.x, dy = m.y - mouseStart.y
        if !dragging && hypot(dx, dy) > 3 {
            dragging = true
            onDragBegan?()
            // 控制器刚把窗口放大（原点跟着变），重新取一次基准，免得雪绪跳一下。
            if let origin = onDragOriginChanged?() {
                mouseStart = m
                lastMouse = m
                originStart = origin
                return
            }
        }
        guard dragging else { return }
        window?.setFrameOrigin(NSPoint(x: originStart.x + dx, y: originStart.y + dy))
        lastMouse = m
    }

    override func mouseUp(with event: NSEvent) {
        if dragging {
            dragging = false
            onDragEnded?()
            return
        }
        if suppressClick {
            suppressClick = false
            return
        }
        onClick?()
    }

    override func rightMouseDown(with event: NSEvent) {
        onContextMenu?(event)
    }
}
