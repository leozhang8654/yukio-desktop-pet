import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite struct BackgroundAnswersTests {
    let q = PetQuestion(text: "Which?", options: [.init(label: "A"), .init(label: "B")])
    func snapshot() -> [String: Any] {
        ["id": "session", "cwd": "/tmp", "turns": [["status": "inProgress", "items": [
            ["id": "call", "type": "agentMessage", "questions": [["title": "Which?", "options": ["A", "B"]]]]
        ]]]]
    }
    @Test func codexOnlyFollowingDoesNotAdvertiseOtherProviders() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        _ = ClaudeQuestionBridge(root: root).poll(now: Date().timeIntervalSince1970 * 1000, providers: ["gpt"])
        #expect(!FileManager.default.fileExists(atPath: root.appendingPathComponent("listener-deepseek").path))
        #expect(!FileManager.default.fileExists(atPath: root.appendingPathComponent("listener").path))
    }
    @Test func exactThreadAndQuestionRequired() throws {
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snapshot(), session: "other", callID: "call", question: q, answer: "A") }
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snapshot(), session: "session", callID: "other", question: q, answer: "A") }
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snapshot(), session: "session", callID: "call", question: .init(text: "Unrelated"), answer: "A") }
    }
    @Test func acceptedAsyncReplyUsesStructuredQuestionID() throws {
        let s = try CodexAnswerClient.submission(snapshot: snapshot(), session: "session", callID: "call", question: q, answer: "中文 <answer>")
        #expect(s.method == "thread-follower-steer-turn")
        let content = try #require(s.params["input"] as? [[String: Any]])
        let text = try #require(content[0]["text"] as? String)
        #expect(text.contains("中文 <answer>"))
        var snap = snapshot()
        var turns = snap["turns"] as! [[String: Any]]
        var items = turns[0]["items"] as! [[String: Any]]
        items.append(["type": "steeringUserMessage", "status": "accepted", "content": content])
        turns[0]["items"] = items; snap["turns"] = turns
        #expect(throws: (any Error).self) { try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A") }
    }
    @Test func blockingQuestionsUseRequestResponseNotChat() throws {
        var snap = snapshot()
        snap["requests"] = [["id": 42, "method": "item/tool/requestUserInput", "params": ["itemId": "blocking", "questions": [["id": "choice", "question": "Which?"]]]]]
        let s = try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "blocking", question: q, answer: "B")
        #expect(s.method == "thread-follower-submit-user-input")
        #expect(s.params["requestId"] as? Int == 42)
        #expect(s.params["input"] == nil)
    }
    func canonicalSnapshot(_ legacy: [String: Any]) -> [String: Any] {
        var result = legacy
        let turns = legacy["turns"] as! [[String: Any]]
        result["turns"] = [] as [[String: Any]]
        result["turnHistory"] = ["kind": "canonical", "history": [
            "entitiesByKey": Dictionary(uniqueKeysWithValues: turns.enumerated().map { ("turn-\($0.offset)", $0.element) }),
            "islands": [["entries": turns.indices.map { ["key": "index-\($0)", "value": "turn-\($0)"] }]]
        ]]
        return result
    }
    @Test func canonicalHistoryAnswersLiveQuestionWithEmptyLegacyTurns() throws {
        let s = try CodexAnswerClient.submission(snapshot: canonicalSnapshot(snapshot()), session: "session", callID: "call", question: q, answer: "A")
        #expect(s.method == "thread-follower-steer-turn")
        // Duplicate protection must also read the canonical history.
        var legacy = snapshot()
        var turn = (legacy["turns"] as! [[String: Any]])[0]
        var items = turn["items"] as! [[String: Any]]
        items.append(["type": "steeringUserMessage", "status": "accepted", "content": s.params["input"]!])
        turn["items"] = items; legacy["turns"] = [turn]
        #expect(throws: CodexAnswerClient.Failure.expired) {
            try CodexAnswerClient.submission(snapshot: canonicalSnapshot(legacy), session: "session", callID: "call", question: q, answer: "B")
        }
    }
    @Test func canonicalHistoryDoesNotUseStaleLegacyOrDetachedTurns() throws {
        var snap = snapshot()
        snap["turnHistory"] = ["kind": "canonical", "history": [
            "entitiesByKey": ["detached": (snap["turns"] as! [[String: Any]])[0]],
            "islands": [["entries": [] as [[String: Any]]]]
        ]]
        #expect(throws: CodexAnswerClient.Failure.expired) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A")
        }
        snap["turnHistory"] = ["kind": "canonical", "history": [
            "entitiesByKey": [:] as [String: [String: Any]],
            "islands": [["entries": [["key": "index", "value": "missing"]]]]
        ]]
        #expect(throws: CodexAnswerClient.Failure.protocolMismatch) {
            try CodexAnswerClient.submission(snapshot: snap, session: "session", callID: "call", question: q, answer: "A")
        }
    }
    @Test func canonicalHistorySupportsBlockingReceiptLookup() throws {
        let receipt: [String: Any] = ["requestId": 42, "completed": true]
        let snap = canonicalSnapshot(["turns": [["status": "completed", "items": [receipt]]]])
        let turns = try CodexAnswerClient.turns(in: snap)
        let items = try #require(turns.first?["items"] as? [[String: Any]])
        #expect(items.first?["requestId"] as? Int == 42)
        #expect(items.first?["completed"] as? Bool == true)
    }
    @Test func claudeHookPreservesOtherSettingsAndIsIdempotent() throws {
        let original: [String: Any] = ["model": "unchanged", "permissions": ["deny": ["Bash"]], "hooks": ["PreToolUse": [["matcher": "*", "hooks": [["type": "command", "command": "existing"]]]]]]
        let once = BackgroundAnswerSetup.mergedSettings(original, executable: "/tmp/YukioAnswerBridge")
        let twice = BackgroundAnswerSetup.mergedSettings(once, executable: "/tmp/YukioAnswerBridge")
        #expect(try JSONSerialization.data(withJSONObject: once, options: .sortedKeys) == JSONSerialization.data(withJSONObject: twice, options: .sortedKeys))
        #expect(twice["model"] as? String == "unchanged")
        #expect((twice["permissions"] as? [String: [String]])?["deny"] == ["Bash"])
    }
    @Test func claudeTwoQuestionRoundTripAndNoListenerFallback() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        let bridge = ClaudeQuestionBridge(root: root)
        let input: [String: Any] = ["hook_event_name": "PreToolUse", "tool_name": "AskUserQuestion", "session_id": "s", "tool_use_id": "c", "tool_input": ["questions": [["question": "One?", "options": ["A", "B"]], ["question": "Two?", "options": ["C", "D"]]]]]
        let bytes = try JSONSerialization.data(withJSONObject: input)
        #expect(ClaudeQuestionBridge.runHook(input: bytes, root: root, waitSeconds: 2) == Data("{}".utf8))
        _ = bridge.poll(now: Date().timeIntervalSince1970 * 1000)
        let hook = Task.detached { ClaudeQuestionBridge.runHook(input: bytes, root: root, waitSeconds: 5) }
        for expected in ["One?", "Two?"] {
            var pending: PetEvent?
            for _ in 0..<80 {
                pending = bridge.poll(now: Date().timeIntervalSince1970 * 1000).first { $0.question?.text == expected }
                if pending != nil { break }
                try await Task.sleep(nanoseconds: 25_000_000)
            }
            let event = try #require(pending)
            try bridge.send(session: "s", callID: try #require(event.eventID), answer: "回答 " + expected)
        }
        let output = try #require(JSONSerialization.jsonObject(with: await hook.value) as? [String: Any])
        let specific = try #require(output["hookSpecificOutput"] as? [String: Any])
        #expect(specific["permissionDecision"] as? String == "allow")
        let updated = try #require(specific["updatedInput"] as? [String: Any])
        #expect(updated["answers"] as? [String: String] == ["One?": "回答 One?", "Two?": "回答 Two?"])
    }
    @Test @MainActor func failureNoticeKeepsClickableOptions() {
        let card = QuestionCardLayout(q, sentNotice: "Connection failed")
        let rect = NSRect(origin: .zero, size: card.size)
        #expect(QuestionCardLayout.probePoints(card, in: rect).contains { card.hit(at: $0.1, in: rect) == .option(0) })
        let busy = QuestionCardLayout(q, sentNotice: "Sending", isSending: true)
        #expect(!QuestionCardLayout.probePoints(busy, in: NSRect(origin: .zero, size: busy.size)).contains { busy.hit(at: $0.1, in: NSRect(origin: .zero, size: busy.size)) == .option(0) })
    }
}
