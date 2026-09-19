import Foundation
import Testing
@testable import YukioCore

/// 用临时目录冒充桌面版的会话记录目录，验证“转录会话 → 那条聊天”的对应。
@Suite struct SessionLinkTests {
    private func makeRecords(_ records: [(file: String, json: String)]) throws -> URL {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("yukio-session-links-\(UUID().uuidString)")
        let dir = root.appendingPathComponent("账号/组织")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        for r in records {
            try Data(r.json.utf8).write(to: dir.appendingPathComponent(r.file))
        }
        return root
    }

    /// 真实记录的开头：桌面版会话 ID 在最前，紧跟着转录的会话 ID。
    private func record(desktop: String, cli: String, filler: Int = 0) -> String {
        let tail = String(repeating: "x", count: filler)
        return """
        {"sessionId":"\(desktop)","cliSessionId":"\(cli)","cwd":"/Users/me/proj","isArchived":false,\
        "title":"某个任务","toolSurfaceSnapshot":"\(tail)"}
        """
    }

    @Test func findsTheChatThatBelongsToATranscriptSession() throws {
        let a = "11111111-2222-3333-4444-555555555555"
        let b = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        let root = try makeRecords([
            ("local_1e6b0a2c-0000-4000-8000-000000000001.json",
             record(desktop: "local_1e6b0a2c-0000-4000-8000-000000000001", cli: a, filler: 4096)),
            ("local_1e6b0a2c-0000-4000-8000-000000000002.json",
             record(desktop: "local_1e6b0a2c-0000-4000-8000-000000000002", cli: b)),
        ])
        defer { try? FileManager.default.removeItem(at: root) }
        let links = ClaudeSessionLinks(sessionsDir: root)
        #expect(links.desktopSessionID(forTranscriptSession: b) == "local_1e6b0a2c-0000-4000-8000-000000000002")
        #expect(links.chatURL(forTranscriptSession: a)?.absoluteString
                == "claude://code/continue?session=local_1e6b0a2c-0000-4000-8000-000000000001")
    }

    @Test func unknownSessionGivesNoLinkInsteadOfAWrongOne() throws {
        let root = try makeRecords([
            ("local_1e6b0a2c-0000-4000-8000-000000000001.json",
             record(desktop: "local_1e6b0a2c-0000-4000-8000-000000000001", cli: "11111111-2222-3333-4444-555555555555")),
        ])
        defer { try? FileManager.default.removeItem(at: root) }
        let links = ClaudeSessionLinks(sessionsDir: root)
        // 在终端里跑的会话（桌面版没有这条记录）：宁可没有链接，也不要跳到别人的聊天。
        #expect(links.desktopSessionID(forTranscriptSession: "99999999-8888-7777-6666-555555555555") == nil)
        // 目录不存在时也只是没有链接。
        #expect(ClaudeSessionLinks(sessionsDir: root.appendingPathComponent("没有这个目录"))
                    .chatURL(forTranscriptSession: "11111111-2222-3333-4444-555555555555") == nil)
    }

    @Test func onlyIDShapedValuesBecomeLinks() {
        // 会话 ID 直接拼进查找与链接，先限定字符。
        #expect(ClaudeSessionLinks.isTranscriptSessionID("c0a80650-cd5e-4e6a-a048-462a287f8ddc"))
        #expect(!ClaudeSessionLinks.isTranscriptSessionID("\" or 1=1"))
        #expect(!ClaudeSessionLinks.isTranscriptSessionID("短"))
        #expect(ClaudeSessionLinks.chatURL(desktopSession: "local_3987aafa-f03f-4d83-8995-1f6a2ebba08a") != nil)
        #expect(ClaudeSessionLinks.chatURL(desktopSession: "3987aafa-f03f-4d83-8995-1f6a2ebba08a") == nil)
        #expect(ClaudeSessionLinks.chatURL(desktopSession: "local_a b") == nil)
    }

    @Test func readsTheValueEvenWithSpacesAroundTheColon() {
        let data = Data(#"{ "sessionId" : "local_x-1" , "cliSessionId":"abc" }"#.utf8)
        #expect(ClaudeSessionLinks.value(of: "sessionId", in: data) == "local_x-1")
        #expect(ClaudeSessionLinks.value(of: "cliSessionId", in: data) == "abc")
        #expect(ClaudeSessionLinks.value(of: "没有这个键", in: data) == nil)
    }
}
