import Foundation

/// Claude Code 会话转录（~/.claude/projects/<项目>/<会话>.jsonl）→ 事件。
///
/// 这是 Claude Code 本地写入的会话记录，不是公开 API；字段可能随版本变化。
/// 解析只读取：条目类型、会话 ID、时间戳、会话标题、请求第一行、工具名与输入（用于分类和简短说明）、
/// 任务清单、工具结果 ID、结束原因。不保存、不上传任何对话内容。
public struct ClaudeTranscriptParser: Sendable {
    public static let source = "claude-transcript"

    public init() {}

    public func events(fromLine data: Data) -> [PetEvent] {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return [] }
        return events(from: obj)
    }

    public func events(from obj: [String: Any]) -> [PetEvent] {
        guard let type = obj["type"] as? String,
              let session = obj["sessionId"] as? String else { return [] }
        // 子代理（sidechain）的活动不驱动主角色。
        if obj["isSidechain"] as? Bool == true { return [] }
        // 会话标题（大任务）。这两类条目不带时间戳，用 0：只更新标题，不影响活动与失联判断。
        if type == "custom-title" || type == "ai-title" {
            guard let title = (obj["customTitle"] ?? obj["aiTitle"]) as? String else { return [] }
            return [PetEvent(ts: 0, source: Self.source, session: session, kind: .sessionTitle, detail: title)]
        }
        guard let ts = PetEvent.parseTimestamp(obj["timestamp"] as? String) else { return [] }

        func ev(_ kind: PetEvent.Kind, id: String? = nil, activity: PetState? = nil, tool: String? = nil,
                detail: String? = nil, todos: [TodoItem]? = nil) -> PetEvent {
            PetEvent(ts: ts, source: Self.source, session: session, kind: kind, eventID: id, activity: activity,
                     tool: tool, detail: detail, todos: todos)
        }

        switch type {
        case "user":
            if obj["isMeta"] as? Bool == true || obj["isCompactSummary"] as? Bool == true { return [] }
            let message = obj["message"] as? [String: Any]
            let content = message?["content"]
            if let blocks = content as? [[String: Any]] {
                let results = blocks.filter { $0["type"] as? String == "tool_result" }
                if !results.isEmpty {
                    var out = results.compactMap { (b: [String: Any]) -> PetEvent? in
                        guard let id = b["tool_use_id"] as? String else { return nil }
                        return ev(Self.isFailure(b) ? .activityFailed : .activityEnd, id: id)
                    }
                    // TaskCreate 新任务的编号只在结果里。
                    if let item = ClaudeTasks.created(fromResult: obj["toolUseResult"]) {
                        out.append(ev(.todoUpdate, todos: [item]))
                    }
                    return out
                }
                let text = blocks.compactMap { $0["type"] as? String == "text" ? $0["text"] as? String : nil }
                    .joined(separator: "\n")
                return userText(text, hasOtherBlocks: blocks.count > 0).map { [ev($0, detail: Self.promptLine(text))] } ?? []
            }
            if let text = content as? String {
                return userText(text, hasOtherBlocks: false).map { [ev($0, detail: Self.promptLine(text))] } ?? []
            }
            return []

        case "assistant":
            guard let message = obj["message"] as? [String: Any] else { return [] }
            if message["model"] as? String == "<synthetic>" {
                // 客户端合成的消息：本轮不会再有真实回答。
                // API 报错带 isApiErrorMessage=true，算失败；“No response requested.”等中断提示不算。
                return [ev(obj["isApiErrorMessage"] as? Bool == true ? .taskFailed : .taskAbort)]
            }
            let stop = message["stop_reason"] as? String
            let blocks = (message["content"] as? [[String: Any]]) ?? []
            var out: [PetEvent] = []
            for b in blocks {
                switch b["type"] as? String {
                case "tool_use":
                    let name = (b["name"] as? String) ?? ""
                    let input = (b["input"] as? [String: Any]) ?? [:]
                    let activity: PetState?
                    switch ClaudeToolClassifier.classify(tool: name, input: input) {
                    case .activity(let s): activity = s
                    case .continuePrevious: activity = nil
                    }
                    out.append(ev(.activityStart, id: b["id"] as? String, activity: activity, tool: name,
                                  detail: ClaudeToolClassifier.describe(tool: name, input: input)))
                    if let t = ClaudeTasks.events(tool: name, input: input) {
                        out.append(ev(t.kind, todos: t.items))
                    }
                case "thinking", "redacted_thinking":
                    out.append(ev(.thinking))
                case "text":
                    if stop == "end_turn" || stop == "stop_sequence" {
                        out.append(ev(.finalAnswer))
                        out.append(ev(.taskEnd))
                    } else {
                        // 调用工具前的过程说明不是最终回答。
                        out.append(ev(.thinking))
                    }
                default:
                    break
                }
            }
            return out

        case "system":
            // Stop hook 摘要只在一轮结束后出现，可作为结束的补充信号。
            return obj["subtype"] as? String == "stop_hook_summary" ? [ev(.taskEnd)] : []

        default:
            return []
        }
    }

    private func userText(_ text: String, hasOtherBlocks: Bool) -> PetEvent.Kind? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.hasPrefix("[Request interrupted by user") { return .taskAbort }
        // 本地命令（/clear、/model 等）的回显不会触发模型回答。
        if t.hasPrefix("<local-command-") || t.hasPrefix("<command-name>") || t.hasPrefix("<command-message>") {
            return nil
        }
        if t.isEmpty && !hasOtherBlocks { return nil }
        return .taskStart
    }

    /// 请求的第一行（跳过标签行、合并空白），没有会话标题时当作“大任务”。
    static func promptLine(_ text: String) -> String? {
        for raw in text.split(whereSeparator: \.isNewline) {
            let line = raw.split(whereSeparator: \.isWhitespace).joined(separator: " ")
            if line.isEmpty || line.hasPrefix("<") { continue }
            return String(line.prefix(80))
        }
        return nil
    }

    /// 工具结果是否算失败：is_error 为真，且不是用户拒绝授权或中断（这两种不让她沮丧）。
    static func isFailure(_ result: [String: Any]) -> Bool {
        guard result["is_error"] as? Bool == true else { return false }
        let text: String
        if let s = result["content"] as? String {
            text = s
        } else if let parts = result["content"] as? [[String: Any]] {
            text = parts.compactMap { $0["text"] as? String }.joined(separator: "\n")
        } else {
            text = ""
        }
        return !(text.contains("doesn't want to proceed") || text.hasPrefix("[Request interrupted"))
    }
}

