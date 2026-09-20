import Foundation
import ImageIO
import Testing
@testable import YukioCore

@Suite struct ShellClassifierTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言
    @Test(arguments: [
        ("swift test", PetState.verify),
        ("pytest -q", .verify),
        ("FOO=1 pytest tests/", .verify),
        ("python3 scripts/verify_package.py", .verify),
        ("npm run test:unit", .verify),
        ("npm test", .verify),
        ("bash -lc 'go test ./...'", .verify),
        ("./run_tests.sh", .verify),
        ("cargo clippy", .verify),
        ("cd YukioPlayer && swift build 2>&1 | tail -3", .default_work),
        ("npm install", .default_work),
        ("make", .default_work),
        ("echo done", .default_work),
        ("cat README.md", .read_file),
        ("sed -n '1,20p' a.swift", .read_file),
        ("ls -la 2>/dev/null", .read_file),
        ("grep foo x >/dev/null 2>&1", .read_file),
        ("rg TODO | wc -l", .read_file),
        ("git status && git diff", .read_file),
        ("sed -i '' 's/a/b/' f.txt", .write_file),
        ("echo hi > out.txt", .write_file),
        ("mkdir -p a/b && cp x y", .write_file),
        ("cat > f.txt <<'EOF'\nhello\nEOF", .write_file),
        ("git commit -m 'test it'", .write_file),
        ("curl -s https://example.com", .read_web),
        ("open https://example.com", .read_web),
    ])
    func shell(_ command: String, _ expected: PetState) {
        #expect(ClaudeToolClassifier.classifyShell(command) == expected, "\(command)")
    }
}

@Suite struct ToolClassifierTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言
    func c(_ tool: String, _ input: [String: Any] = [:]) -> ToolClassification {
        ClaudeToolClassifier.classify(tool: tool, input: input)
    }

    @Test func builtIns() {
        #expect(c("Read", ["file_path": "/a/b.PNG"]) == .activity(.view_image))
        #expect(c("Read", ["file_path": "/a/b.swift"]) == .activity(.read_file))
        #expect(c("Grep") == .activity(.read_file))
        #expect(c("Edit") == .activity(.write_file))
        #expect(c("MultiEdit") == .activity(.write_file))
        #expect(c("WebSearch") == .activity(.read_web))
        #expect(c("Bash", ["command": "swift test"]) == .activity(.verify))
        #expect(c("TaskOutput") == .continuePrevious)
        #expect(c("TodoWrite") == .activity(.thinking))
        #expect(c("AskUserQuestion") == .activity(.question_for_user))
        #expect(c("Agent") == .activity(.default_work))
        #expect(c("SomethingNew") == .activity(.default_work))
    }

    @Test func mcpTools() {
        #expect(c("mcp__Claude_Browser__computer", ["action": "screenshot"]) == .activity(.view_image))
        #expect(c("mcp__Claude_Browser__computer", ["action": "left_click"]) == .activity(.read_web))
        #expect(c("mcp__Claude_Browser__navigate") == .activity(.read_web))
        #expect(c("mcp__computer-use__app_screenshot") == .activity(.view_image))
        #expect(c("mcp__computer-use__app_click") == .activity(.default_work))
        #expect(c("mcp__notion__search") == .activity(.default_work))
    }
}

