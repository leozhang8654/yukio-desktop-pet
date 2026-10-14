import AppKit
import YukioCore

/// The small card is a preview. Decisions require the complete, scrollable request.
/// Return/Escape choose "Later", never permission to execute.
enum ApprovalReview {
    static func answer(_ question: PetQuestion) -> String? {
        let alert = NSAlert()
        alert.messageText = question.header ?? tr("Approval request", "申请确认")
        alert.informativeText = tr("Review the complete request. Your choice applies only to this request.", "请查看完整申请。你的选择只针对这一次申请。")
        alert.addButton(withTitle: tr("Later", "稍后处理"))
        for option in question.options { alert.addButton(withTitle: option.label) }
        alert.buttons[0].keyEquivalent = "\r"
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 520, height: 280))
        scroll.hasVerticalScroller = true
        let text = NSTextView(frame: scroll.bounds)
        text.isEditable = false; text.isSelectable = true
        text.font = .systemFont(ofSize: 13)
        text.string = question.text
        text.textContainer?.widthTracksTextView = true
        text.isVerticallyResizable = true
        scroll.documentView = text
        alert.accessoryView = scroll
        let result = alert.runModal().rawValue - NSApplication.ModalResponse.alertFirstButtonReturn.rawValue - 1
        guard question.options.indices.contains(result) else { return nil }
        return question.options[result].label
    }
}
