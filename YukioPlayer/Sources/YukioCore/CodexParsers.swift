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
/// 一次工具调用两边各写一条，靠 `call_id` 配对；`item_completed` 只用来补成败，不再发一次开始。
///
/// 一个实例跟一个文件（也就是一条聊天）：会话 ID 与「上一次报的失败」都记在实例里。
public final class CodexRolloutParser {
    public static let source = "codex"

    /// 会话 ID：先用文件名里的那个，读到 session_meta 就换成它写的。
    public private(set) var session: String
    /// item_completed 报了失败、还没等到对应的输出：下一条输出算失败。
    private var pendingFailure = false

    public init(session: String = "") {
        self.session = session
    }

    public func events(fromLine data: Data, now: Double = 0) -> [PetEvent] {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return [] }
        return events(from: obj, now: now)
    }

    public func events(from obj: [String: Any], now: Double = 0) -> [PetEvent] {
        // 新版把记录包在 payload 里，旧版直接写 ResponseItem；两种都认。
        let payload = (obj["payload"] as? [String: Any]) ?? obj
        let kind = (payload["type"] as? String) ?? (obj["type"] as? String) ?? ""
        let ts = PetEvent.parseTimestamp(obj["timestamp"] as? String)
            ?? PetEvent.parseTimestamp(payload["timestamp"] as? String)
            ?? now

        if kind == "session_meta" {
            if let id = (payload["session_id"] ?? payload["id"]) as? String, !id.isEmpty { session = id }
            return []
        }
        if session.isEmpty, let id = (payload["thread_id"] ?? payload["session_id"]) as? String { session = id }
        // 会话 ID 还没拿到（文件名不合规、也还没读到 session_meta）：这条认不到人，跳过。
        guard !session.isEmpty else { return [] }

        switch kind {
        // MARK: 一轮的开头与结尾（event_msg）
        case "task_complete":
            pendingFailure = false
            // 有回答才算答完：没有 last_agent_message 的一轮（被压缩、被接管）只算结束。
            let answered = (payload["last_agent_message"] as? String)?.isEmpty == false
            return answered ? [ev(ts, .finalAnswer), ev(ts, .taskEnd)] : [ev(ts, .taskEnd)]

        case "turn_aborted":
            pendingFailure = false
            // 用户按停、或被新一轮顶掉：都不算失败，不让她沮丧。
            let reason = (payload["reason"] as? String)?.lowercased() ?? ""
            return [ev(ts, reason.contains("error") ? .taskFailed : .taskAbort)]

        case "error", "stream_error":
            pendingFailure = false
            return [ev(ts, .taskFailed)]

        case "item_completed", "item_started", "item_updated":
            return item(payload["item"] as? [String: Any], ts: ts, completed: kind == "item_completed")

        // MARK: 模型这一轮的输入输出（response_item）
        case "message":
            let role = (payload["role"] as? String) ?? ""
            let text = Self.text(fromContent: payload["content"])
            if role == "user" {
                guard let line = Self.promptLine(text) else { return [] }
                return [ev(ts, .taskStart, detail: line)]
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
    // 这些条目是「做完之后」的回执，工具的开始已经由 response_item 发过了，
    // 所以这里只补两样：报错（让她沮丧）、以及 response_item 里根本没有的网页搜索。

    private func item(_ item: [String: Any]?, ts: Double, completed: Bool) -> [PetEvent] {
        guard let item, let type = item["type"] as? String else { return [] }
        switch type {
        case "UserMessage":
            guard completed, let line = Self.promptLine(Self.text(fromContent: item["content"])) else { return [] }
            return [ev(ts, .taskStart, detail: line)]

        case "AgentMessage":
            guard completed else { return [] }
            // phase 有时写明这条是最终回答；没写就当过程说明。
            return [ev(ts, item["phase"] as? String == "final_answer" ? .finalAnswer : .thinking)]

        case "Reasoning":
            return completed ? [ev(ts, .thinking)] : []

        case "CommandExecution":
            if Self.failed(status: item["status"], exitCode: item["exit_code"]) { pendingFailure = true }
            return []

        case "McpToolCall", "CollabAgentToolCall", "DynamicToolCall":
            if Self.failed(status: item["status"], success: item["success"]) { pendingFailure = true }
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

    /// `status: "failed"`／非零退出码／`success: false` 算失败；被用户按停的不算（那是 turn_aborted）。
    static func failed(status: Any? = nil, exitCode: Any? = nil, success: Any? = nil) -> Bool {
        if let s = (status as? String)?.lowercased(), s == "failed" || s == "error" { return true }
        if let ok = success as? Bool, ok == false { return true }
        if let code = (exitCode as? NSNumber)?.intValue, code != 0 { return true }
        return false
    }

    // MARK: 工具调用

    private func toolStart(_ payload: [String: Any], ts: Double) -> [PetEvent] {
        let name = (payload["name"] as? String) ?? ""
        let namespace = payload["namespace"] as? String
        // function_call 的参数是一段 JSON 文本；custom_tool_call 的 input 是一段脚本或补丁正文。
        let arguments = Self.dictionary(payload["arguments"]) ?? [:]
        let script = payload["input"] as? String
        let call = (payload["call_id"] as? String) ?? (payload["id"] as? String)
        let (classification, detail) = CodexToolClassifier.classify(tool: name, namespace: namespace,
                                                                    arguments: arguments, script: script)
        let activity: PetState?
        switch classification {
        case .activity(let s): activity = s
        case .continuePrevious: activity = nil
        }
        pendingFailure = false
        var out = [ev(ts, .activityStart, id: call, activity: activity, tool: name, detail: detail,
                      question: CodexToolClassifier.question(tool: name, arguments: arguments))]
        if let todos = CodexPlan.items(from: arguments["plan"] ?? arguments["items"] ?? arguments["todos"]) {
            out.append(ev(ts, .todoList, todos: todos))
        }
        return out
    }

    private func toolEnd(_ payload: [String: Any], ts: Double) -> [PetEvent] {
        let call = (payload["call_id"] as? String) ?? (payload["id"] as? String)
        let failed = pendingFailure || Self.outputFailed(payload["output"])
        pendingFailure = false
        return [ev(ts, failed ? .activityFailed : .activityEnd, id: call)]
    }

    /// 老版 Codex 把结果写成一段 JSON 文本：`{"output": "...", "metadata": {"exit_code": 1}}`。
    /// 新版写成 `[{"type": "input_text", "text": ...}]`，成败只在 item_completed 里，这里看不出来。
    static func outputFailed(_ output: Any?) -> Bool {
        guard let text = output as? String, text.hasPrefix("{"),
              let data = text.data(using: .utf8),
              let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return false }
        if let metadata = obj["metadata"] as? [String: Any],
           let code = (metadata["exit_code"] as? NSNumber)?.intValue, code != 0 { return true }
        if let ok = obj["success"] as? Bool { return !ok }
        return false
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
