import Foundation
import Testing
@testable import YukioCore

/// 抄题：AskUserQuestion 的问题与选项要原样到得了雪绪身边那张卡上。
@Suite struct QuestionTests {
    init() { L10n.language = .chinese }

    /// Claude Code 写进转录里的真实形状。
    private let claudeInput: [String: Any] = [
        "questions": [[
            "question": "发到 GitHub 的安装包要包含另一个会话没提交的改动吗？",
            "header": "发布范围",
            "multiSelect": false,
            "options": [
                ["label": "一起发（推荐）", "description": "分两次提交，合并进 main，发 v0.1.0"],
                ["label": "只发图标这版", "description": "从干净工作树重新打包"],
                ["label": "先别提交推送"],
            ],
        ]],
    ]

    @Test func copiesQuestionHeaderAndOptions() {
        let q = PetQuestion.from(input: claudeInput)
        #expect(q?.text == "发到 GitHub 的安装包要包含另一个会话没提交的改动吗？")
        #expect(q?.header == "发布范围")
        #expect(q?.multiSelect == false)
        #expect(q?.options.count == 3)
        #expect(q?.options.first?.label == "一起发（推荐）")
        #expect(q?.options.first?.detail == "分两次提交，合并进 main，发 v0.1.0")
        #expect(q?.options.last?.detail == nil)
    }

    /// Codex 那边的写法：问题在 title，选项直接是几个字符串。
    @Test func copiesCodexShapeWithPlainStringOptions() {
        let q = PetQuestion.from(input: [
            "questions": [["title": "先跑测试还是先打包？", "options": ["先跑测试", "先打包"], "multi_select": true]],
        ])
        #expect(q?.text == "先跑测试还是先打包？")
        #expect(q?.multiSelect == true)
        #expect(q?.options.map(\.label) == ["先跑测试", "先打包"])
    }

    /// 没有 questions 数组、顶层直接给一句的简写。
    @Test func copiesFlatShape() {
        let q = PetQuestion.from(input: ["prompt": "要我继续吗？"])
        #expect(q?.text == "要我继续吗？")
        #expect(q?.options.isEmpty == true)
    }

    @Test func ignoresToolsThatAreNotAsking() {
        #expect(ClaudeToolClassifier.question(tool: "Bash", input: ["command": "echo question"]) == nil)
        #expect(ClaudeToolClassifier.question(tool: "AskUserQuestion", input: claudeInput) != nil)
        #expect(ClaudeToolClassifier.question(tool: "ask_user_question", input: claudeInput) != nil)
    }

    /// 问题正文里的硬换行折成一行，气泡与卡片上的短说明用小标题。
    @Test func shortLabelPrefersTheHeader() {
        let q = PetQuestion.from(input: claudeInput)
        #expect(q?.shortLabel == "发布范围")
        let noHeader = PetQuestion(text: String(repeating: "长", count: 60))
        #expect(noHeader.shortLabel.count == 41)          // 40 个字加一个省略号
        #expect(PetQuestion(text: "第一行\n第二行").shortLabel == "第一行 第二行")
    }

    /// 气泡上那行字：抄到的问题（或小标题）就是说明文字。
    @Test func describeUsesTheQuestion() {
        #expect(ClaudeToolClassifier.describe(tool: "AskUserQuestion", input: claudeInput) == "发布范围")
        #expect(ClaudeToolClassifier.describe(tool: "AskUserQuestion", input: [:]) == "等你回答")
    }

    /// 从转录一路到路由器：举着问号卡时问得出「此刻在问什么」，答完就没有了。
    @Test func routerHandsOutTheQuestionWhileTheCardIsUp() {
        let h = Harness()
        h.send(.taskStart)
        let question = PetQuestion.from(input: claudeInput)!
        h.router.ingest(PetEvent(ts: h.now, source: "test", session: h.session, kind: .activityStart,
                                 eventID: "q", activity: .question_for_user, tool: "AskUserQuestion",
                                 detail: question.shortLabel, question: question), now: h.now)
        h.run(to: 4000)
        #expect(h.router.displayed == .question_for_user)
        let pending = h.router.askingQuestion
        #expect(pending?.session == h.session)
        #expect(pending?.callID == "q")
        #expect(pending?.question.options.count == 3)
        h.send(.activityEnd, id: "q")
        h.send(.thinking)
        h.run(to: 8000)
        #expect(h.router.askingQuestion == nil)
    }

    /// 转录里的一条 assistant 记录：工具调用带着问题一起出来。
    @Test func transcriptCarriesTheQuestion() throws {
        let line = """
        {"type":"assistant","sessionId":"s","timestamp":"2026-09-22T10:00:00.000Z","message":{"stop_reason":"tool_use",\
        "content":[{"type":"tool_use","id":"t1","name":"AskUserQuestion","input":{"questions":[{"question":"要发吗？",\
        "header":"发布","options":[{"label":"发"},{"label":"先不发"}]}]}}]}}
        """
        let events = ClaudeTranscriptParser().events(fromLine: Data(line.utf8))
        let start = try #require(events.first { $0.kind == .activityStart })
        #expect(start.activity == .question_for_user)
        #expect(start.question?.text == "要发吗？")
        #expect(start.question?.options.map(\.label) == ["发", "先不发"])
        #expect(start.detail == "发布")
    }
}
