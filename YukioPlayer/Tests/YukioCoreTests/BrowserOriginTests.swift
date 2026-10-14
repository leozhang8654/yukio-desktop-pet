import Foundation
import Testing
@testable import YukioCore

@Suite struct BrowserOriginTests {
    @Test func originIsLoadedEvenWhenOldTranscriptIsNotReplayed() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let url = root.appendingPathComponent("sessions/rollout-plugin.jsonl")
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(#"{"type":"session_meta","payload":{"id":"plugin","originator":"codex-chrome-extension-sidepanel"}}"#.utf8).write(to: url)
        let h = try FileHandle(forWritingTo: url); try h.seekToEnd(); try h.write(contentsOf: Data([10])); try h.close()
        let now = Date().timeIntervalSince1970 * 1000
        try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSince1970: now / 1000 - 3600)], ofItemAtPath: url.path)
        try Data((#"{"id":"plugin","thread_name":"A finished browser chat"}"# + "\n").utf8).write(to: root.appendingPathComponent("session_index.jsonl"))
        let source = CodexSessionsSource(sessionsDir: url.deletingLastPathComponent())
        let events = source.poll(now: now)
        #expect(events.contains { $0.kind == .sessionTitle && $0.session == "plugin" && $0.detail == "A finished browser chat" })
        #expect(!events.contains { $0.kind == .finalAnswer || $0.kind == .taskEnd })
        #expect(source.isBrowserSession("plugin"))
        #expect(!source.isBrowserSession("other"))
    }
}
