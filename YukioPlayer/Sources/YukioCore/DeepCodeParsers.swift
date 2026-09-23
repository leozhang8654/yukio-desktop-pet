import Foundation

/// DeepSeek 的 Deep Code CLI 的本机会话记录 → 事件。
///
/// Deep Code 把每个项目的会话存在 `~/.deepcode/projects/<项目码>/` 下：
///
///     sessions-index.json   会话列表：标题（summary）、状态、更新时间
///     <会话 ID>.jsonl       消息记录，一行一条
///
/// 消息的字段（Deep Code 0.4 写入）：
///
///     {"id", "sessionId", "role": "user|assistant|tool|system", "content",
///      "messageParams": {"tool_calls": [...], "reasoning_content": "...", "tool_call_id": "..."},
///      "meta": {...}, "visible", "compacted", "createTime", "updateTime"}
///
/// 这是 Deep Code 在本地写的会话记录、不是公开 API，字段会随版本变化；解析失败只会少事件，
/// 不会崩溃，并按失联规则回空闲。只读取：角色、时间、工具名与参数（用于分类和简短说明）、
/// 工具是否报错、任务清单，不保存、不上传任何对话内容。
///
/// 这一份是 Windows 版 `yukio/parsers_deepcode.py` 的移植，两边规则保持一致。
public struct DeepCodeMessageParser: Sendable {
    public static let source = "deepcode"

    /// 中断时 Deep Code 追加的用户消息以这句开头。
    static let interruptPrefix = "Interrupted."

    public init() {}

    public func events(fromLine data: Data, fallbackSession: String = "", now: Double = 0) -> [PetEvent] {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return [] }
        return events(from: obj, fallbackSession: fallbackSession, now: now)
    }

    public func events(from obj: [String: Any], fallbackSession: String = "", now: Double = 0) -> [PetEvent] {
        let session = (obj["sessionId"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? fallbackSession
        guard !session.isEmpty else { return [] }
        // 被长会话压缩标记的历史消息：重写文件时会重新出现，不当成新活动。
        if obj["compacted"] as? Bool == true { return [] }

        let ts = PetEvent.parseTimestamp(obj["createTime"] as? String) ?? (obj["createTime"] as? Double) ?? now
        let meta = (obj["meta"] as? [String: Any]) ?? [:]
        let params = (obj["messageParams"] as? [String: Any]) ?? [:]
        let content = (obj["content"] as? String) ?? ""

        func ev(_ kind: PetEvent.Kind, id: String? = nil, activity: PetState? = nil, tool: String? = nil,
                detail: String? = nil, todos: [TodoItem]? = nil) -> PetEvent {
            PetEvent(ts: ts, source: Self.source, session: session, kind: kind, eventID: id, activity: activity,
                     tool: tool, detail: detail, todos: todos)
        }

        switch obj["role"] as? String {
        case "user":
            let stripped = content.trimmingCharacters(in: .whitespacesAndNewlines)
            if stripped.hasPrefix(Self.interruptPrefix) { return [ev(.taskAbort)] }
            // 回答 AskUserQuestion：同一轮任务继续，不是新任务。
            if meta["isAnswers"] as? Bool == true { return [ev(.thinking)] }
            if stripped.isEmpty { return [] }
            if stripped.hasPrefix("<") && stripped.hasSuffix(">") { return [] }
            return [ev(.taskStart, detail: ClaudeTranscriptParser.promptLine(content))]

        case "assistant":
            var out: [PetEvent] = []
            if let reasoning = params["reasoning_content"] as? String,
               !reasoning.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                out.append(ev(.thinking))
            }
            if let calls = params["tool_calls"] as? [[String: Any]], !calls.isEmpty {
                for call in calls {
                    let function = (call["function"] as? [String: Any]) ?? [:]
                    guard let name = function["name"] as? String, !name.isEmpty else { continue }
                    let args = CodexRolloutParser.dictionary(function["arguments"]) ?? [:]
                    let activity: PetState?
                    switch ClaudeToolClassifier.classify(tool: name, input: args) {
                    case .activity(let s): activity = s
                    case .continuePrevious: activity = nil
                    }
                    out.append(ev(.activityStart, id: call["id"] as? String, activity: activity, tool: name,
                                  detail: ClaudeToolClassifier.describe(tool: name, input: args)))
                    if name.lowercased() == "updateplan", let plan = args["plan"] as? String {
                        out.append(ev(.todoList, todos: DeepCodePlan.items(fromMarkdown: plan)))
                    }
                }
                // 调用工具前的过程说明不是最终回答。
                if !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { out.append(ev(.thinking)) }
                return out
            }
            if !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                out.append(ev(.finalAnswer))
                out.append(ev(.taskEnd))
            }
            return out

        case "tool":
            let callID = (params["tool_call_id"] as? String).flatMap { $0.isEmpty ? nil : $0 }
            let tool = ((meta["function"] as? [String: Any])?["name"]) as? String
            let failed = Self.outcome(content) == .failed
            return [ev(failed ? .activityFailed : .activityEnd, id: callID, tool: tool)]

        default:
            return []
        }
    }

    enum Outcome { case ok, failed, interrupted }

    /// 工具结果 → 成／败／被中断。
    ///
    /// Deep Code 把结果写成 JSON 文本：`{"ok": bool, "name": …, "output"/"error": …}`；
    /// 被用户中断时 `metadata.interrupted` 为真——中断和拒绝授权都不算失败，不让她沮丧。
    static func outcome(_ content: String) -> Outcome {
        let text = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard text.hasPrefix("{"), let data = text.data(using: .utf8),
              let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return .ok }
        if let metadata = obj["metadata"] as? [String: Any], metadata["interrupted"] as? Bool == true {
            return .interrupted
        }
        if let error = obj["error"] as? String {
            let lower = error.lowercased()
            if lower.contains("denied") || lower.contains("cancell") { return .interrupted }
        }
        return (obj["ok"] as? Bool ?? true) ? .ok : .failed
    }
}

