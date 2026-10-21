import Foundation

/// GPT（Codex）的本机会话记录 → 事件。
///
/// Codex 把每条聊天写在 `~/.codex/sessions/<年>/<月>/<日>/rollout-<时间>-<会话 ID>.jsonl`，
/// 一行一条 JSON：`{"timestamp", "type", "payload"}`。这是 Codex 在本地写的记录、不是公开 API，
/// 字段会随版本变化；认不出的行直接跳过，只会少事件，不会崩溃，并按失联规则回空闲。
/// 只读取：条目类型、时间、工具名与参数（用于分类和简短说明）、成败、请求第一行与会话 ID，
/// 不保存、不上传任何对话内容。
///
/// 同一个文件里两套记录并存，都认：
///   * `response_item` —— 送给模型的那一份（`function_call`／`custom_tool_call`／`message`／`reasoning`），
///     工具**开始**时就写下，所以动作跟得上；
///   * `event_msg` —— 界面事件（`item_completed`／`task_complete`／`turn_aborted`），
///     工具**结束**之后才写，用来补成败和「一轮结束」。
/// 两套记录可能属于不同层级。仅显式调用引用或已知的同一 ID 可关联；其余回执保留为未关联。
///
/// 一个实例跟一个文件；结果按有依据的调用身份隔离，不能用到达顺序配对。
public final class CodexRolloutParser {
    public static let source = "codex"

    /// 会话 ID：先用文件名里的那个，读到 session_meta 就换成它写的。
    public private(set) var session: String
    private let results = CodexResultTracker()
    /// Result metadata for the last parsed record, including unlinked receipts.
    public private(set) var lastToolResults: [CodexToolResult] = []
    private var asyncQuestions: Set<String> = []

    public init(session: String = "") {
        self.session = session
    }

    // History persists this metadata-only correlation window with its cursor.
    // Display state and message/argument/output bodies are deliberately absent.
    private struct HistoryCheckpoint: Codable {
        let version: Int
        let session: String
        let results: CodexResultTracker.Checkpoint
    }
    var historyTurnID: String? { results.turnID }
    func historyCheckpoint() throws -> String {
        let data = try JSONEncoder().encode(HistoryCheckpoint(version: 1, session: session, results: results.checkpoint()))
        return String(decoding: data, as: UTF8.self)
    }
    static func fromHistoryCheckpoint(_ json: String) throws -> CodexRolloutParser {
        let state = try JSONDecoder().decode(HistoryCheckpoint.self, from: Data(json.utf8))
        guard state.version == 1 else { throw CocoaError(.coderReadCorrupt) }
        let parser = CodexRolloutParser(session: state.session)
        try parser.results.restore(state.results)
        return parser
    }

