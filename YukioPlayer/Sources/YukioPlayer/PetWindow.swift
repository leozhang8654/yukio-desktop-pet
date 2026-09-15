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

/// 只负责显示一帧并上报拖动。按原始宽高比整体绘制，不做逐帧缩放。
final class PetView: NSView {
    var onDragBegan: (() -> Void)?
    var onDragMoved: ((CGFloat) -> Void)?
    var onDragEnded: (() -> Void)?
    var onContextMenu: ((NSEvent) -> Void)?

    private(set) var dragging = false
    private var current: SpriteLibrary.Frame?
    private var mouseStart: NSPoint = .zero
    private var originStart: NSPoint = .zero
    private var lastMouse: NSPoint = .zero

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.contentsGravity = .resize
        layer?.magnificationFilter = .linear
        layer?.minificationFilter = .trilinear
        layer?.backgroundColor = NSColor.clear.cgColor
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override var isOpaque: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    func show(_ frame: SpriteLibrary.Frame) {
        if current?.image === frame.image { return }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        layer?.contents = frame.image
        CATransaction.commit()
        current = frame
    }

    /// point：窗口内坐标（左下原点）。
    func isOpaque(at point: NSPoint) -> Bool {
        guard let f = current, bounds.width > 0, bounds.height > 0 else { return false }
        let x = Int(point.x / bounds.width * CGFloat(f.width))
        let y = Int((bounds.height - point.y) / bounds.height * CGFloat(f.height))
        return f.isOpaque(x: x, y: y)
    }

    override func mouseDown(with event: NSEvent) {
        if event.modifierFlags.contains(.control) {
            onContextMenu?(event)
            return
        }
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
        }
        guard dragging else { return }
        window?.setFrameOrigin(NSPoint(x: originStart.x + dx, y: originStart.y + dy))
        onDragMoved?(m.x - lastMouse.x)
        lastMouse = m
    }

    override func mouseUp(with event: NSEvent) {
        if dragging {
            dragging = false
            onDragEnded?()
        }
    }

    override func rightMouseDown(with event: NSEvent) {
        onContextMenu?(event)
    }
}