@Suite struct TranscriptParserTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言
    let p = ClaudeTranscriptParser()

    func line(_ json: String) -> [PetEvent] { p.events(fromLine: Data(json.utf8)) }
    func kinds(_ json: String) -> [PetEvent.Kind] { line(json).map(\.kind) }

    let head = #""sessionId":"S1","timestamp":"2026-09-13T12:00:00.000Z""#

    @Test func userPromptStartsTask() {
        #expect(kinds(#"{"type":"user",\#(head),"message":{"role":"user","content":"帮我修一下"}}"#) == [.taskStart])
        #expect(kinds(#"{"type":"user",\#(head),"message":{"role":"user","content":[{"type":"text","text":"hi"}]}}"#) == [.taskStart])
    }

    @Test func toolUseAndResultPair() {
        let start = line(#"{"type":"assistant",\#(head),"message":{"stop_reason":"tool_use","content":[{"type":"tool_use","id":"tu_1","name":"Bash","input":{"command":"swift test"}}]}}"#)
        #expect(start.count == 1)
        #expect(start[0].kind == .activityStart && start[0].eventID == "tu_1" && start[0].activity == .verify)
        #expect(start[0].session == "S1" && start[0].ts == 1_789_300_800_000)
        let end = line(#"{"type":"user",\#(head),"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_1","content":"ok"}]}}"#)
        #expect(end.map(\.kind) == [.activityEnd] && end[0].eventID == "tu_1")
    }

    @Test func finalTextEndsTaskButCommentaryDoesNot() {
        #expect(kinds(#"{"type":"assistant",\#(head),"message":{"stop_reason":"end_turn","content":[{"type":"text","text":"完成"}]}}"#) == [.finalAnswer, .taskEnd])
        #expect(kinds(#"{"type":"assistant",\#(head),"message":{"stop_reason":"tool_use","content":[{"type":"text","text":"先看看"}]}}"#) == [.thinking])
        #expect(kinds(#"{"type":"assistant",\#(head),"message":{"stop_reason":"end_turn","content":[{"type":"thinking","thinking":""}]}}"#) == [.thinking])
    }

    @Test func interruptionsSidechainsAndLocalCommands() {
        #expect(kinds(#"{"type":"user",\#(head),"message":{"role":"user","content":[{"type":"text","text":"[Request interrupted by user]"}]}}"#) == [.taskAbort])
        #expect(kinds(#"{"type":"user",\#(head),"isSidechain":true,"message":{"role":"user","content":"x"}}"#) == [])
        #expect(kinds(#"{"type":"user",\#(head),"message":{"role":"user","content":"<local-command-stdout>ok</local-command-stdout>"}}"#) == [])
        #expect(kinds(#"{"type":"user",\#(head),"isMeta":true,"message":{"role":"user","content":"x"}}"#) == [])
        #expect(kinds(#"{"type":"assistant",\#(head),"message":{"model":"<synthetic>","content":[{"type":"text","text":"x"}]}}"#) == [.taskAbort])
        #expect(kinds(#"{"type":"attachment",\#(head)}"#) == [])
        #expect(kinds("not json") == [])
    }

    @Test func toolErrorsAndApiErrorsAreFailuresButRejectionIsNot() {
        let fail = line(#"{"type":"user",\#(head),"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_1","is_error":true,"content":"Exit code 1\nFAILED"}]}}"#)
        #expect(fail.map(\.kind) == [.activityFailed] && fail[0].eventID == "tu_1")
        #expect(kinds(#"{"type":"user",\#(head),"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_2","is_error":true,"content":[{"type":"text","text":"<tool_use_error>String to replace not found</tool_use_error>"}]}]}}"#) == [.activityFailed])
        // 你拒绝授权不是她的失败。
        #expect(kinds(#"{"type":"user",\#(head),"message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tu_3","is_error":true,"content":"The user doesn't want to proceed with this tool use."}]}}"#) == [.activityEnd])
        #expect(kinds(#"{"type":"assistant",\#(head),"isApiErrorMessage":true,"message":{"model":"<synthetic>","content":[{"type":"text","text":"API Error: x"}]}}"#) == [.taskFailed])
        #expect(kinds(#"{"type":"assistant",\#(head),"isApiErrorMessage":false,"message":{"model":"<synthetic>","content":[{"type":"text","text":"No response requested."}]}}"#) == [.taskAbort])
    }
}

@Suite struct HookParserTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言
    @Test func hookEvents() {
        let p = ClaudeHookParser()
        let pre = p.events(from: ["hook_event_name": "PreToolUse", "session_id": "S", "tool_name": "Edit",
                                  "tool_input": ["file_path": "a"], "tool_use_id": "t1"], receivedAt: 5)
        #expect(pre.map(\.kind) == [.activityStart] && pre[0].activity == .write_file && pre[0].eventID == "t1" && pre[0].ts == 5)
        #expect(p.events(from: ["hook_event_name": "PostToolUse", "session_id": "S", "tool_use_id": "t1"], receivedAt: 6).map(\.kind) == [.activityEnd])
        // 工具失败一般没有 PostToolUse（由转录补）；响应里带错误时这里也认出来。
        #expect(p.events(from: ["hook_event_name": "PostToolUse", "session_id": "S", "tool_use_id": "t1",
                                "tool_response": ["is_error": true, "error": "Exit code 1"]], receivedAt: 6).map(\.kind) == [.activityFailed])
        #expect(p.events(from: ["hook_event_name": "PostToolUse", "session_id": "S", "tool_use_id": "t1",
                                "tool_response": ["is_error": true, "error": "The user doesn't want to proceed with this tool use."]], receivedAt: 6).map(\.kind) == [.activityEnd])
        #expect(p.events(from: ["hook_event_name": "PostToolUse", "session_id": "S", "tool_use_id": "t1",
                                "tool_response": ["is_interrupt": true]], receivedAt: 6).map(\.kind) == [.activityEnd])
        // Claude Code 并没有 PostToolUseFailure / StopFailure 这两个事件名。
        #expect(p.events(from: ["hook_event_name": "PostToolUseFailure", "session_id": "S"], receivedAt: 6).isEmpty)
        #expect(p.events(from: ["hook_event_name": "UserPromptSubmit", "session_id": "S"], receivedAt: 1).map(\.kind) == [.taskStart])
        #expect(p.events(from: ["hook_event_name": "Stop", "session_id": "S"], receivedAt: 9).map(\.kind) == [.finalAnswer, .taskEnd])
        #expect(p.events(from: ["hook_event_name": "Notification", "session_id": "S"], receivedAt: 9).isEmpty)
    }
}

