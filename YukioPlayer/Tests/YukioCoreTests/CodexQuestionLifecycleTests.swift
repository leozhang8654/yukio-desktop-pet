import Foundation
import Testing
@testable import YukioCore

@Suite struct CodexQuestionLifecycleTests {
    private func event(_ parser: CodexRolloutParser, _ payload: [String: Any]) -> [PetEvent] {
        parser.events(from: ["type": "response_item", "payload": payload], now: 1000)
    }
    private func start(_ parser: CodexRolloutParser, async: Bool = true) -> [PetEvent] {
        event(parser, ["type": "function_call", "name": async ? "request_user_input_async" : "request_user_input",
            "call_id": "question", "arguments": ["questions": [["title": "选择颜色", "options": ["蓝色", "绿色"]]]]])
    }

    @Test func acknowledgementKeepsQuestionVisibleWhileOtherToolsRun() {
        let parser = CodexRolloutParser(session: "test")
        let h = Harness(session: "test")
        for e in start(parser) { h.router.ingest(e, now: 1000) }
        let ack = event(parser, ["type": "function_call_output", "call_id": "question", "output": "{\"accepted\":true}"])
        #expect(ack.isEmpty)
        for e in event(parser, ["type": "function_call", "name": "exec_command", "call_id": "work",
                                "arguments": ["cmd": "ls"]]) { h.router.ingest(e, now: 1000) }
        h.run(to: 5000)
        #expect(h.router.askingQuestion?.question.text == "选择颜色")
        #expect(h.router.askingQuestion?.question.options.map(\.label) == ["蓝色", "绿色"])
        let answer = event(parser, ["type": "message", "role": "user", "content": "蓝色"])
        #expect(answer.map(\.kind) == [.activityEnd, .taskStart])
        for e in answer { h.router.ingest(e, now: 5000) }
        h.run(to: 8000)
        #expect(h.router.askingQuestion == nil)
    }

    @Test func structuredReplyClosesWithoutStartingAnotherTurn() {
        let parser = CodexRolloutParser(session: "test")
        _ = start(parser)
        let reply = event(parser, ["type": "message", "role": "user", "content": "<send_user_message_question_reply>Blue</send_user_message_question_reply>"])
        #expect(reply.map(\.kind) == [.activityEnd])
    }

    @Test func synchronousAnswerStillClosesImmediately() {
        let parser = CodexRolloutParser(session: "test")
        _ = start(parser, async: false)
        let result = event(parser, ["type": "function_call_output", "call_id": "question", "output": "{\"answers\":{}}"])
        #expect(result.map(\.kind) == [.activityEnd])
    }

    @Test func failedAsyncCallDoesNotLeaveQuestionOpen() {
        let parser = CodexRolloutParser(session: "test")
        _ = start(parser)
        let result = event(parser, ["type": "function_call_output", "call_id": "question", "output": "{\"success\":false}"])
        #expect(result.map(\.kind) == [.activityFailed])
        let user = event(parser, ["type": "message", "role": "user", "content": "继续"])
        #expect(user.map(\.kind) == [.taskStart])
    }

    @Test func turnEndClearsAsyncQuestionTracking() {
        let parser = CodexRolloutParser(session: "test")
        _ = start(parser)
        _ = event(parser, ["type": "task_complete", "last_agent_message": "完成"])
        let user = event(parser, ["type": "message", "role": "user", "content": "继续"])
        #expect(user.map(\.kind) == [.taskStart])
    }
}
