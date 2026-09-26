import AppKit
import Testing
@testable import YukioPlayer

@Suite @MainActor
struct AnswerSenderTests {
    private final class Harness {
        let pb = NSPasteboard.withUniqueName()
        var front: String? = "target"
        var permission = true
        var requested = false
        var keys: [CGKeyCode] = []
        var queue: [() -> Void] = []
        var outcome: AnswerSender.Outcome?
        var failKey = false
        deinit { pb.releaseGlobally() }

        func send(target: String? = "target") {
            pb.setString("original", forType: .string)
            AnswerSender.send("答案", to: target, bringToFront: {}, completion: { self.outcome = $0 },
                environment: .init(pasteboard: pb, hasPermission: { self.permission },
                    requestPermission: { self.requested = true }, frontmost: { self.front },
                    pressKey: { code, _ in
                        if self.failKey { return false }
                        self.keys.append(code)
                        return true
                    }, schedule: { _, work in self.queue.append(work) }))
        }
        func step() { queue.removeFirst()() }
        func finish() { while !queue.isEmpty { step() } }
    }

    @Test func successfulPasteRestoresAllClipboardFormats() {
        let h = Harness()
        let rich = Data("{\\rtf1 original}".utf8)
        h.pb.setData(rich, forType: .rtf)
        h.send()
        h.finish()
        #expect(h.keys == [9, 36])
        #expect(h.outcome == .typed)
        #expect(h.pb.string(forType: .string) == "original")
        #expect(h.pb.data(forType: .rtf) == rich)
    }

    @Test func failedActivationKeepsAnswerForManualPaste() {
        let h = Harness()
        h.front = "other"
        h.send()
        h.finish()
        #expect(h.keys.isEmpty)
        #expect(h.outcome == .copied)
        #expect(h.pb.string(forType: .string) == "答案")
    }

    @Test func switchingAppsAfterPasteNeverSendsReturn() {
        let h = Harness()
        h.send()
        h.step()
        h.front = "other"
        h.finish()
        #expect(h.keys == [9])
        #expect(h.outcome == .copied)
        #expect(h.pb.string(forType: .string) == "答案")
    }

    @Test func permissionFailureKeepsAnswerAndDoesNotType() {
        let h = Harness()
        h.permission = false
        h.send()
        h.finish()
        #expect(h.requested)
        #expect(h.outcome == .needsPermission)
        #expect(h.keys.isEmpty)
        #expect(h.pb.string(forType: .string) == "答案")
    }

    @Test func copyOnlyDoesNotRequestAccessibility() {
        let h = Harness()
        h.permission = false
        h.send(target: nil)
        #expect(!h.requested)
        #expect(h.outcome == .copied)
    }

    @Test func changedClipboardIsNeitherPastedNorOverwritten() {
        let h = Harness()
        h.send()
        h.pb.clearContents()
        h.pb.setString("new copy", forType: .string)
        h.finish()
        #expect(h.keys.isEmpty)
        #expect(h.pb.string(forType: .string) == "new copy")
        #expect(h.outcome == .clipboardChanged)
    }

    @Test func recopyingSameAnswerIsNotUndoneByDelayedRestore() {
        let h = Harness()
        h.send()
        h.step()
        h.step()
        h.pb.clearContents()
        h.pb.setString("答案", forType: .string)
        h.finish()
        #expect(h.pb.string(forType: .string) == "答案")
    }

    @Test func failedKeystrokeDoesNotClaimSuccess() {
        let h = Harness()
        h.failKey = true
        h.send()
        h.finish()
        #expect(h.outcome == .copied)
        #expect(h.keys.isEmpty)
    }
}
