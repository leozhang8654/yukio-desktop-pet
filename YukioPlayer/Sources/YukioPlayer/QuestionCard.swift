import AppKit
import YukioCore

/// 举牌时立在她身边的那张问题卡：把 AskUserQuestion 的问题原样抄下来，
/// 选项一行一个可以直接点，下面留一个输入框自己写一句。
///
/// 外观沿用头顶气泡那套（`CardLook`：同样的圆角、描边、墨色），只是宽一些——
/// 气泡 180 点只够放一行状态，问题要读得下去，所以这张 280 点、正文会折行。
/// 这里只管排版与绘制，与窗口无关（`--question` 快照也用它）。
struct QuestionCardLayout {
    enum Hit: Equatable {
        /// 点了第几个选项（直接把这个选项的文字答回去）。
        case option(Int)
        /// 点了输入框（交给真正的文本框收键盘输入）。
        case input
        /// 点了送出。
        case send
        /// 点了“打开聊天”。
        case openChat
        /// 点了右上角的 ✕：这一轮先不在这儿答。
        case close
    }

    static let width: CGFloat = 280
    /// 问题正文最多显示几行，再长就截断（完整的那份在聊天里）。
    static let maxQuestionLines = 6
    /// 最多列几个选项，多出来的折进“还有 N 个选项”那行提示。
    static let maxOptions = 6

    private static let padX = CardLook.padX + 2
    private static let padY = CardLook.padY + 2
    private static let gap: CGFloat = 6
    private static let optionGap: CGFloat = 3
    private static let optionPadX: CGFloat = 6
    private static let optionPadY: CGFloat = 4
    private static let numberWidth: CGFloat = 16
    private static let inputHeight: CGFloat = 24
    private static let sendWidth: CGFloat = 30
    private static let closeBox: CGFloat = 15

    private static let headerFont = CardLook.titleFont
    private static let questionFont = NSFont.systemFont(ofSize: 12.5, weight: .semibold)
    private static let optionFont = NSFont.systemFont(ofSize: 11.5, weight: .medium)
    private static let detailFont = NSFont.systemFont(ofSize: 10, weight: .regular)
    private static let hintFont = CardLook.smallFont

    /// 已经答过、等她接着干活时那行字。
    let sentNotice: String?
    let header: String?
    /// 折过行、必要时截断过的问题正文。
    let question: String
    let options: [PetQuestion.Option]
    /// 没列出来的选项个数。
    let hiddenOptions: Int
    let multiSelect: Bool
    /// 多选时已经选中的选项下标。
    let picked: Set<Int>
    /// 能不能跳回那条聊天（Deep Code 没有窗口可跳，就不画这条）。
    let canOpenChat: Bool
    let size: NSSize

    private let questionHeight: CGFloat
    private let optionRects: [NSRect]
    private let optionLines: [(label: String, detail: String?)]
    private let inputRect: NSRect
    private let sendRect: NSRect
    /// 答过之后那行「已送出」占的位置（没答过时是空的）。
    private let noticeRect: NSRect
    private let hintRect: NSRect
    private let openChatRect: NSRect?

