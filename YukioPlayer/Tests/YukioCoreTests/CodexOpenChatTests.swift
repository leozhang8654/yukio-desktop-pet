import Foundation
import Testing
@testable import YukioCore

@Suite struct CodexOpenChatTests {
    let a = "11111111-1111-4111-8111-111111111111"
    let b = "22222222-2222-4222-8222-222222222222"
    let base = PetEvent.parseTimestamp("2026-09-26T05:00:00.000Z")!

    func line(_ message: String, second: Int = 0, window: Int = 1,
              focused: Bool = true, visible: Bool = true) -> String {
        let stamp = String(format: "2026-09-26T05:00:%02d.000Z", second)
        return "\(stamp) info [electron-message-handler] \(message) rendererWindowAppearance=primary rendererWindowFocused=\(focused) rendererWindowId=\(window) rendererWindowVisible=\(visible)"
    }
    func view(_ id: String, active: Bool = true) -> String {
        "thread_stream_view_activity_changed active=\(active) conversationId=\(id)"
    }

    @Test func onlyViewedThreadIsSelectedNotBackgroundCompletion() {
        var s = CodexOpenChatState()
        s.ingest(line(view(a)))
        s.ingest(line("Reasoning summary item completed threadId=\(b)", second: 1))
        #expect(s.session(now: base + 1000) == a)
    }

    @Test func switchingChatsAndLeavingThreadClearsSelection() {
        var s = CodexOpenChatState()
        s.ingest(line(view(a)))
        s.ingest(line(view(a, active: false), second: 1))
        #expect(s.session(now: base + 1000) == nil)
        s.ingest(line(view(b), second: 1))
        #expect(s.session(now: base + 1000) == b)
        s.ingest(line(view(a, active: false), second: 2))
        #expect(s.session(now: base + 2000) == b)
    }

    @Test func secondaryWindowsDoNotDismissTheWrongThread() {
        var s = CodexOpenChatState()
        s.ingest(line(view(a)))
        s.ingest(line(view(b), window: 2, focused: false))
        #expect(s.session(now: base) == a)
        s.ingest(line("status", second: 1, window: 2))
        #expect(s.session(now: base + 1000) == b)
        s.ingest(line("status", second: 2, window: 1, focused: false))
        #expect(s.session(now: base + 2000) == b)
        s.ingest(line("status", second: 3, window: 2, visible: false))
        #expect(s.session(now: base + 3000) == nil)
    }

    @Test func staleMissingAndUnrecognizedEvidenceKeepsReminders() {
        var s = CodexOpenChatState()
        s.ingest(line("background conversationId=\(a)"))
        #expect(s.session(now: base) == nil)
        s.ingest(line(view("not-a-thread")))
        #expect(s.session(now: base) == nil)
        s.ingest(line(view(a)))
        #expect(s.session(now: base + 10001) == nil)
        s.ingest(line("status", second: 12))
        #expect(s.session(now: base + 12000) == a)
        s.ingest(line("status", second: 13, focused: false))
        #expect(s.session(now: base + 13000) == nil)
    }

    @Test func readerFollowsAppendsPartialLinesAndProcessRestarts() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let file = dir.appendingPathComponent("codex-desktop-test-42-t0-i1-000001-0.log")
        try Data((line(view(a)) + "\n").utf8).write(to: file)
        let reader = CodexOpenChat(logsDirectory: dir)
        #expect(reader.focusedSession(processID: 42, now: base) == a)
        let handle = try FileHandle(forWritingTo: file)
        defer { try? handle.close() }
        try handle.seekToEnd()
        try handle.write(contentsOf: Data(line(view(b), second: 1).utf8))
        #expect(reader.focusedSession(processID: 42, now: base + 1000) == a)
        try handle.write(contentsOf: Data("\n".utf8))
        #expect(reader.focusedSession(processID: 42, now: base + 1000) == b)
        #expect(reader.focusedSession(processID: 99, now: base + 1000) == nil)
    }

    @Test func codexViewSuppressesOnlyItsOwnCompletionAndLowersRaisedSign() {
        var s = CodexOpenChatState()
        s.ingest(line(view(a)))
        let h = Harness(session: a)
        h.router.openChatSession = s.session(now: base)
        h.send(.taskStart, source: "codex")
        h.run(to: 3000)
        h.send(.finalAnswer, source: "codex"); h.send(.taskEnd, source: "codex")
        h.run(to: 12000)
        #expect(!h.states.contains(.task_complete))
        h.send(.taskStart, session: b, source: "codex")
        h.run(to: 15000)
        h.send(.finalAnswer, session: b, source: "codex"); h.send(.taskEnd, session: b, source: "codex")
        h.run(to: 20000)
        #expect(h.router.completedSession == b)
        s.ingest(line(view(a, active: false), second: 1))
        s.ingest(line(view(b), second: 1))
        h.router.openChatSession = s.session(now: base + 1000)
        h.run(to: 23000)
        #expect(h.router.completedSession == nil)
        h.router.openChatSession = nil
        h.run(to: 28000)
        #expect(h.router.completedSession == nil)
    }
}