/// `sessions-index.json` 的条目 → 标题与状态事件。
///
/// 索引比消息文件更早反映「正在等你批准」「已中断」「本轮失败」这些状态：
/// 消息文件里没有对应记录，只有索引会改。
public final class DeepCodeIndexParser {
    public static let source = DeepCodeMessageParser.source

    static let processing = "processing"
    static let failed = "failed"
    static let interrupted = "interrupted"
    static let askPermission = "ask_permission"
    static let waitingForUser = "waiting_for_user"
    static let permissionDenied = "permission_denied"

    private var status: [String: String] = [:]
    private var titles: [String: String] = [:]
    /// 为等待类状态开的合成工具调用 ID（等待结束时要关掉）。
    private var waiting: [String: String] = [:]

    public init() {}

    public func events(entry: [String: Any], now: Double) -> [PetEvent] {
        guard let session = entry["id"] as? String, !session.isEmpty else { return [] }
        let ts = PetEvent.parseTimestamp(entry["updateTime"] as? String) ?? (entry["updateTime"] as? Double) ?? now
        var out: [PetEvent] = []

        func ev(_ kind: PetEvent.Kind, id: String? = nil, activity: PetState? = nil, detail: String? = nil, at: Double = 0) -> PetEvent {
            PetEvent(ts: at == 0 ? ts : at, source: Self.source, session: session, kind: kind, eventID: id,
                     activity: activity, detail: detail)
        }

        if let summary = (entry["summary"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
           !summary.isEmpty, titles[session] != summary {
            titles[session] = summary
            // 标题不带时间：只更新大任务，不影响活动与失联判断。
            out.append(PetEvent(ts: 0, source: Self.source, session: session, kind: .sessionTitle,
                                detail: String(summary.prefix(80))))
        }

        guard let state = entry["status"] as? String else { return out }
        let previous = status[session]
        if state == previous { return out }
        status[session] = state

        if let id = waiting[session], state != Self.askPermission, state != Self.waitingForUser {
            waiting.removeValue(forKey: session)
            out.append(ev(.activityEnd, id: id))
        }

        switch state {
        case Self.askPermission, Self.waitingForUser:
            // 等你批准／等你回答：立问号卡。消息文件里这一刻没有任何记录。
            let id = "wait:\(session):\(Int(ts))"
            waiting[session] = id
            let detail = state == Self.askPermission ? tr("Needs your approval", "等你批准")
                                                     : tr("Needs your answer", "等你回答")
            out.append(ev(.activityStart, id: id, activity: .question_for_user, detail: detail))
        case Self.interrupted, Self.permissionDenied:
            // 中断、拒绝授权都不算失败。
            out.append(ev(.taskAbort))
        case Self.failed:
            out.append(ev(.taskFailed))
        case Self.processing where previous != nil:
            // 恢复运行：让「沮丧」「等你回答」尽快退场。
            out.append(ev(.thinking))
        default:
            break
        }
        return out
    }

    public func forget(session: String) {
        status.removeValue(forKey: session)
        titles.removeValue(forKey: session)
        waiting.removeValue(forKey: session)
    }
}

/// `UpdatePlan` 的 markdown 清单 → 任务条目。`[ ]` 未开始、`[>]` 进行中、`[x]` 已完成。
public enum DeepCodePlan {
    public static func items(fromMarkdown markdown: String) -> [TodoItem] {
        var items: [TodoItem] = []
        for raw in markdown.split(whereSeparator: \.isNewline) {
            var line = raw.trimmingCharacters(in: .whitespaces)
            // 去掉列表符号：- * + 或 1. / 1)
            if let first = line.first, "-*+".contains(first) {
                line = String(line.dropFirst()).trimmingCharacters(in: .whitespaces)
            } else if let dot = line.firstIndex(where: { $0 == "." || $0 == ")" }),
                      line[line.startIndex..<dot].allSatisfy(\.isNumber), dot > line.startIndex {
                line = String(line[line.index(after: dot)...]).trimmingCharacters(in: .whitespaces)
            }
            guard line.hasPrefix("["), line.count > 3 else { continue }
            let chars = Array(line)
            guard chars[2] == "]" else { continue }
            let mark = chars[1]
            let subject = String(chars[3...]).trimmingCharacters(in: .whitespaces)
            guard !subject.isEmpty else { continue }
            let status: TodoItem.Status
            switch mark {
            case "x", "X": status = .completed
            case ">": status = .inProgress
            case " ", "~", "!", "-": status = .pending
            default: continue
            }
            // 编号用序号：UpdatePlan 每次给出完整清单，整体替换。
            items.append(TodoItem(id: String(items.count), subject: subject, status: status))
        }
        return items
    }
}
