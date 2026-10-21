import Foundation
import Testing
@testable import YukioCore

@Suite struct VisibleChatTests {
    let a = "75f6b686-7df9-2166-5c45-437f32b2703d"
    let b = "0ff5afbf-2794-8a70-8df1-96e3be2aefd9"

    @Test func webAppAndExtensionDocumentRoutes() {
        for url in ["https://claude.ai/chat/\(a)", "https://claude.ai/code/\(a)",
                    "https://claude.ai/cic/task/cse_0123456789"] {
            #expect(VisibleChat(url: url)?.provider == .claude)
        }
        for url in ["https://chatgpt.com/c/\(a)", "https://chat.openai.com/c/\(a)",
                    "https://chatgpt.com/g/g-project/c/\(a)", "codex://threads/\(a)",
                    "https://chatgpt.com/codex/tasks/task_0123456789"] {
            #expect(VisibleChat(url: url)?.provider == .gpt)
        }
    }

    @Test func unrelatedPagesHistorySpoofedHostsAndBadIDsAreRejected() {
        for url in ["https://claude.ai/", "https://claude.ai/recents", "https://chatgpt.com/",
                    "https://claude.ai.evil.test/chat/\(a)", "https://claude.ai@evil.test/chat/\(a)",
                    "http://claude.ai/chat/\(a)", "https://claude.ai/chat/no-id",
                    "https://chatgpt.com/share/\(a)", "https://chatgpt.com/c/\(a)/extra",
                    "chrome-extension://test/sidepanel.html?session=\(a)"] {
            #expect(VisibleChat(url: url) == nil, "\(url)")
        }
    }

    @Test func identitiesAreProviderScopedAndAliasesMustBeExplicit() throws {
        let web = try #require(VisibleChat(url: "https://claude.ai/chat/\(a)"))
        #expect(web.matches(session: a, provider: .claude))
        #expect(!web.matches(session: a, provider: .gpt))
        #expect(!web.matches(session: b, provider: .claude))
        let app = try #require(VisibleChat(url: "claude://code/continue?session=local_\(a)"))
        #expect(!app.matches(session: a, provider: .claude))
        #expect(app.matches(session: a, provider: .claude, aliases: ["local_\(a)": a]))
    }

    @Test func readingDuringResponseHoldAcknowledgesThatTurnOnly() {
        let h = Harness(session: a)
        h.send(.taskStart); h.run(to: 3000)
        h.send(.finalAnswer); h.send(.taskEnd)
        h.router.visibleChatSessions = [a]
        h.run(to: 3500) // Leave before the old sign-arming delay.
        h.router.visibleChatSessions = []
        h.run(to: 15000)
        #expect(h.router.completedSession == nil)
        h.send(.taskStart); h.run(to: 18000)
        h.send(.finalAnswer); h.send(.taskEnd); h.run(to: 24000)
        #expect(h.router.completedSession == a) // New unseen turn still reminds.
    }

    @Test func visiblePageAndSidePanelClearRaisedSignsWhilePinnedElsewhere() {
        let h = Harness(session: a)
        h.send(.taskStart, session: "working")
        _ = h.router.pinSession("working", now: h.now)
        for id in [a, b, "unseen"] {
            h.send(.taskStart, session: id)
            h.send(.finalAnswer, session: id); h.send(.taskEnd, session: id)
        }
        h.run(to: 12000)
        #expect(h.router.sessionSummaries(now: h.now).filter(\.raisedSign).count == 3)
        h.router.visibleChatSessions = [a, b]
        h.run(to: 13000)
        #expect(h.router.sessionSummaries(now: h.now).filter(\.raisedSign).map(\.id) == ["unseen"])
        h.router.visibleChatSessions = []
        h.run(to: 14000)
        #expect(h.router.sessionSummaries(now: h.now).filter(\.raisedSign).map(\.id) == ["unseen"])
    }
}
