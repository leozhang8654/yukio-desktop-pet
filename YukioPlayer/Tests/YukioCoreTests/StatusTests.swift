import Foundation
import Testing
@testable import YukioCore

extension Harness {
    func event(_ kind: PetEvent.Kind, id: String? = nil, _ activity: PetState? = nil,
               detail: String? = nil, todos: [TodoItem]? = nil) {
        router.ingest(PetEvent(ts: now, source: "test", session: session, kind: kind, eventID: id,
                               activity: activity, detail: detail, todos: todos), now: now)
    }

    var line: StatusLine? { router.statusLine(now: now) }
}

@Suite struct StatusLineTests {
    @Test func hiddenWhenIdleAndTextFollowsTheDisplayedPose() {
        let h = Harness()
        #expect(h.line == nil)
        h.event(.taskStart, detail: "修一下登录页")
        h.run(to: 1000)
        #expect(h.line == StatusLine(title: "修一下登录页", current: "思考中", progress: nil))
        h.event(.activityStart, id: "a", .write_file, detail: "编辑 main.swift")
        h.run(to: 1200)
        // 还没过防抖：文字仍跟着正在显示的动作。
        #expect(h.line?.current == "思考中")
        h.run(to: 3000)
        #expect(h.line?.current == "编辑 main.swift")
        // 会话标题优先于请求第一行。
        h.event(.sessionTitle, detail: "桌宠缺失状态")
        #expect(h.line?.title == "桌宠缺失状态")
        h.event(.activityEnd, id: "a")
        h.event(.finalAnswer)
        h.event(.taskEnd)
        h.run(to: 6000)
        #expect(h.line?.current == "已回答")
        h.run(to: 20000)
        // 勾选卡一直举着，气泡跟着留着；点一下才一起收走。
        #expect(h.line?.current == "已完成 · 点她跳过去")
        #expect(h.router.dismissCompletion(now: h.now))
        #expect(h.line == nil)
    }

    @Test func todoListGivesCurrentItemAndProgress() {
        let h = Harness()
        h.event(.taskStart)
        h.event(.todoUpdate, todos: [TodoItem(id: "1", subject: "读代码"), TodoItem(id: "2", subject: "改代码"),
                                     TodoItem(id: "3", subject: "跑测试")])
        h.event(.todoUpdate, todos: [TodoItem(id: "1", status: .completed), TodoItem(id: "2", status: .inProgress)])
        h.event(.activityStart, id: "e", .write_file, detail: "编辑 a.swift")
        h.run(to: 1000)
        #expect(h.line == StatusLine(title: nil, current: "改代码", progress: .init(done: 1, total: 3)))
        // 一批全部完成后又新建任务：进度从头算。
        h.event(.todoUpdate, todos: [TodoItem(id: "2", status: .completed), TodoItem(id: "3", status: .completed)])
        h.event(.todoUpdate, todos: [TodoItem(id: "4", subject: "写文档")])
        #expect(h.line?.progress == .init(done: 0, total: 1))
        #expect(h.line?.current == "编辑 a.swift")
        h.event(.todoUpdate, todos: [TodoItem(id: "4", status: .deleted)])
        #expect(h.line?.progress == nil)
    }

    @Test func failureAndWaitingForUserTexts() {
        let h = Harness()
        h.event(.taskStart)
        h.event(.activityStart, id: "t", .verify, detail: "$ swift test")
        h.run(to: 3000)
        h.event(.activityFailed, id: "t")
        h.run(to: 4000)
        #expect(h.line?.current == "出错：$ swift test")
        h.event(.activityStart, id: "q", .question_for_user, detail: "等你回答")
        h.run(to: 7000)
        #expect(h.router.displayed == .question_for_user)
        #expect(h.line?.current == "等你回答 · 点她跳过去")
        // 回答完成：先递交报告，再举勾选卡，气泡跟着说“已完成”。
        h.event(.activityEnd, id: "q")
        h.event(.finalAnswer)
        h.event(.taskEnd)
        h.run(to: 12000)
        #expect(h.router.displayed == .task_complete)
        #expect(h.line?.current == "已完成 · 点她跳过去")
    }
}

@Suite struct HeldValueTests {
    @Test func eachTextStaysThenJumpsToTheLatest() {
        var v = HeldValue<String?>(nil, minHoldMs: 1000)
        var changed = v.update("a", now: 0, immediate: true)
        #expect(changed)
        changed = v.update("b", now: 300)
        #expect(!changed)
        changed = v.update("c", now: 600)
        #expect(!changed && v.value == "a")
        changed = v.update("c", now: 1000)
        #expect(changed && v.value == "c")
        changed = v.update(nil, now: 1100, immediate: true)
        #expect(changed && v.value == nil)
    }
}

@Suite struct DescribeTests {
    func d(_ tool: String, _ input: [String: Any] = [:]) -> String? {
        ClaudeToolClassifier.describe(tool: tool, input: input)
    }

