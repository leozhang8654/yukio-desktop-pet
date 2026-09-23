import Foundation
import Testing
@testable import YukioCore

/// 跟哪一家、以及各家的记录目录怎么扫。
@Suite(.serialized) struct AgentSourceTests {
    let root: URL

    init() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("yukio-agents-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        L10n.language = .chinese
    }

    func now() -> Double { Date().timeIntervalSince1970 * 1000 }

    func stamp(_ ms: Double) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.string(from: Date(timeIntervalSince1970: ms / 1000))
    }

    func append(_ url: URL, _ s: String) throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        let h = try FileHandle(forWritingTo: url)
        try h.seekToEnd()
        try h.write(contentsOf: Data(s.utf8))
        try h.close()
    }

    @Test func settingsValueMapsToAProvider() {
        #expect(AgentProvider(code: nil) == .auto)
        #expect(AgentProvider(code: "gpt") == .gpt)
        #expect(AgentProvider(code: "codex") == .gpt)          // 别名
        #expect(AgentProvider(code: "deepcode") == .deepseek)   // Windows 版设置里存的就是这个
        #expect(AgentProvider(code: "Claude") == .claude)
        #expect(AgentProvider(code: "什么") == .auto)            // 设置坏了就三家都跟
        #expect(AgentProvider.owner(ofSource: "codex") == .gpt)
        #expect(AgentProvider.owner(ofSource: "claude-hook") == .claude)
        #expect(AgentProvider.owner(ofSource: "sim") == nil)    // 模拟演示不属于任何一家
    }

    @Test func onlyTheChosenFamilyIsFollowed() {
        #expect(AgentSources(provider: .gpt).statuses.map(\.provider) == [.gpt])
        #expect(AgentSources(provider: .claude).statuses.map(\.provider) == [.claude])
        #expect(AgentSources(provider: .auto).statuses.map(\.provider) == [.claude, .deepseek, .gpt])
        // Claude 的 hooks 收件箱只在跟 Claude 时挂着。
        #expect(AgentSources(provider: .gpt).hooks == nil)
        #expect(AgentSources(provider: .claude).hooks != nil)

        let feeds = AgentSources(provider: .claude)
        feeds.switchTo(.gpt)
        #expect(feeds.provider == .gpt)
        #expect(feeds.statuses.map(\.provider) == [.gpt])
    }

    @Test func codexSessionsAreFoundUnderTheDateFolders() throws {
        let sessions = root.appendingPathComponent("codex/sessions")
        let file = sessions.appendingPathComponent("2026/09/22/rollout-2026-09-22T18-53-22-01a0cbf7-b0eb-7ab1-8854-5fd2a4b1cb49.jsonl")
        let t0 = now()
        try append(file, #"{"timestamp":"\#(stamp(t0 - 5000))","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"改动画"}]}}"# + "\n")

        let source = CodexSessionsSource(sessionsDir: sessions)
        let first = source.poll(now: now())
        #expect(source.status.directoryFound)
        #expect(source.status.trackedFiles == 1)
        #expect(first.map(\.kind) == [.taskStart])
        #expect(first.first?.session == "01a0cbf7-b0eb-7ab1-8854-5fd2a4b1cb49")

        // 之后只读新增的部分。
        try append(file, #"{"timestamp":"\#(stamp(now()))","type":"response_item","payload":{"type":"custom_tool_call","name":"exec","call_id":"c1","input":"await tools.exec_command({cmd:\"cat a.txt\"})"}}"# + "\n")
        let more = source.poll(now: now())
        #expect(more.map(\.kind) == [.activityStart])
        #expect(more.first?.activity == .read_file)
        #expect(source.poll(now: now()).isEmpty)
    }

    @Test func deepCodeReadsMessagesAndTheSessionIndex() throws {
        let projects = root.appendingPathComponent("deepcode/projects")
        let project = projects.appendingPathComponent("p1")
        let t0 = now()
        try append(project.appendingPathComponent("s1.jsonl"),
                   #"{"sessionId":"s1","role":"user","content":"改动画","createTime":"\#(stamp(t0 - 5000))"}"# + "\n")
        try append(project.appendingPathComponent("sessions-index.json"),
                   #"{"entries":[{"id":"s1","summary":"改动画","status":"processing","updateTime":"\#(stamp(t0 - 4000))"}]}"#)

        let source = DeepCodeSource(projectsDir: projects)
        let first = source.poll(now: now())
        #expect(source.status.directoryFound)
        // 首次读索引只取标题，不把历史状态当成刚发生的事。
        #expect(first.map(\.kind) == [.taskStart, .sessionTitle])

        // 「等你批准」只写在索引里。
        try FileManager.default.removeItem(at: project.appendingPathComponent("sessions-index.json"))
        try append(project.appendingPathComponent("sessions-index.json"),
                   #"{"entries":[{"id":"s1","summary":"改动画","status":"ask_permission","updateTime":"\#(stamp(now()))"}]}"#)
        let waiting = source.poll(now: now())
        #expect(waiting.map(\.kind) == [.activityStart])
        #expect(waiting.first?.activity == .question_for_user)
    }
}
