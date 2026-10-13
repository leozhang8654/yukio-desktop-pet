import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite struct ApprovalTests {
    func snapshot(method: String = "item/commandExecution/requestApproval", extra: [String: Any] = [:]) -> [String: Any] {
        var params: [String: Any] = ["threadId": "s", "turnId": "t", "itemId": "i", "command": "echo test", "reason": "Test only"]
        params.merge(extra) { _, new in new }
        return ["id": "s", "turns": [["id": "t", "status": "inProgress", "items": [["id": "i", "changes": [["path": "example.txt", "diff": "+ test"]]]]]],
                "requests": [["id": 42, "method": method, "params": params]]]
    }
    @Test func onlyExactLiveApprovalCanBeAnswered() throws {
        let original = snapshot()
        let card = try #require(CodexAnswerClient.approvals(snapshot: original, session: "s").first)
        #expect(card.question.isApproval)
        for answer in [ApprovalQuestion.allow, ApprovalQuestion.deny] {
            let response = try CodexAnswerClient.approvalSubmission(snapshot: original, session: "s", callID: card.callID, question: card.question, answer: answer)
            #expect(response.method == "thread-follower-command-approval-decision")
            #expect(response.params["decision"] as? String == (answer == ApprovalQuestion.allow ? "accept" : "decline"))
        }
        var ended = original; ended["turns"] = [["id": "t", "status": "completed"]]
        for changed in [snapshot(extra: ["command": "different command"]), snapshot(extra: ["turnId": "other"]), ended] {
            #expect(throws: (any Error).self) {
                try CodexAnswerClient.approvalSubmission(snapshot: changed, session: "s", callID: card.callID, question: card.question, answer: ApprovalQuestion.allow)
            }
        }
        #expect(throws: (any Error).self) { try CodexAnswerClient.approvalSubmission(snapshot: original, session: "other", callID: card.callID, question: card.question, answer: ApprovalQuestion.allow) }
        #expect(throws: (any Error).self) { try CodexAnswerClient.approvalSubmission(snapshot: original, session: "s", callID: card.callID, question: card.question, answer: "yes") }
        var duplicate = original; duplicate["requests"] = (original["requests"] as! [[String: Any]]) + (original["requests"] as! [[String: Any]])
        #expect(throws: (any Error).self) { try CodexAnswerClient.approvalSubmission(snapshot: duplicate, session: "s", callID: card.callID, question: card.question, answer: ApprovalQuestion.allow) }
    }
    @Test func noPermanentOrUnavailableGrant() throws {
        let snap = snapshot(method: "item/permissions/requestApproval", extra: ["permissions": ["network": ["enabled": true]]])
        let a = try #require(CodexAnswerClient.approvals(snapshot: snap, session: "s").first)
        for answer in [ApprovalQuestion.allow, ApprovalQuestion.deny] {
            let result = try CodexAnswerClient.approvalSubmission(snapshot: snap, session: "s", callID: a.callID, question: a.question, answer: answer)
            let response = try #require(result.params["response"] as? [String: Any])
            #expect(response["scope"] as? String == "turn")
            #expect((response["permissions"] as? [String: Any])?.isEmpty == (answer == ApprovalQuestion.deny))
        }
        let limited = snapshot(extra: ["availableDecisions": ["acceptForSession", "decline"]])
        let b = try #require(CodexAnswerClient.approvals(snapshot: limited, session: "s").first)
        #expect(b.question.options.map(\.label) == [ApprovalQuestion.deny])
    }
    @Test func fileApprovalIncludesActualChangesAndRejectsChangedDiff() throws {
        let snap = snapshot(method: "item/fileChange/requestApproval")
        let a = try #require(CodexAnswerClient.approvals(snapshot: snap, session: "s").first)
        #expect(a.question.text.contains("example.txt"))
        #expect(a.question.text.contains("+ test"))
        var missing = snap; missing["turns"] = [["id": "t", "status": "inProgress", "items": []]]
        #expect(try CodexAnswerClient.approvals(snapshot: missing, session: "s").isEmpty)
    }
    @Test func surfaceRequiresTrustedAddressAndDecisionPair() {
        #expect(ApprovalSurface.provider(url: "https://chatgpt.com/c/123") == "gpt")
        #expect(ApprovalSurface.provider(url: "chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn/sidepanel.html") == "claude")
        for url in ["https://claude.ai.evil.test/", "https://claude.ai@evil.test/", "http://claude.ai/", "https://example.com/", "https://claude.ai/artifact/fake"] {
            #expect(ApprovalSurface.provider(url: url) == nil)
        }
        #expect(ApprovalSurface.isRequest(text: "Allow access to this file?", buttons: ["Allow once", "Deny"]))
        #expect(!ApprovalSurface.isRequest(text: "Example permission prompt", buttons: ["Copy", "Send"]))
        #expect(!ApprovalSurface.isRequest(text: "Allow access to this file?", buttons: ["Always allow", "Cancel"]))
        #expect(!ApprovalSurface.isRequest(text: "Allow access to this file?", buttons: ["Allow", "Deny", "Allow"]))
    }
    @Test func claudePermissionRoundTripAndOfflineFallback() async throws {
        for answer in [ApprovalQuestion.allow, ApprovalQuestion.deny] {
            let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: root) }
            let bridge = ClaudeQuestionBridge(root: root)
            let data = try JSONSerialization.data(withJSONObject: ["hook_event_name": "PermissionRequest", "session_id": "s", "tool_name": "Bash", "cwd": "/tmp", "tool_input": ["command": "echo test"]])
            #expect(ClaudeQuestionBridge.runHook(input: data, root: root, waitSeconds: 0.1) == Data("{}".utf8))
            _ = bridge.poll(now: Date().timeIntervalSince1970 * 1000)
            let hook = Task.detached { ClaudeQuestionBridge.runHook(input: data, root: root, waitSeconds: 4) }
            var pending: PetEvent?
            for _ in 0..<80 {
                pending = bridge.poll(now: Date().timeIntervalSince1970 * 1000).first { $0.question?.isApproval == true }
                if pending != nil { break }; try await Task.sleep(nanoseconds: 25_000_000)
            }
            let e = try #require(pending)
            #expect(throws: (any Error).self) { try bridge.send(session: "s", callID: e.eventID!, answer: "yes") }
            try bridge.send(session: "s", callID: e.eventID!, answer: answer)
            let result = try #require(JSONSerialization.jsonObject(with: await hook.value) as? [String: Any])
            let output = try #require(result["hookSpecificOutput"] as? [String: Any])
            #expect(output["hookEventName"] as? String == "PermissionRequest")
            let decision = try #require(output["decision"] as? [String: Any])
            #expect(decision["behavior"] as? String == (answer == ApprovalQuestion.allow ? "allow" : "deny"))
            #expect(decision["updatedPermissions"] == nil)
        }
    }
    @Test @MainActor func fieldEditorHandlesPasteWithoutAssistantMenu() throws {
        let panel = QuestionPanel()
        let editor = NSTextView(frame: .init(x: 0, y: 0, width: 100, height: 100))
        panel.contentView = editor
        #expect(panel.makeFirstResponder(editor))
        let board = NSPasteboard.general
        let saved = board.pasteboardItems?.map { item in item.types.compactMap { type in item.data(forType: type).map { (type, $0) } } } ?? []
        defer {
            board.clearContents()
            let items = saved.map { values -> NSPasteboardItem in let item = NSPasteboardItem(); for (type, data) in values { item.setData(data, forType: type) }; return item }
            board.writeObjects(items)
            panel.close()
        }
        func key(_ char: String) throws -> NSEvent { try #require(NSEvent.keyEvent(with: .keyDown, location: .zero, modifierFlags: .command, timestamp: 0, windowNumber: panel.windowNumber, context: nil, characters: char, charactersIgnoringModifiers: char, isARepeat: false, keyCode: 0)) }
        board.clearContents(); board.setString("中文回答\nsecond line 🙂", forType: .string)
        #expect(panel.performKeyEquivalent(with: try key("v")))
        #expect(editor.string == "中文回答\nsecond line 🙂")
        #expect(panel.performKeyEquivalent(with: try key("a")))
        #expect(editor.selectedRange().length == (editor.string as NSString).length)
        board.clearContents(); board.setString("替换", forType: .string)
        #expect(panel.performKeyEquivalent(with: try key("v")))
        #expect(editor.string == "替换")
    }
}