/// Claude Code 官方 hooks 的 stdin JSON → 事件。
/// 需要用户自行在 settings.json 中启用 hooks（见 integrations/claude-hooks）。
public struct ClaudeHookParser: Sendable {
    public static let source = "claude-hook"

    public init() {}

    /// receivedAt：播放器收到这条记录的时间（hook 输入本身不带时间戳）。
    public func events(from obj: [String: Any], receivedAt: Double) -> [PetEvent] {
        guard let name = obj["hook_event_name"] as? String,
              let session = obj["session_id"] as? String else { return [] }
        let ts = (obj["yukio_ts_ms"] as? Double) ?? receivedAt
        func ev(_ kind: PetEvent.Kind, id: String? = nil, activity: PetState? = nil, tool: String? = nil,
                detail: String? = nil, todos: [TodoItem]? = nil) -> PetEvent {
            PetEvent(ts: ts, source: Self.source, session: session, kind: kind, eventID: id, activity: activity,
                     tool: tool, detail: detail, todos: todos)
        }
        switch name {
        case "UserPromptSubmit":
            return [ev(.taskStart, detail: (obj["prompt"] as? String).flatMap(ClaudeTranscriptParser.promptLine))]
        case "PreToolUse":
            let tool = (obj["tool_name"] as? String) ?? ""
            let input = (obj["tool_input"] as? [String: Any]) ?? [:]
            let activity: PetState?
            switch ClaudeToolClassifier.classify(tool: tool, input: input) {
            case .activity(let s): activity = s
            case .continuePrevious: activity = nil
            }
            var out = [ev(.activityStart, id: obj["tool_use_id"] as? String, activity: activity, tool: tool,
                          detail: ClaudeToolClassifier.describe(tool: tool, input: input))]
            if let t = ClaudeTasks.events(tool: tool, input: input) {
                out.append(ev(t.kind, todos: t.items))
            }
            return out
        case "PostToolUse":
            // Claude Code 只在工具成功后触发 PostToolUse，失败时通常不发这条；
            // 工具失败与整轮失败由会话转录的 is_error / API 报错条目补上（两个来源按 tool_use_id 去重）。
            // 万一响应里带了错误信息，这里也认出来。
            var out = [ev(Self.isFailure(obj["tool_response"]) ? .activityFailed : .activityEnd,
                          id: obj["tool_use_id"] as? String, tool: obj["tool_name"] as? String)]
            if let item = ClaudeTasks.created(fromResult: obj["tool_response"]) {
                out.append(ev(.todoUpdate, todos: [item]))
            }
            return out
        case "Stop":
            return [ev(.finalAnswer), ev(.taskEnd)]
        case "SessionEnd":
            return [ev(.taskAbort)]
        default:
            return []
        }
    }