@Suite struct JSONObjectStreamTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言
    @Test func splitsAcrossChunksAndHandlesBracesInStrings() {
        var s = JSONObjectStream()
        let text = #"{"a":"}{","b":[1,{"c":2}]}"# + "\n" + #"{"x":"\"quoted\""}"# + "\n{\n  \"multi\": true\n}"
        let bytes = Array(text.utf8)
        var out: [Data] = []
        for chunk in stride(from: 0, to: bytes.count, by: 7) {
            out += s.append(Data(bytes[chunk..<min(chunk + 7, bytes.count)]))
        }
        #expect(out.count == 3)
        let objs = out.compactMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        #expect(objs.count == 3)
        #expect(objs[0]["a"] as? String == "}{")
        #expect(objs[2]["multi"] as? Bool == true)
    }

    @Test func keepsPartialLineUntilComplete() {
        var s = JSONObjectStream()
        #expect(s.append(Data(#"{"type":"us"#.utf8)).isEmpty)
        #expect(s.append(Data(#"er"}"#.utf8)).count == 1)
    }
}

@Suite struct TimelineAndCatalogTests {
    init() { L10n.language = .chinese }   // 这些测试按中文文案断言
    static var assetsRoot: URL {
        URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("Resources/Assets")
    }

    @Test func realAssetsLoadAndFramesStayInBounds() throws {
        let catalog = try AnimationCatalog.load(assetsRoot: Self.assetsRoot)
        let problems = catalog.validate { path in
            let url = Self.assetsRoot.appendingPathComponent(path)
            guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
                  let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any],
                  let w = props[kCGImagePropertyPixelWidth] as? Int,
                  let h = props[kCGImagePropertyPixelHeight] as? Int else { return nil }
            return (w, h)
        }
        #expect(problems.isEmpty, "\(problems)")
        // 小幅动作（tools/motion 生成）覆盖了原图条：一张底图加局部变形，循环播放。
        for state in PetState.allCases {
            let spec = catalog.spec(for: state)
            #expect(spec.assetPath == "motion/\(state.rawValue).webp", "\(state)")
            #expect(spec.loop, "\(state)")
        }
        // 递交报告、沮丧先播一次（递出、垂眼），之后只循环眨眼等小动作。
        #expect(catalog.spec(for: .respond).loopStart > 0)
        #expect(catalog.spec(for: .failed).loopStart > 0)
        #expect(catalog.spec(for: .thinking).loopStart == 0)
        // 拖动时被大手拎着：这一帧比常规帧高，还带着抓手点与头顶线。
        let held = catalog.specs[AnimationCatalog.heldID]
        #expect(held?.assetPath == "base/held.png")
        #expect(held?.frameHeight == 240)
        // 抓手点在头发顶端上方的空处（那只大手看不见），头顶线与站立图一致。
        #expect(held?.hang?.headTop == 16)
        #expect((held?.hang?.gripY ?? 99) < (held?.hang?.headTop ?? 0))
    }

    @Test func loopingTimelineCycles() {
        let spec = AnimationSpec(id: "t", label: "", assetPath: "", frameWidth: 1, frameHeight: 1,
                                 sequence: [0, 1, 2, 1, 0], durationsMs: [2400, 200, 300, 200, 1800],
                                 loop: true, holdLastFrame: false)
        var tl = SpriteTimeline(spec: spec, now: 0)
        tl.advance(to: 2399); #expect(tl.frame == 0)
        tl.advance(to: 2400); #expect(tl.frame == 1)
        tl.advance(to: 2600); #expect(tl.frame == 2)
        tl.advance(to: 4900); #expect(tl.frame == 0 && tl.step == 0)   // 4900 = 一整圈，回到开头
    }

    @Test func reportPlaysOnceAndHoldsLastFrame() {
        let spec = AnimationSpec(id: "respond", label: "", assetPath: "", frameWidth: 1, frameHeight: 1,
                                 sequence: [0, 1, 2, 3], durationsMs: [1200, 220, 220, 1200],
                                 loop: false, holdLastFrame: true)
        var tl = SpriteTimeline(spec: spec, now: 0)
        tl.advance(to: 60_000)
        #expect(tl.frame == 3 && tl.finished && tl.nextChangeAt == nil)
    }
}
