import AppKit
import YukioCore

/// 立在她身边的那张问题卡的窗口。
///
/// 和气泡、卡叠一样是跟着她走的透明子窗口，但这一张要收键盘输入（自己写一句回答），
/// 所以它能成为 key 窗口——不过只有你真的点了它才会（`NSApp.activate` 在控制器里调），
/// 问题立起来的那一刻不抢你正在敲的东西。
final class QuestionPanel: NSPanel {
    let cardView = QuestionCardView(frame: NSRect(x: 0, y: 0, width: QuestionCardLayout.width, height: 40))

    init() {
        super.init(contentRect: NSRect(x: 0, y: 0, width: QuestionCardLayout.width, height: 40),
                   styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .ignoresCycle]
        hidesOnDeactivate = false
        isReleasedWhenClosed = false
        isMovable = false
        alphaValue = 0
        contentView = cardView
    }

    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}

/// 问题卡的正文：选项和提示是画出来的，只有输入框是真正的 NSTextField
/// （中文输入法、选词、光标都交给系统，不自己做一套）。
final class QuestionCardView: NSView, NSTextFieldDelegate {
    /// 这张卡的排版（属性不叫 layout：NSView 自己有个同名方法）。
    var card: QuestionCardLayout? {
        didSet {
            needsDisplay = true
            placeField()
        }
    }

    /// 点了第几个选项。
    var onOption: ((Int) -> Void)?
    /// 送出输入框里的话。
    var onSend: ((String) -> Void)?
    /// 点了“打开聊天”。
    var onOpenChat: (() -> Void)?
    /// 点了 ✕：这一轮先不在这儿答。
    var onClose: (() -> Void)?
    /// 点在卡片上（控制器用来把窗口变成 key，好让输入法能用）。
    var onActivate: (() -> Void)?

    let field = NSTextField(frame: .zero)

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        field.isBordered = false
        field.drawsBackground = false
        field.focusRingType = .none
        field.font = NSFont.systemFont(ofSize: 11.5)
        field.textColor = CardLook.ink
        field.placeholderString = tr("Type your own answer", "自己写一句…")
        field.delegate = self
        field.cell?.lineBreakMode = .byTruncatingHead
        field.isHidden = true
        addSubview(field)
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override var isOpaque: Bool { false }
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override var acceptsFirstResponder: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        card?.draw(in: bounds)
    }

    private func placeField() {
        guard let card, card.sentNotice == nil else {
            field.isHidden = true
            return
        }
        field.isHidden = false
        field.frame = card.textFieldFrame(in: bounds).insetBy(dx: 5, dy: 4)
    }

    override func setFrameSize(_ newSize: NSSize) {
        super.setFrameSize(newSize)
        placeField()
    }

    /// 输入框里的话；送出之后清空。
    var answerText: String {
        get { field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines) }
        set { field.stringValue = newValue }
    }

    func focusField() {
        window?.makeFirstResponder(field)
    }

    override func mouseDown(with event: NSEvent) {
        // 和点雪绪一样在 mouseUp 里处理；这里只把窗口变成 key，输入法才用得上。
        onActivate?()
    }

    override func mouseUp(with event: NSEvent) {
        let point = convert(event.locationInWindow, from: nil)
        switch card?.hit(at: point, in: bounds) {
        case .option(let i): onOption?(i)
        case .input: focusField()
        case .send: onSend?(answerText)
        case .openChat: onOpenChat?()
        case .close: onClose?()
        case nil: break
        }
    }

    /// 数字键 1–9 等于点对应的选项，Esc 等于点 ✕。输入框拿到焦点时这些键归输入框。
    override func keyDown(with event: NSEvent) {
        guard let chars = event.charactersIgnoringModifiers, let first = chars.first else {
            super.keyDown(with: event)
            return
        }
        if first == "\u{1b}" { onClose?(); return }
        if first == "\r" || first == "\u{3}" { onSend?(answerText); return }
        if let n = first.wholeNumberValue, n >= 1, n <= (card?.options.count ?? 0) {
            onOption?(n - 1)
            return
        }
        super.keyDown(with: event)
    }

    // MARK: 输入框

    func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        switch selector {
        case #selector(NSResponder.insertNewline(_:)):
            onSend?(answerText)
            return true
        case #selector(NSResponder.cancelOperation(_:)):
            // 有字先清掉，空的时候再按才收卡。
            if answerText.isEmpty { onClose?() } else { answerText = "" }
            return true
        default:
            return false
        }
    }
}