    init(_ q: PetQuestion, picked: Set<Int> = [], canOpenChat: Bool = true, sentNotice: String? = nil) {
        self.sentNotice = sentNotice
        self.multiSelect = q.multiSelect
        self.picked = picked
        self.canOpenChat = canOpenChat
        header = q.header.flatMap { $0.isEmpty ? nil : CardLook.singleLine($0) }
        let innerW = Self.width - 2 * Self.padX
        // 没有小标题时问题正文就从最上面一行开始，右上角的 ✕ 压在那儿：正文整体让出这一格宽。
        let questionW = innerW - (header == nil ? Self.closeBox + 4 : 0)
        let wrapped = Self.wrap(q.text, font: Self.questionFont, width: questionW, maxLines: Self.maxQuestionLines)
        question = wrapped.text
        questionHeight = wrapped.height

        let shown = Array(q.options.prefix(Self.maxOptions))
        options = shown
        hiddenOptions = q.options.count - shown.count

        // 从上往下排，最后整体翻成左下原点的坐标。
        var y: CGFloat = Self.padY
        let hintH = CardLook.lineHeight(Self.hintFont)
        hintRect = NSRect(x: Self.padX, y: y, width: innerW, height: hintH)
        openChatRect = canOpenChat
            ? NSRect(x: Self.width - Self.padX - Self.openChatWidth, y: y, width: Self.openChatWidth, height: hintH)
            : nil
        y += hintH + Self.gap

        if sentNotice == nil {
            inputRect = NSRect(x: Self.padX, y: y, width: innerW - Self.sendWidth - 4, height: Self.inputHeight)
            sendRect = NSRect(x: Self.width - Self.padX - Self.sendWidth, y: y,
                              width: Self.sendWidth, height: Self.inputHeight)
            noticeRect = .zero
            y += Self.inputHeight + Self.gap
        } else {
            inputRect = .zero
            sendRect = .zero
            let h = CardLook.lineHeight(Self.optionFont)
            noticeRect = NSRect(x: Self.padX, y: y, width: innerW, height: h)
            y += h + Self.gap
        }

        var rects: [NSRect] = []
        var lines: [(String, String?)] = []
        let labelW = innerW - Self.numberWidth - 2 * Self.optionPadX
        for option in shown.reversed() {
            let label = Self.clip(option.label, font: Self.optionFont, width: labelW)
            let detail = option.detail.map { Self.clip($0, font: Self.detailFont, width: labelW) }
            var h = 2 * Self.optionPadY + CardLook.lineHeight(Self.optionFont)
            if detail != nil { h += CardLook.lineHeight(Self.detailFont) - 1 }
            rects.append(NSRect(x: Self.padX, y: y, width: innerW, height: h))
            lines.append((label, detail))
            y += h + Self.optionGap
        }
        optionRects = rects.reversed()
        optionLines = lines.reversed().map { (label: $0.0, detail: $0.1) }
        if !shown.isEmpty { y += Self.gap - Self.optionGap }

        y += questionHeight + Self.gap
        if header != nil { y += CardLook.lineHeight(Self.headerFont) + CardLook.lineGap }
        y += Self.padY
        size = NSSize(width: Self.width, height: ceil(y))
    }

    private static let openChatWidth: CGFloat = 78

    /// 卡片的左下角：立在她身旁（右边放不下就换到左边），高度对齐她的上半身。
    /// 卡片始终留在这块屏幕里，也不压到她头顶那摞气泡上。
    static func origin(size: NSSize, petFrame pet: NSRect, visible: NSRect) -> NSPoint {
        let gap: CGFloat = 8
        var x = pet.maxX + gap
        if x + size.width > visible.maxX - 4 {
            x = pet.minX - gap - size.width               // 右边放不下就立到左边
        }
        x = min(max(x, visible.minX + 4), max(visible.minX + 4, visible.maxX - size.width - 4))
        // 上边大致与她的肩同高：卡片不高时贴着上半身，很高时往下坐，别顶出屏幕。
        var y = pet.maxY - size.height * 0.75
        y = min(max(y, visible.minY + 4), max(visible.minY + 4, visible.maxY - size.height - 4))
        return NSPoint(x: x.rounded(), y: y.rounded())
    }

    func hit(at point: NSPoint, in bounds: NSRect) -> Hit? {
        func r(_ rect: NSRect) -> NSRect { rect.offsetBy(dx: bounds.minX, dy: bounds.minY) }
        guard bounds.contains(point) else { return nil }
        if r(Self.closeRect(NSRect(origin: .zero, size: size))).contains(point) { return .close }
        for (i, rect) in optionRects.enumerated() where r(rect).contains(point) { return .option(i) }
        if sentNotice == nil {
            if r(inputRect).contains(point) { return .input }
            if r(sendRect).contains(point) { return .send }
        }
        if let open = openChatRect, r(open).contains(point) { return .openChat }
        return nil
    }

    /// 输入框在窗口里的位置：真正收键盘的是一个 NSTextField，由视图摆到这儿。
    func textFieldFrame(in bounds: NSRect) -> NSRect {
        inputRect.offsetBy(dx: bounds.minX, dy: bounds.minY).insetBy(dx: 1, dy: 1)
    }

