import Foundation
import Testing
@testable import YukioCore

/// DeepSeek（Deep Code CLI）的记录 → 事件。规则与 Windows 版 `yukio/parsers_deepcode.py` 一致。
@Suite struct DeepCodeParserTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言

    let parser = DeepCodeMessageParser()
    let session = "sess-1"

    func parse(_ json: String) -> [PetEvent] {
        parser.events(fromLine: Data(json.utf8), fallbackSession: session, now: 1000)
    }

    @Test func userMessagesStartAndStopTheTask() {
        let start = parse(#"{"sessionId":"sess-1","role":"user","content":"把动画改顺一点","createTime":"2026-09-20T10:00:00.000Z"}"#)
        #expect(start.map(\.kind) == [.taskStart])
        #expect(start.first?.detail == "把动画改顺一点")
        #expect(start.first?.source == "deepcode")

        #expect(parse(#"{"sessionId":"sess-1","role":"user","content":"Interrupted. 用户打断"}"#).map(\.kind) == [.taskAbort])
        // 回答 AskUserQuestion 是同一轮继续，不是新任务。
        #expect(parse(#"{"sessionId":"sess-1","role":"user","content":"A","meta":{"isAnswers":true}}"#).map(\.kind) == [.thinking])
        // 压缩过的历史消息会被重写一遍，不能当成新活动。
        #expect(parse(#"{"sessionId":"sess-1","role":"user","content":"旧的","compacted":true}"#).isEmpty)
    }

    @Test func toolCallsAreClassifiedByTheSharedRules() {
        let events = parse(#"""
        {"sessionId":"sess-1","role":"assistant","content":"这就看一眼","messageParams":{"tool_calls":[{"id":"t1","function":{"name":"read","arguments":"{\"file_path\":\"/a/main.swift\"}"}},{"id":"t2","function":{"name":"bash","arguments":"{\"command\":\"swift test\"}"}}]}}
        """#)
        #expect(events.map(\.kind) == [.activityStart, .activityStart, .thinking])
        #expect(events[0].activity == .read_file)
        #expect(events[0].detail == "阅读 main.swift")
        #expect(events[0].eventID == "t1")
        #expect(events[1].activity == .verify)
        #expect(events[1].detail == "$ swift test")
    }

    @Test func toolResultsEndTheCallAndErrorsMakeHerSad() {
        let ok = parse(#"{"sessionId":"sess-1","role":"tool","content":"{\"ok\":true,\"output\":\"done\"}","messageParams":{"tool_call_id":"t1"}}"#)
        #expect(ok.map(\.kind) == [.activityEnd])
        #expect(ok.first?.eventID == "t1")

        let bad = parse(#"{"sessionId":"sess-1","role":"tool","content":"{\"ok\":false,\"error\":\"boom\"}","messageParams":{"tool_call_id":"t1"}}"#)
        #expect(bad.map(\.kind) == [.activityFailed])

        // 用户中断、拒绝授权都不算失败。
        let stopped = parse(#"{"sessionId":"sess-1","role":"tool","content":"{\"ok\":false,\"metadata\":{\"interrupted\":true}}","messageParams":{"tool_call_id":"t1"}}"#)
        #expect(stopped.map(\.kind) == [.activityEnd])
        let denied = parse(#"{"sessionId":"sess-1","role":"tool","content":"{\"ok\":false,\"error\":\"Permission denied by user\"}","messageParams":{"tool_call_id":"t1"}}"#)
        #expect(denied.map(\.kind) == [.activityEnd])
    }

    @Test func plainAnswerEndsTheTurn() {
        let answer = parse(#"{"sessionId":"sess-1","role":"assistant","content":"改好了"}"#)
        #expect(answer.map(\.kind) == [.finalAnswer, .taskEnd])
    }

    @Test func updatePlanBecomesTheTaskList() {
        let events = parse(#"""
        {"sessionId":"sess-1","role":"assistant","content":"","messageParams":{"tool_calls":[{"id":"p1","function":{"name":"UpdatePlan","arguments":"{\"plan\":\"- [x] 读代码\\n- [>] 改动画\\n- [ ] 跑测试\"}"}}]}}
        """#)
        #expect(events.map(\.kind) == [.activityStart, .todoList])
        let todos = events.last?.todos ?? []
        #expect(todos.map(\.subject) == ["读代码", "改动画", "跑测试"])
        #expect(todos.map(\.status) == [.completed, .inProgress, .pending])
    }

    @Test func indexBringsTitlesAndWaitingStates() {
        let index = DeepCodeIndexParser()
        let first = index.events(entry: ["id": session, "summary": "改动画", "status": "processing"], now: 1000)
        #expect(first.map(\.kind) == [.sessionTitle])
        #expect(first.first?.detail == "改动画")

        // 「等你批准」只写在索引里：立问号卡，等状态变了再收。
        let waiting = index.events(entry: ["id": session, "summary": "改动画", "status": "ask_permission"], now: 2000)
        #expect(waiting.map(\.kind) == [.activityStart])
        #expect(waiting.first?.activity == .question_for_user)
        #expect(waiting.first?.detail == "等你批准")

        let resumed = index.events(entry: ["id": session, "summary": "改动画", "status": "processing"], now: 3000)
        #expect(resumed.map(\.kind) == [.activityEnd, .thinking])
        #expect(resumed.first?.eventID == waiting.first?.eventID)

        #expect(index.events(entry: ["id": session, "status": "failed"], now: 4000).map(\.kind) == [.taskFailed])
        // 中断不算失败。
        #expect(index.events(entry: ["id": session, "status": "interrupted"], now: 5000).map(\.kind) == [.taskAbort])
    }
}