    /// hook 的 tool_response 是否表示失败：带 is_error 或非空 error 字段。
    /// 你拒绝授权、主动中断都不算她的失败。
    static func isFailure(_ response: Any?) -> Bool {
        guard let dict = response as? [String: Any], dict["is_interrupt"] as? Bool != true else { return false }
        let text = (dict["error"] as? String) ?? ""
        guard dict["is_error"] as? Bool == true || !text.isEmpty else { return false }
        return !(text.contains("doesn't want to proceed") || text.hasPrefix("[Request interrupted"))
    }
}

/// Claude Code 任务清单工具 → 任务清单事件。
/// TodoWrite 每次给出完整清单；TaskCreate 的编号在结果里（toolUseResult.task）；TaskUpdate 给出编号与新状态。
enum ClaudeTasks {
    static func events(tool: String, input: [String: Any]) -> (kind: PetEvent.Kind, items: [TodoItem])? {
        switch tool {
        case "TodoWrite":
            guard let todos = input["todos"] as? [[String: Any]] else { return nil }
            let items = todos.enumerated().map { (i, t) in
                TodoItem(id: idString(t["id"]) ?? String(i),
                         subject: (t["content"] as? String) ?? (t["activeForm"] as? String),
                         status: (t["status"] as? String).flatMap(TodoItem.Status.init(rawValue:)) ?? .pending)
            }
            return (.todoList, items)
        case "TaskUpdate":
            guard let id = idString(input["taskId"]) else { return nil }
            let status = (input["status"] as? String).flatMap(TodoItem.Status.init(rawValue:))
            let subject = input["subject"] as? String
            guard status != nil || subject != nil else { return nil }
            return (.todoUpdate, [TodoItem(id: id, subject: subject, status: status)])
        default:
            return nil
        }
    }

    /// TaskCreate 的结果：{"task": {"id": "3", "subject": "…"}}。
    static func created(fromResult result: Any?) -> TodoItem? {
        guard let task = (result as? [String: Any])?["task"] as? [String: Any],
              let id = idString(task["id"]), let subject = task["subject"] as? String else { return nil }
        return TodoItem(id: id, subject: subject)
    }

    static func idString(_ v: Any?) -> String? {
        if let s = v as? String { return s }
        if let n = v as? Int { return String(n) }
        return nil
    }
}

/// 从字节流中切出完整的顶层 JSON 对象。兼容 JSONL（一行一个）与多行 JSON 直接拼接。
public struct JSONObjectStream: Sendable {
    private var buffer = Data()
    private var scanIndex = 0
    private var depth = 0
    private var inString = false
    private var escape = false
    private var objectStart: Int?
    public var maxBufferBytes = 16 * 1024 * 1024

    public init() {}

    public mutating func append(_ data: Data) -> [Data] {
        buffer.append(data)
        var out: [Data] = []
        buffer.withUnsafeBytes { (raw: UnsafeRawBufferPointer) in
            let bytes = raw.bindMemory(to: UInt8.self)
            while scanIndex < bytes.count {
                let b = bytes[scanIndex]
                if objectStart == nil {
                    if b == UInt8(ascii: "{") { objectStart = scanIndex; depth = 1; inString = false; escape = false }
                } else if inString {
                    if escape { escape = false }
                    else if b == UInt8(ascii: "\\") { escape = true }
                    else if b == UInt8(ascii: "\"") { inString = false }
                } else {
                    switch b {
                    case UInt8(ascii: "\""): inString = true
                    case UInt8(ascii: "{"), UInt8(ascii: "["): depth += 1
                    case UInt8(ascii: "}"), UInt8(ascii: "]"):
                        depth -= 1
                        if depth == 0, let start = objectStart {
                            out.append(Data(bytes[start...scanIndex]))
                            objectStart = nil
                        }
                    default: break
                    }
                }
                scanIndex += 1
            }
        }
        // 丢弃已处理部分。
        let keepFrom = objectStart ?? scanIndex
        if keepFrom > 0 {
            buffer.removeSubrange(0..<keepFrom)
            scanIndex -= keepFrom
            if objectStart != nil { objectStart = 0 }
        }
        if buffer.count > maxBufferBytes {
            buffer.removeAll(); scanIndex = 0; objectStart = nil; depth = 0; inString = false
        }
        return out
    }
}