    func draw(in bounds: NSRect) {
        CardLook.box(bounds, radius: CardLook.radius + 1)
        func r(_ rect: NSRect) -> NSRect { rect.offsetBy(dx: bounds.minX, dy: bounds.minY) }
        let innerW = Self.width - 2 * Self.padX
        var top = bounds.maxY - Self.padY

        if let header {
            let h = CardLook.lineHeight(Self.headerFont)
            top -= h
            CardLook.draw(header, Self.headerFont, CardLook.muted,
                          in: NSRect(x: bounds.minX + Self.padX, y: top,
                                     width: innerW - Self.closeBox, height: h))
            top -= CardLook.lineGap
        }
        drawClose(in: r(Self.closeRect(NSRect(origin: .zero, size: size))))

        top -= questionHeight
        Self.drawWrapped(question, font: Self.questionFont, color: CardLook.ink,
                         in: NSRect(x: bounds.minX + Self.padX, y: top,
                                    width: innerW - (header == nil ? Self.closeBox + 4 : 0), height: questionHeight))

        for (i, rect) in optionRects.enumerated() {
            drawOption(i, in: r(rect))
        }

        if let notice = sentNotice {
            CardLook.draw(notice, Self.optionFont, CardLook.accent, in: r(noticeRect))
        } else {
            drawInput(in: r(inputRect))
            drawSend(in: r(sendRect))
        }

        var hint = multiSelect ? tr("Pick any, ⏎ to send", "可多选，⏎ 送出") : tr("Click an option or type ⏎", "点选项，或打字 ⏎")
        if hiddenOptions > 0 { hint = tr("\(hiddenOptions) more in the chat", "还有 \(hiddenOptions) 个选项在聊天里") }
        if sentNotice != nil { hint = tr("Check the chat", "请到聊天中确认") }
        let hintRectOnScreen = r(hintRect)
        CardLook.draw(hint, Self.hintFont, CardLook.muted,
                      in: NSRect(x: hintRectOnScreen.minX, y: hintRectOnScreen.minY,
                                 width: hintRectOnScreen.width - (openChatRect != nil ? Self.openChatWidth : 0),
                                 height: hintRectOnScreen.height))
        if let open = openChatRect {
            CardLook.draw(tr("Open the chat ›", "打开聊天 ›"), Self.hintFont, CardLook.accent,
                          in: r(open))
        }
    }

    private func drawOption(_ i: Int, in rect: NSRect) {
        let on = picked.contains(i)
        let path = NSBezierPath(roundedRect: rect.insetBy(dx: 0.5, dy: 0.5), xRadius: 5, yRadius: 5)
        (on ? CardLook.accent.withAlphaComponent(0.14) : CardLook.ink.withAlphaComponent(0.05)).setFill()
        path.fill()
        (on ? CardLook.accent.withAlphaComponent(0.55) : CardLook.ink.withAlphaComponent(0.10)).setStroke()
        path.lineWidth = 1
        path.stroke()

        let numberH = CardLook.lineHeight(Self.hintFont)
        let line = optionLines[i]
        let labelH = CardLook.lineHeight(Self.optionFont)
        var top = rect.maxY - Self.optionPadY - labelH
        // 序号：键盘上按这个数字就等于点它。
        CardLook.draw(on ? "✓" : "\(i + 1)", Self.hintFont, on ? CardLook.accent : CardLook.muted,
                      in: NSRect(x: rect.minX + Self.optionPadX, y: top + (labelH - numberH) / 2,
                                 width: Self.numberWidth, height: numberH))
        let x = rect.minX + Self.optionPadX + Self.numberWidth
        let w = rect.maxX - Self.optionPadX - x
        CardLook.draw(line.label, Self.optionFont, CardLook.ink, in: NSRect(x: x, y: top, width: w, height: labelH))
        if let detail = line.detail {
            let h = CardLook.lineHeight(Self.detailFont)
            top -= h - 1
            CardLook.draw(detail, Self.detailFont, CardLook.muted, in: NSRect(x: x, y: top, width: w, height: h))
        }
    }

    private func drawInput(in rect: NSRect) {
        let path = NSBezierPath(roundedRect: rect.insetBy(dx: 0.5, dy: 0.5), xRadius: 5, yRadius: 5)
        NSColor(white: 1, alpha: 0.9).setFill()
        path.fill()
        CardLook.ink.withAlphaComponent(0.18).setStroke()
        path.lineWidth = 1
        path.stroke()
    }

