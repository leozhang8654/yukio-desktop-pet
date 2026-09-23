import Foundation
import Testing
@testable import YukioCore

/// GPT（Codex）的记录 → 事件。样例按本机真实 rollout 的形状写（字段裁短，不含对话内容）。
@Suite struct CodexParserTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言

    let session = "01a0cbf7-b0eb-7ab1-8854-5fd2a4b1cb49"

    func parse(_ parser: CodexRolloutParser, _ json: String) -> [PetEvent] {
        parser.events(fromLine: Data(json.utf8), now: 0)
    }

    func line(_ ts: String, _ type: String, _ payload: String) -> String {
        #"{"timestamp":"\#(ts)","type":"\#(type)","payload":\#(payload)}"#
    }

    @Test func sessionIDComesFromTheFileNameThenFromSessionMeta() {
        #expect(CodexSessionsSource.sessionID(fromFileName: "rollout-2026-09-22T18-53-22-\(session).jsonl") == session)
        // 分支出来的记录名里有两个 ID，取后面那个（新的那条）。
        #expect(CodexSessionsSource.sessionID(fromFileName: "rollout-2026-09-22T19-10-20-01a0c702-e876-7f71-a663-420d6fd3e7d7_\(session).jsonl") == session)
        // 认不出来时原样用文件名，至少还能把同一个文件的事件归到一起。
        #expect(CodexSessionsSource.sessionID(fromFileName: "weird-name.jsonl") == "weird-name")

        let parser = CodexRolloutParser(session: "from-file-name")
        _ = parse(parser, line("2026-09-23T01:54:03.608Z", "session_meta",
                               #"{"session_id":"\#(session)","cwd":"/tmp","originator":"Codex Desktop"}"#))
        #expect(parser.session == session)
    }

    @Test func userMessageStartsTheTaskAndBoilerplateDoesNot() {
        let parser = CodexRolloutParser(session: session)
        // 塞给模型的环境说明（整条以 < 开头）不是人说的话。
        let context = parse(parser, line("2026-09-23T01:54:03.930Z", "response_item",
            #"{"type":"message","role":"user","content":[{"type":"input_text","text":"<app-context>\n# Codex desktop context"}]}"#))
        #expect(context.isEmpty)
        let developer = parse(parser, line("2026-09-23T01:54:03.930Z", "response_item",
            #"{"type":"message","role":"developer","content":[{"type":"input_text","text":"You are Codex"}]}"#))
        #expect(developer.isEmpty)

        let prompt = parse(parser, line("2026-09-23T01:54:03.931Z", "response_item",
            #"{"type":"message","role":"user","content":[{"type":"input_text","text":"把动画改顺一点\n第二行"}]}"#))
        #expect(prompt.map(\.kind) == [.taskStart])
        #expect(prompt.first?.detail == "把动画改顺一点")
        #expect(prompt.first?.source == "codex")
        #expect(prompt.first?.session == session)

        // 界面那一份也写了同一条消息；路由器按 duplicateTaskStartMs 去重，这里只看认得出来。
        let item = parse(parser, line("2026-09-23T01:54:04.201Z", "event_msg",
            #"{"type":"item_completed","thread_id":"\#(session)","item":{"type":"UserMessage","content":[{"type":"text","text":"把动画改顺一点"}]}}"#))
        #expect(item.map(\.kind) == [.taskStart])
    }

    @Test func turnEndsWithFinalAnswerThenTaskEnd() {
        let parser = CodexRolloutParser(session: session)
        let done = parse(parser, line("2026-09-23T02:00:50.865Z", "event_msg",
            #"{"type":"task_complete","turn_id":"t1","last_agent_message":"做完了"}"#))
        #expect(done.map(\.kind) == [.finalAnswer, .taskEnd])

        // 没有回答的一轮（被压缩、被接管）只算结束，不走递交报告。
        let quiet = parse(parser, line("2026-09-23T02:00:50.865Z", "event_msg",
            #"{"type":"task_complete","turn_id":"t1","last_agent_message":""}"#))
        #expect(quiet.map(\.kind) == [.taskEnd])

        // 用户按停不算失败。
        let stopped = parse(parser, line("2026-09-23T02:01:50.865Z", "event_msg",
            #"{"type":"turn_aborted","reason":"interrupted"}"#))
        #expect(stopped.map(\.kind) == [.taskAbort])
        let broke = parse(parser, line("2026-09-23T02:02:50.865Z", "event_msg", #"{"type":"error","message":"stream error"}"#))
        #expect(broke.map(\.kind) == [.taskFailed])
    }

    @Test func execScriptSaysWhatItIsDoing() {
        let parser = CodexRolloutParser(session: session)
        func start(_ input: String) -> PetEvent {
            let json = #"{"type":"custom_tool_call","name":"exec","call_id":"call_1","input":"\#(input)"}"#
            return parse(parser, line("2026-09-23T01:55:03.425Z", "response_item", json)).first!
        }
        let read = start(#"const r = await tools.exec_command({cmd:\"sed -n '1,240p' main.swift\",\"workdir\":\"/tmp\"});text(r.output)"#)
        #expect(read.activity == .read_file)
        #expect(read.detail == "$ sed -n 1,240p")

        let test = start(#"const r = await tools.exec_command({cmd:\"cd app && swift test\"});"#)
        #expect(test.activity == .verify)

        let patch = start(#"text(await tools.apply_patch(\"*** Begin Patch\n*** Update File: /tmp/main.swift\n\"))"#)
        #expect(patch.activity == .write_file)
        #expect(patch.detail == "编辑 main.swift")

        let image = start(#"image((await tools.view_image({path:\"/tmp/shot.png\"})).content)"#)
        #expect(image.activity == .view_image)
        #expect(image.detail == "查看 shot.png")

        // 等一条还在跑的命令：延续上一个动作（activity 为 nil）。
        let wait = start(#"text(await tools.write_stdin({session_id:\"2\",chars:\"y\n\"}))"#)
        #expect(wait.activity == nil)
    }

    @Test func toolCallsPairUpAndFailuresMakeHerSad() {
        let parser = CodexRolloutParser(session: session)
        let start = parse(parser, line("2026-09-23T01:55:03.425Z", "response_item",
            #"{"type":"custom_tool_call","name":"exec","call_id":"call_1","input":"await tools.exec_command({cmd:\"rg TODO\"})"}"#))
        #expect(start.map(\.kind) == [.activityStart])
        #expect(start.first?.eventID == "call_1")

        // 界面那一份先写「这条命令失败了」，紧接着才是输出。
        let item = parse(parser, line("2026-09-23T01:55:04.000Z", "event_msg",
            #"{"type":"item_completed","item":{"type":"CommandExecution","status":"failed","exit_code":1}}"#))
        #expect(item.isEmpty)
        let end = parse(parser, line("2026-09-23T01:55:04.100Z", "response_item",
            #"{"type":"custom_tool_call_output","call_id":"call_1","output":[{"type":"input_text","text":"no matches"}]}"#))
        #expect(end.map(\.kind) == [.activityFailed])
        #expect(end.first?.eventID == "call_1")

        // 下一次成功的调用不该还带着上一次的失败。
        _ = parse(parser, line("2026-09-23T01:55:05.000Z", "response_item",
            #"{"type":"custom_tool_call","name":"exec","call_id":"call_2","input":"await tools.exec_command({cmd:\"rg TODO\"})"}"#))
        let ok = parse(parser, line("2026-09-23T01:55:06.000Z", "response_item",
            #"{"type":"custom_tool_call_output","call_id":"call_2","output":[{"type":"input_text","text":"ok"}]}"#))
        #expect(ok.map(\.kind) == [.activityEnd])
    }

    @Test func classicCliToolsAreUnderstood() {
        let parser = CodexRolloutParser(session: session)
        func start(_ payload: String) -> PetEvent {
            parse(parser, line("2026-09-23T01:55:03.425Z", "response_item", payload)).first!
        }
        let shell = start(#"{"type":"function_call","name":"shell","call_id":"c1","arguments":"{\"command\":[\"bash\",\"-lc\",\"cat README.md\"]}"}"#)
        #expect(shell.activity == .read_file)

        let ask = start(#"{"type":"function_call","name":"request_user_input_async","call_id":"c2","arguments":"{\"questions\":[{\"title\":\"要哪一种？\"}]}"}"#)
        #expect(ask.activity == .question_for_user)
        #expect(ask.detail == "要哪一种？")

        let search = start(#"{"type":"function_call","name":"web_search","call_id":"c3","arguments":"{\"query\":\"swift testing\"}"}"#)
        #expect(search.activity == .read_web)

        // 老版把退出码写在输出里。
        let failed = parse(parser, line("2026-09-23T01:55:04.425Z", "response_item",
            #"{"type":"function_call_output","call_id":"c1","output":"{\"output\":\"boom\",\"metadata\":{\"exit_code\":2}}"}"#))
        #expect(failed.map(\.kind) == [.activityFailed])
    }

    @Test func planUpdatesBecomeTheTaskList() {
        let parser = CodexRolloutParser(session: session)
        let events = parse(parser, line("2026-09-23T01:55:03.425Z", "response_item",
            #"{"type":"function_call","name":"update_plan","call_id":"c9","arguments":"{\"plan\":[{\"step\":\"读代码\",\"status\":\"completed\"},{\"step\":\"改动画\",\"status\":\"in_progress\"}]}"}"#))
        #expect(events.map(\.kind) == [.activityStart, .todoList])
        #expect(events.first?.activity == .thinking)
        let todos = events.last?.todos ?? []
        #expect(todos.map(\.subject) == ["读代码", "改动画"])
        #expect(todos.map(\.status) == [.completed, .inProgress])
    }

    @Test func webSearchItemsShowUpAsBrowsing() {
        let parser = CodexRolloutParser(session: session)
        let events = parse(parser, line("2026-09-23T01:55:03.425Z", "event_msg",
            #"{"type":"item_completed","item":{"type":"WebSearch","id":"ws-1","query":"blender 5 release"}}"#))
        #expect(events.map(\.kind) == [.activityStart, .activityEnd])
        #expect(events.first?.activity == .read_web)
        #expect(events.first?.detail == "搜索网页 blender 5 release")
    }
}
