#if DEBUG
import AppKit
import YukioCore

/// Opt-in integration fixture: the real card and provider sender, with a receipt file.
/// Never invoked during a normal launch, and never clicks or answers automatically.
final class AnswerCardCheck {
    let panel = QuestionPanel()
    let config: [String: Any]
    let question: PetQuestion
    let output: URL
    init(path: String) throws {
        config = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: path))) as! [String: Any]
        question = PetQuestion.from(input: config["question"] as! [String: Any])!
        output = URL(fileURLWithPath: config["output"] as! String)
        panel.title = "Yukio · background answer check"
        panel.alphaValue = 1
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false)
        panel.setFrame(NSRect(origin: NSPoint(x: 200, y: 250), size: panel.cardView.card!.size), display: true)
        panel.cardView.onOption = { [weak self] index in self?.send(self!.question.options[index].label) }
        panel.cardView.onSend = { [weak self] text in self?.send(text) }
        panel.cardView.onClose = { NSApp.terminate(nil) }
        panel.orderFrontRegardless()
    }
    func send(_ answer: String) {
        guard !answer.isEmpty, panel.cardView.card?.isSending != true else { return }
        let front = NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? ""
        let clipboard = NSPasteboard.general.changeCount
        panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, sentNotice: "Sending…", isSending: true)
        panel.setContentSize(panel.cardView.card!.size)
        DispatchQueue.global().async { [self] in
            var status = "received"
            do {
                if ["claude", "deepseek"].contains(config["provider"] as? String ?? "") {
                    try ClaudeQuestionBridge().send(session: config["session"] as! String, callID: config["callID"] as! String, answer: answer, provider: config["provider"] as! String)
                } else {
                    try CodexAnswerClient(socketPath: config["socketPath"] as? String).send(session: config["session"] as! String, callID: config["callID"] as! String, question: question, answer: answer)
                }
            } catch { status = error.localizedDescription }
            let result = status
            DispatchQueue.main.async { [self] in
                let record: [String: Any] = ["status": result, "frontBefore": front,
                    "frontAfter": NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? "",
                    "clipboardUnchanged": clipboard == NSPasteboard.general.changeCount]
                try? JSONSerialization.data(withJSONObject: record, options: [.prettyPrinted, .sortedKeys]).write(to: output)
                panel.cardView.card = QuestionCardLayout(question, canOpenChat: false, sentNotice: result)
                panel.setContentSize(panel.cardView.card!.size)
                if result == "received" { DispatchQueue.main.asyncAfter(deadline: .now() + 1) { NSApp.terminate(nil) } }
            }
        }
    }
}

#endif