    @Test func builtInTools() {
        #expect(d("Read", ["file_path": "/a/b/README.md"]) == "阅读 README.md")
        #expect(d("Read", ["file_path": "/a/shot.PNG"]) == "查看 shot.PNG")
        #expect(d("Edit", ["file_path": "/x/main.swift"]) == "编辑 main.swift")
        #expect(d("Write", ["file_path": "notes.md"]) == "写入 notes.md")
        #expect(d("Grep", ["pattern": "TODO"]) == "搜索 TODO")
        #expect(d("Glob", ["pattern": "**/*.swift"]) == "查找 **/*.swift")
        #expect(d("WebFetch", ["url": "https://www.example.com/a/b"]) == "浏览 example.com")
        #expect(d("WebSearch", ["query": "swift testing"]) == "搜索网页 swift testing")
        #expect(d("AskUserQuestion") == "等你回答")
        #expect(d("TaskUpdate", ["taskId": "1", "status": "completed"]) == "整理任务清单")
        #expect(d("Agent", ["description": "Explore code"]) == "委派：Explore code")
        #expect(d("TaskOutput") == nil)
        #expect(d("mcp__Claude_Browser__computer", ["action": "screenshot"]) == "截图")
        #expect(d("mcp__notion__search") == "search")
        #expect(d("SomethingNew") == "SomethingNew")
    }

    @Test(arguments: [
        ("cd YukioPlayer && swift build 2>&1 | tail -3", "swift build"),
        ("swift test", "swift test"),
        ("FOO=1 timeout 30 pytest -q tests/", "pytest -q tests/"),
        ("git status && git diff", "git status"),
        ("./scripts/build-app.sh", "build-app.sh"),
        ("bash -lc 'npm test'", "npm test"),
        ("python3 - <<'EOF'\nimport os\nEOF", "python3 -"),
        ("echo done", "echo done"),
    ])
    func shellSummary(_ command: String, _ expected: String) {
        #expect(ClaudeToolClassifier.shellSummary(command) == expected, "\(command)")
    }

    @Test func heredocScriptsPreferTheDescription() {
        #expect(d("Bash", ["command": "python3 - <<'EOF'\nprint(1)\nEOF", "description": "统计转录"]) == "统计转录")
        #expect(d("Bash", ["command": "swift test", "description": "Run tests"]) == "$ swift test")
    }
}

@Suite struct TaskInfoParserTests {
    let p = ClaudeTranscriptParser()
    func line(_ json: String) -> [PetEvent] { p.events(fromLine: Data(json.utf8)) }
    let head = #""sessionId":"S1","timestamp":"2026-09-13T12:00:00.000Z""#

    @Test func sessionTitlesAndPromptLine() {
        let t = line(#"{"type":"custom-title","customTitle":"桌宠缺失状态","sessionId":"S1"}"#)
        #expect(t.map(\.kind) == [.sessionTitle] && t[0].detail == "桌宠缺失状态")
        #expect(line(#"{"type":"ai-title","aiTitle":"Fix login","sessionId":"S1"}"#).first?.detail == "Fix login")
        let start = line(#"{"type":"user",\#(head),"message":{"role":"user","content":"  帮我修一下登录页\n细节如下"}}"#)
        #expect(start.map(\.kind) == [.taskStart] && start[0].detail == "帮我修一下登录页")
    }

    @Test func toolUseCarriesDetailAndTaskEvents() {
        let edit = line(#"{"type":"assistant",\#(head),"message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"tu_1","name":"Edit","input":{"file_path":"/a/Catalog.swift"}}]}}"#)
        #expect(edit.first?.detail == "编辑 Catalog.swift")
        let upd = line(#"{"type":"assistant",\#(head),"message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"tu_2","name":"TaskUpdate","input":{"taskId":"3","status":"in_progress"}}]}}"#)
        #expect(upd.map(\.kind) == [.activityStart, .todoUpdate])
        #expect(upd[1].todos == [TodoItem(id: "3", status: .inProgress)])
        let created = line(#"{"type":"user",\#(head),"toolUseResult":{"task":{"id":"3","subject":"实现气泡"}},"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_3","content":"Task #3 created successfully: 实现气泡"}]}}"#)
        #expect(created.map(\.kind) == [.activityEnd, .todoUpdate])
        #expect(created[1].todos == [TodoItem(id: "3", subject: "实现气泡")])
        let todo = line(#"{"type":"assistant",\#(head),"message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"tu_4","name":"TodoWrite","input":{"todos":[{"content":"读代码","status":"completed","activeForm":"读代码中"},{"content":"改代码","status":"in_progress","activeForm":"改代码中"}]}}]}}"#)
        #expect(todo.map(\.kind) == [.activityStart, .todoList])
        #expect(todo[1].todos == [TodoItem(id: "0", subject: "读代码", status: .completed),
                                  TodoItem(id: "1", subject: "改代码", status: .inProgress)])
    }
}
