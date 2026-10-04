import Foundation
import Darwin
import YukioCore

/// Explicit AskUserQuestion hook. Answers stay local; only this tool's input is updated.
final class ClaudeQuestionBridge {
    struct Request: Codable {
        var provider: String? = nil
        let id: String
        let session: String
        let callID: String
        let questions: [PetQuestion]
        let pid: Int32
        let createdAt: Double
        let expiresAt: Double
    }
    enum Failure: LocalizedError {
        case notConnected, expired, unconfirmed
        var errorDescription: String? {
            switch self {
            case .notConnected: return tr("Claude bridge needed · ask again after setup", "Claude 需连接回答通道后重新提问")
            case .expired: return tr("Question expired or already answered", "问题已结束或已回答")
            case .unconfirmed: return tr("No receipt yet · retry to check", "暂未收到回执 · 可重试核对")
            }
        }
    }
    static var defaultRoot: URL {
        if let path = ProcessInfo.processInfo.environment["YUKIO_ANSWER_BRIDGE_DIR"] { return URL(fileURLWithPath: path) }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/YukioPlayer/answers")
    }
    let root: URL
    private var shown: [String: Request] = [:]
    private var heartbeatAt: Double = 0
    init(root: URL = defaultRoot) { self.root = root }
    private func prepare() throws {
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
    }
    private func request(at dir: URL, now: Double) -> Request? {
        guard let bytes = try? Data(contentsOf: dir.appendingPathComponent("request.json")), bytes.count < 1 << 20,
              let value = try? JSONDecoder().decode(Request.self, from: bytes), value.id == dir.lastPathComponent,
              value.expiresAt > now, kill(value.pid, 0) == 0,
              !FileManager.default.fileExists(atPath: dir.appendingPathComponent("done").path) else { return nil }
        return value
    }
    private func source(_ r: Request) -> String { r.provider == "deepseek" ? DeepCodeMessageParser.source : ClaudeTranscriptParser.source }
    private func key(_ r: Request, _ index: Int) -> String { "yukio-\(r.provider ?? "claude"):\(r.id):\(index)" }
    func poll(now: Double, enabled: Bool = true, providers: Set<String> = ["claude", "deepseek"]) -> [PetEvent] {
        try? prepare()
        if enabled && now - heartbeatAt > 1000 {
            for provider in providers.intersection(["claude", "deepseek"]) {
                try? Data(String(getpid()).utf8).write(to: root.appendingPathComponent(provider == "claude" ? "listener" : "listener-deepseek"), options: .atomic)
            }
            heartbeatAt = now
        }
        var next: [String: Request] = [:], events: [PetEvent] = []
        if enabled {
            let directories = (try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)) ?? []
            for dir in directories where UUID(uuidString: dir.lastPathComponent) != nil {
                guard let r = request(at: dir, now: now), providers.contains(r.provider ?? "claude"),
                      let index = r.questions.indices.first(where: { !FileManager.default.fileExists(atPath: dir.appendingPathComponent("receipt-\($0).json").path) }) else { continue }
                let id = key(r, index)
                next[id] = r
                if shown[id] == nil {
                    events.append(PetEvent(ts: now, source: source(r), session: r.session,
                        kind: .activityStart, eventID: id, activity: .question_for_user,
                        tool: "AskUserQuestion", detail: r.questions[index].shortLabel, question: r.questions[index]))
                }
            }
        }
        for (id, r) in shown where next[id] == nil {
            events.append(PetEvent(ts: now, source: source(r), session: r.session, kind: .activityEnd, eventID: id))
        }
        shown = next
        return events
    }
    func send(session: String, callID: String, answer: String, provider: String = "claude") throws {
        let parts = callID.split(separator: ":")
        guard parts.count == 3, parts[0] == "yukio-\(provider)", UUID(uuidString: String(parts[1])) != nil,
              let index = Int(parts[2]), index >= 0 else { throw Failure.notConnected }
        let dir = root.appendingPathComponent(String(parts[1]))
        guard !answer.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, answer.utf8.count < 65536,
              let requestData = try? Data(contentsOf: dir.appendingPathComponent("request.json")),
              let savedRequest = try? JSONDecoder().decode(Request.self, from: requestData),
              savedRequest.id == String(parts[1]), savedRequest.session == session,
              (savedRequest.provider ?? "claude") == provider, index < savedRequest.questions.count else { throw Failure.expired }
        let receipt = dir.appendingPathComponent("receipt-\(index).json")
        if let data = try? Data(contentsOf: receipt), let saved = try? JSONDecoder().decode(String.self, from: data) {
            guard saved == answer else { throw Failure.expired }
            return
        }
        guard let r = request(at: dir, now: Date().timeIntervalSince1970 * 1000), r.session == session, (r.provider ?? "claude") == provider,
              index < r.questions.count else { throw Failure.expired }
        let response = dir.appendingPathComponent("answer-\(index).json")
        if let data = try? Data(contentsOf: response), let saved = try? JSONDecoder().decode(String.self, from: data), saved != answer {
            throw Failure.unconfirmed // Do not overwrite an answer that may already be in flight.
        }
        try JSONEncoder().encode(answer).write(to: response, options: .atomic)
        let deadline = Date().addingTimeInterval(3)
        while Date() < deadline {
            if let data = try? Data(contentsOf: receipt), let saved = try? JSONDecoder().decode(String.self, from: data), saved == answer { return }
            Thread.sleep(forTimeInterval: 0.05)
        }
        throw Failure.unconfirmed
    }

    /// Called by Claude's PreToolUse hook before AskUserQuestion is executed.
    static func runHook(input: Data, root: URL = defaultRoot, waitSeconds: Double = 570) -> Data {
        let empty = Data("{}".utf8)
        guard let obj = try? JSONSerialization.jsonObject(with: input) as? [String: Any],
              obj["hook_event_name"] as? String == "PreToolUse", obj["tool_name"] as? String == "AskUserQuestion",
              let session = obj["session_id"] as? String, let callID = obj["tool_use_id"] as? String,
              let toolInput = obj["tool_input"] as? [String: Any],
              let raw = toolInput["questions"] as? [[String: Any]], !raw.isEmpty,
              let attributes = try? FileManager.default.attributesOfItem(atPath: root.appendingPathComponent("listener").path),
              let modified = attributes[.modificationDate] as? Date, Date().timeIntervalSince(modified) < 4,
              let listenerText = try? String(contentsOf: root.appendingPathComponent("listener")),
              let listenerPID = Int32(listenerText), kill(listenerPID, 0) == 0 else { return empty }
        let questions = raw.compactMap { PetQuestion.from(input: $0) }
        guard questions.count == raw.count, Set(raw.compactMap { $0["question"] as? String }).count == raw.count else { return empty }
        let now = Date().timeIntervalSince1970 * 1000
        let r = Request(id: UUID().uuidString, session: session, callID: callID, questions: questions,
                        pid: getpid(), createdAt: now, expiresAt: now + waitSeconds * 1000)
        let dir = root.appendingPathComponent(r.id)
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            try JSONEncoder().encode(r).write(to: dir.appendingPathComponent("request.json"), options: .atomic)
            defer { try? Data().write(to: dir.appendingPathComponent("done"), options: .atomic) }
            var answers: [String: String] = [:]
            let deadline = Date().addingTimeInterval(waitSeconds)
            while Date() < deadline {
                guard let attrs = try? FileManager.default.attributesOfItem(atPath: root.appendingPathComponent("listener").path),
                      let alive = attrs[.modificationDate] as? Date, Date().timeIntervalSince(alive) < 5,
                      kill(listenerPID, 0) == 0 else { return empty }
                for index in raw.indices where answers[raw[index]["question"] as? String ?? ""] == nil {
                    guard let text = raw[index]["question"] as? String,
                          let data = try? Data(contentsOf: dir.appendingPathComponent("answer-\(index).json")), data.count < 65536,
                          let answer = try? JSONDecoder().decode(String.self, from: data), !answer.isEmpty else { continue }
                    answers[text] = answer
                    try data.write(to: dir.appendingPathComponent("receipt-\(index).json"), options: .atomic)
                }
                if answers.count == raw.count {
                    var updated = toolInput
                    updated["answers"] = answers
                    return try JSONSerialization.data(withJSONObject: ["hookSpecificOutput": ["hookEventName": "PreToolUse",
                        "permissionDecision": "allow", "updatedInput": updated]])
                }
                Thread.sleep(forTimeInterval: 0.1)
            }
            return empty
        } catch { return empty }
    }
}