    private func drawSend(in rect: NSRect) {
        let path = NSBezierPath(roundedRect: rect.insetBy(dx: 0.5, dy: 0.5), xRadius: 5, yRadius: 5)
        CardLook.accent.withAlphaComponent(0.92).setFill()
        path.fill()
        let h = CardLook.lineHeight(Self.hintFont)
        CardLook.draw("⏎", Self.hintFont, .white,
                      in: NSRect(x: rect.minX, y: rect.midY - h / 2, width: rect.width, height: h), center: true)
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

    private static func closeRect(_ card: NSRect) -> NSRect {
        NSRect(x: card.maxX - closeBox - 2, y: card.maxY - closeBox - 2, width: closeBox, height: closeBox)
    }

    // MARK: 折行

    private static func paragraph(_ mode: NSLineBreakMode) -> NSMutableParagraphStyle {
        let p = NSMutableParagraphStyle()
        p.lineBreakMode = mode
        return p
    }

    static func drawWrapped(_ s: String, font: NSFont, color: NSColor, in rect: NSRect) {
        (s as NSString).draw(with: rect, options: [.usesLineFragmentOrigin],
                             attributes: [.font: font, .foregroundColor: color,
                                          .paragraphStyle: paragraph(.byWordWrapping)], context: nil)
    }

    static func height(_ s: String, font: NSFont, width: CGFloat) -> CGFloat {
        let box = (s as NSString).boundingRect(
            with: NSSize(width: width, height: .greatestFiniteMagnitude),
            options: [.usesLineFragmentOrigin],
            attributes: [.font: font, .paragraphStyle: paragraph(.byWordWrapping)])
        return ceil(box.height)
    }

    /// 折到不超过 maxLines 行；超了就往回截，末尾补省略号（完整的一份在聊天里）。
    static func wrap(_ s: String, font: NSFont, width: CGFloat, maxLines: Int) -> (text: String, height: CGFloat) {
        let text = CardLook.singleLine(s)
        let limit = CardLook.lineHeight(font) * CGFloat(maxLines) + 2
        let full = height(text, font: font, width: width)
        if full <= limit { return (text, full) }
        // 二分找最长的能放下的前缀：整句比较长时省得一个字一个字试。
        var low = 0, high = text.count
        while low < high {
            let mid = (low + high + 1) / 2
            let candidate = String(text.prefix(mid)) + "…"
            if height(candidate, font: font, width: width) <= limit { low = mid } else { high = mid - 1 }
        }
        let clipped = String(text.prefix(low)) + "…"
        return (clipped, height(clipped, font: font, width: width))
    }

    /// 一行以内：放不下就截断加省略号（选项标题与说明都只给一行）。
    static func clip(_ s: String, font: NSFont, width: CGFloat) -> String {
        let text = CardLook.singleLine(s)
        guard CardLook.width(text, font) > width else { return text }
        var low = 0, high = text.count
        while low < high {
            let mid = (low + high + 1) / 2
            if CardLook.width(String(text.prefix(mid)) + "…", font) <= width { low = mid } else { high = mid - 1 }
        }
        return String(text.prefix(low)) + "…"
    }

    /// 自查用：几个代表点（每个选项、输入框、送出、打开聊天、✕、空白处）。
    static func probePoints(_ layout: QuestionCardLayout, in bounds: NSRect) -> [(String, NSPoint)] {
        var out: [(String, NSPoint)] = []
        for (i, rect) in layout.optionRects.enumerated() {
            let r = rect.offsetBy(dx: bounds.minX, dy: bounds.minY)
            out.append(("选项\(i + 1)", NSPoint(x: r.midX, y: r.midY)))
        }
        let input = layout.inputRect.offsetBy(dx: bounds.minX, dy: bounds.minY)
        out.append(("输入框", NSPoint(x: input.midX, y: input.midY)))
        let send = layout.sendRect.offsetBy(dx: bounds.minX, dy: bounds.minY)
        out.append(("送出", NSPoint(x: send.midX, y: send.midY)))
        if let open = layout.openChatRect?.offsetBy(dx: bounds.minX, dy: bounds.minY) {
            out.append(("打开聊天", NSPoint(x: open.midX, y: open.midY)))
        }
        let close = closeRect(NSRect(origin: .zero, size: layout.size)).offsetBy(dx: bounds.minX, dy: bounds.minY)
        out.append(("✕", NSPoint(x: close.midX, y: close.midY)))
        out.append(("问题正文（不可点）", NSPoint(x: bounds.midX, y: bounds.maxY - 4)))
        return out
    }
}
