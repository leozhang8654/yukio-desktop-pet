import Foundation
import Testing
@testable import YukioCore

@Suite struct CodexHelperActivityTests {
    let parent = "11111111-1111-4111-8111-111111111111"
    let child = "22222222-2222-4222-8222-222222222222"

    func header() -> [String: Any] {
        ["type": "session_meta", "payload": ["id": child, "session_id": parent,
         "source": ["subagent": ["thread_spawn": ["parent_thread_id": parent]]]]]
    }

    @Test func helperIdentityDoesNotOverwriteParentAndStartIsImmediate() {
        let parser = CodexRolloutParser(session: child)
        _ = parser.events(from: header())
        #expect(parser.session == child)
        #expect(parser.parentSession == parent)
        let events = parser.events(from: ["type": "event_msg", "payload": ["type": "task_started"]], now: 100)
        #expect(events.map(\.session) == [child])
        #expect(events.map(\.kind) == [.taskStart])
    }

    @Test func helperFinishingDoesNotStopParentOrRaiseCompletion() {
        let parser = CodexRolloutParser(session: child)
        _ = parser.events(from: header())
        let router = ActivityRouter(now: 0)
        router.ingest(PetEvent(ts: 0, source: "codex", session: parent, kind: .taskStart), now: 0)
        for event in parser.events(from: ["type": "event_msg", "payload": ["type": "task_started"]], now: 10) {
            router.ingest(event, now: 10)
        }
        router.settle(now: 20)
        #expect(router.sessionSummaries(now: 20).filter(\.live).count == 2)
        for payload: [String: Any] in [
            ["type": "message", "role": "assistant", "phase": "final_answer", "content": [["type": "output_text", "text": "done"]]],
            ["type": "item_completed", "item": ["type": "AgentMessage", "phase": "final_answer"]],
            ["type": "task_complete", "last_agent_message": "done"]
        ] {
            for event in parser.events(from: ["payload": payload], now: 100) { router.ingest(event, now: 100) }
        }
        router.settle(now: 5000)
        let rows = router.sessionSummaries(now: 5000)
        #expect(rows.first(where: { $0.id == parent })?.live == true)
        #expect(rows.first(where: { $0.id == child })?.live == false)
        #expect(rows.allSatisfy { !$0.raisedSign })
        #expect(router.displayed == .thinking)
        #expect(router.focusedSession == parent)
    }

    @Test func normalChatStillRaisesItsOwnCompletion() {
        let parser = CodexRolloutParser(session: parent)
        let events = parser.events(from: ["payload": ["type": "task_complete", "last_agent_message": "done"]], now: 100)
        #expect(events.map(\.kind) == [.finalAnswer, .taskEnd])
    }

    @Test func largeFileRestartKeepsHelperIdentityTitleAndNoFalseDoneCard() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("yukio-helper-\(UUID())")
        defer { try? FileManager.default.removeItem(at: root) }
        let directory = root.appendingPathComponent("sessions")
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        func line(_ object: [String: Any]) throws -> Data {
            var data = try JSONSerialization.data(withJSONObject: object); data.append(10); return data
        }
        let now = Date().timeIntervalSince1970 * 1000
        var data = try line(header())
        data.append(try line(["type": "padding", "text": String(repeating: "x", count: 2 << 20)]))
        data.append(try line(["payload": ["type": "task_started"]]))
        let file = directory.appendingPathComponent("rollout-2026-10-11T00-00-00-\(child).jsonl")
        try data.write(to: file)
        try line(["id": parent, "thread_name": "Animation task"]).write(to: root.appendingPathComponent("session_index.jsonl"))
        let source = CodexSessionsSource(sessionsDir: directory)
        let events = source.poll(now: now)
        #expect(events.contains { $0.kind == .taskStart && $0.session == child })
        #expect(events.contains { $0.kind == .sessionTitle && $0.detail?.hasPrefix("Animation task") == true })
        #expect(events.allSatisfy { $0.session == child })
        let handle = try FileHandle(forWritingTo: file)
        try handle.seekToEnd()
        try handle.write(contentsOf: line(["payload": ["type": "task_complete", "last_agent_message": "done"]]))
        try handle.close()
        let ended = source.poll(now: now + 100)
        #expect(ended.map(\.kind) == [.taskEnd])
        #expect(ended.allSatisfy { $0.session == child })
    }
}