    public func events(fromLine data: Data, now: Double = 0) -> [PetEvent] {
        lastToolResults = []
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return [] }
        return events(from: obj, now: now)
    }

    public func events(from obj: [String: Any], now: Double = 0) -> [PetEvent] {
        lastToolResults = []
        // 新版把记录包在 payload 里，旧版直接写 ResponseItem；两种都认。
        let payload = (obj["payload"] as? [String: Any]) ?? obj
        let kind = (payload["type"] as? String) ?? (obj["type"] as? String) ?? ""
        let ts = PetEvent.parseTimestamp(obj["timestamp"] as? String)
            ?? PetEvent.parseTimestamp(payload["timestamp"] as? String)
            ?? now

        if kind == "session_meta" {
            if let id = (payload["session_id"] ?? payload["id"]) as? String, !id.isEmpty {
                if id != session { results.reset(); asyncQuestions.removeAll() }
                session = id
            }
            return []
        }
        if session.isEmpty, let id = (payload["thread_id"] ?? payload["session_id"]) as? String { session = id }
        // 会话 ID 还没拿到（文件名不合规、也还没读到 session_meta）：这条认不到人，跳过。
        guard !session.isEmpty else { return [] }
        if let thread = CodexResultTracker.identifier(payload["thread_id"]), thread != session { return [] }

        switch kind {
        case "task_started", "turn_context":
            if let turn = CodexResultTracker.identifier(payload["turn_id"]), turn != results.turnID {
                asyncQuestions.removeAll()
            }
            results.beginTurn(payload["turn_id"])
            return []
        // MARK: 一轮的开头与结尾（event_msg）
        case "task_complete":
            guard results.matchesTurn(payload["turn_id"]) else { return [] }
            asyncQuestions.removeAll()
            results.closeTurn()
            // 有回答才算答完：没有 last_agent_message 的一轮（被压缩、被接管）只算结束。
            let answered = (payload["last_agent_message"] as? String)?.isEmpty == false
            return answered ? [ev(ts, .finalAnswer), ev(ts, .taskEnd)] : [ev(ts, .taskEnd)]

        case "turn_aborted":
            guard results.matchesTurn(payload["turn_id"]) else { return [] }
            asyncQuestions.removeAll()
            results.closeTurn()
            // 用户按停、或被新一轮顶掉：都不算失败，不让她沮丧。
            let reason = (payload["reason"] as? String)?.lowercased() ?? ""
            return [ev(ts, reason.contains("error") ? .taskFailed : .taskAbort)]

        case "error", "stream_error":
            guard results.matchesTurn(payload["turn_id"]) else { return [] }
            asyncQuestions.removeAll()
            results.closeTurn()
            return [ev(ts, .taskFailed)]

        case "item_completed", "item_started", "item_updated":
            return item(payload["item"] as? [String: Any], payload: payload, ts: ts, completed: kind == "item_completed")

        // MARK: 模型这一轮的输入输出（response_item）
        case "message":
            let role = (payload["role"] as? String) ?? ""
            let text = Self.text(fromContent: payload["content"])
            if role == "user" {
                if let answered = Self.questionReplyCalls(text) {
                    return closeQuestions(answered, ts: ts)
                }
                guard let line = Self.promptLine(text) else { return [] }
                return closeAsyncQuestions(ts: ts) + [ev(ts, .taskStart, detail: line)]
            }
            if role == "assistant" {
                // 中间的过程说明不是最终回答：一轮什么时候结束由 task_complete 说了算。
                return text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? [] : [ev(ts, .thinking)]
            }
            return []

        case "reasoning":
            return [ev(ts, .thinking)]

        case "function_call", "custom_tool_call", "local_shell_call":
            return toolStart(payload, ts: ts)

        case "function_call_output", "custom_tool_call_output", "local_shell_call_output":
            return toolEnd(payload, ts: ts)

        case "web_search_call":
            let action = payload["action"] as? [String: Any]
            let query = (action?["query"] as? String) ?? (payload["query"] as? String)
            return searchPair(id: payload["id"] as? String, query: query, ts: ts)

        default:
            return []
        }
    }

    private func ev(_ ts: Double, _ kind: PetEvent.Kind, id: String? = nil, activity: PetState? = nil,
                    tool: String? = nil, detail: String? = nil, todos: [TodoItem]? = nil,
                    question: PetQuestion? = nil) -> PetEvent {
        PetEvent(ts: ts, source: Self.source, session: session, kind: kind, eventID: id, activity: activity,
                 tool: tool, detail: detail, todos: todos, question: question)
    }

    // MARK: event_msg 里的条目
    //
    // 这些条目是界面条目的回执，可能与外层 response_item 的工具不同，
    // 保存结果元数据；有身份依据时才补外层成败。网页搜索仍保留原有显示投影。

    private func item(_ item: [String: Any]?, payload: [String: Any], ts: Double, completed: Bool) -> [PetEvent] {
        guard let item, let type = item["type"] as? String else { return [] }
        switch type {
        case "UserMessage":
            guard completed else { return [] }
            let text = Self.text(fromContent: item["content"])
            if let answered = Self.questionReplyCalls(text) { return closeQuestions(answered, ts: ts) }
            guard let line = Self.promptLine(text) else { return [] }
            return closeAsyncQuestions(ts: ts) + [ev(ts, .taskStart, detail: line)]

        case "AgentMessage":
            guard completed else { return [] }
            // phase 有时写明这条是最终回答；没写就当过程说明。
            return [ev(ts, item["phase"] as? String == "final_answer" ? .finalAnswer : .thinking)]

        case "Reasoning":
            return completed ? [ev(ts, .thinking)] : []

        case "CommandExecution", "McpToolCall", "CollabAgentToolCall", "DynamicToolCall":
            guard completed else { return [] }
            lastToolResults = [results.record(session: session, payload: payload, item: item,
                                               sourceKind: "item_completed", timestamp: ts)]
            return []

        case "WebSearch":
            guard completed else { return [] }
            return searchPair(id: item["id"] as? String, query: item["query"] as? String, ts: ts)

        case "Extension":
            // 插件条目：只有网页搜索类的能一眼看懂，其余交给它对应的工具调用。
            guard completed, (item["kind"] as? String)?.hasPrefix("web.") == true else { return [] }
            return searchPair(id: item["id"] as? String, query: item["query"] as? String, ts: ts)

        case "TodoList", "PlanUpdate":
            guard completed, let todos = CodexPlan.items(from: item["items"] ?? item["plan"]) else { return [] }
            return [ev(ts, .todoList, todos: todos)]

        default:
            return []
        }
    }

    // MARK: 工具调用

    private func toolStart(_ payload: [String: Any], ts: Double) -> [PetEvent] {
        let name = (payload["name"] as? String) ?? ""
        let namespace = payload["namespace"] as? String
        // function_call 的参数是一段 JSON 文本；custom_tool_call 的 input 是一段脚本或补丁正文。
        let arguments = Self.dictionary(payload["arguments"]) ?? [:]
        let script = payload["input"] as? String
        let call = CodexResultTracker.identifier(payload["call_id"]) ?? CodexResultTracker.identifier(payload["id"])
        let (classification, detail) = CodexToolClassifier.classify(tool: name, namespace: namespace,
                                                                    arguments: arguments, script: script)
        let activity: PetState?
        switch classification {
        case .activity(let s): activity = s
        case .continuePrevious: activity = nil
        }
        guard results.isCurrent(payload["turn_id"]) || payload["turn_id"] == nil else { return [] }
        results.start(call)
        if name.lowercased() == "request_user_input_async", let call { asyncQuestions.insert(call) }
        var out = [ev(ts, .activityStart, id: call, activity: activity, tool: name, detail: detail,
                      question: CodexToolClassifier.question(tool: name, arguments: arguments))]
        if let todos = CodexPlan.items(from: arguments["plan"] ?? arguments["items"] ?? arguments["todos"]) {
            out.append(ev(ts, .todoList, todos: todos))
        }
        return out
    }

    private func toolEnd(_ payload: [String: Any], ts: Double) -> [PetEvent] {
        let result = results.record(session: session, payload: payload,
                                    sourceKind: (payload["type"] as? String) ?? "tool_output", timestamp: ts)
        lastToolResults = [result]
        // A missing ID must never close the router's most recent unrelated call.
        guard result.projectionEligible, let call = result.callID else { return [] }
        // An async acknowledgement only confirms that the question was displayed.
        // Keep it open until an answer/new user message or the turn ends.
        if asyncQuestions.contains(call),
           let output = Self.dictionary(payload["output"]), output["accepted"] as? Bool == true {
            return []
        }
        asyncQuestions.remove(call)
        // activityEnd is a display receipt, not an execution-success assertion.
        return [ev(ts, result.callOutcome == .failed ? .activityFailed : .activityEnd, id: call)]
    }

    private func closeAsyncQuestions(ts: Double) -> [PetEvent] {
        let events = asyncQuestions.sorted().map { ev(ts, .activityEnd, id: $0) }
        asyncQuestions.removeAll()
        return events
    }

    private func closeQuestions(_ calls: Set<String>, ts: Double) -> [PetEvent] {
        asyncQuestions.subtract(calls)
        return calls.sorted().map { ev(ts, .activityEnd, id: $0) }
    }

    /// Codex submits option/free-text replies inside a tagged user message.
    /// This is an answer, not an environment block or a new task. The desktop
    /// card presents question index 0, so other answers must not close it.
    static func questionReplyCalls(_ text: String) -> Set<String>? {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let start = "<send_user_message_question_reply>"
        let end = "</send_user_message_question_reply>"
        guard text.hasPrefix(start), text.hasSuffix(end) else { return nil }
        let body = String(text.dropFirst(start.count).dropLast(end.count))
        guard let data = body.data(using: .utf8),
              let replies = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else { return [] }
        return Set(replies.compactMap { reply in
            guard reply["answer"] is String,
                  let raw = reply["questionItemId"] as? String,
                  let bytes = raw.data(using: .utf8),
                  let id = (try? JSONSerialization.jsonObject(with: bytes)) as? [Any], id.count == 3,
                  let tool = id[0] as? String,
                  ["request_user_input_async", "request_user_input"].contains(tool.split(separator: ".").last.map(String.init) ?? tool),
                  let call = id[1] as? String, !call.isEmpty,
                  let index = id[2] as? Int, index == 0 else { return nil }
            return call
        })
    }

    /// 网页搜索在记录里只有「搜完了」这一条，没有开始。发一对开始／结束，让她照样看一下网页。
    private func searchPair(id: String?, query: String?, ts: Double) -> [PetEvent] {
        let call = id ?? "search-\(Int(ts))"
        let detail = query.map { tr("Searching the web: \($0)", "搜索网页 \($0)") }
        return [ev(ts, .activityStart, id: call, activity: .read_web, tool: "web_search", detail: detail),
                ev(ts, .activityEnd, id: call)]
    }

    // MARK: 取文字

    /// content 可能是字符串，也可能是 `[{"type": "input_text"/"text"/"output_text", "text": ...}]`。
    static func text(fromContent content: Any?) -> String {
        if let s = content as? String { return s }
        guard let parts = content as? [[String: Any]] else { return "" }
        return parts.compactMap { $0["text"] as? String }.joined(separator: "\n")
    }

    /// 请求的第一行。整条以 `<` 开头的是塞给模型的环境说明（`<app-context>` 之类），不是人说的话。
    static func promptLine(_ text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty || trimmed.hasPrefix("<") { return nil }
        return ClaudeTranscriptParser.promptLine(trimmed)
    }

    /// 参数可能已经是字典，也可能是一段 JSON 文本。
    static func dictionary(_ value: Any?) -> [String: Any]? {
        if let d = value as? [String: Any] { return d }
        guard let s = value as? String, let data = s.data(using: .utf8) else { return nil }
        return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
    }
}

/// `update_plan` 的清单 → 任务条目。Codex 每次给出完整清单，所以整体替换、编号用序号。
public enum CodexPlan {
    public static func items(from value: Any?) -> [TodoItem]? {
        guard let rows = value as? [[String: Any]], !rows.isEmpty else { return nil }
        var out: [TodoItem] = []
        for row in rows {
            let subject = (row["step"] as? String) ?? (row["text"] as? String) ?? (row["title"] as? String)
            guard let subject, !subject.isEmpty else { continue }
            let status: TodoItem.Status
            switch ((row["status"] as? String) ?? "").lowercased() {
            case "completed", "done", "complete": status = .completed
            case "in_progress", "inprogress", "running", "active": status = .inProgress
            default: status = .pending
            }
            out.append(TodoItem(id: String(out.count), subject: subject, status: status))
        }
        return out.isEmpty ? nil : out
    }
}
