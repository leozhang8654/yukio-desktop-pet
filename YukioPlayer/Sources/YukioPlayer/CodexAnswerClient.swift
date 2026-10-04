import Foundation
import Darwin
import YukioCore

/// Same-user Codex desktop IPC. No UI activation, clipboard or synthesized keys.
final class CodexAnswerClient {
    enum Failure: LocalizedError, Equatable {
        case unavailable, protocolMismatch, expired, ambiguous, rejected(String)
        var errorDescription: String? {
            switch self {
            case .unavailable: return tr("Codex connection unavailable · retry", "Codex 未连接 · 可重试")
            case .protocolMismatch: return tr("Codex connection format changed", "Codex 接口格式已变化")
            case .expired: return tr("Question expired or already answered", "问题已结束或已回答")
            case .ambiguous: return tr("Answer this question in the chat", "此问题暂不支持后台回答")
            case .rejected: return tr("Not confirmed · check before retrying", "未确认接收 · 核对后重试")
            }
        }
    }
    private let socketPath: String
    init(socketPath: String? = nil) {
        let home = ProcessInfo.processInfo.environment["CODEX_HOME"]
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex").path
        self.socketPath = socketPath ?? home + "/ipc/ipc.sock"
    }

    /// New desktop snapshots keep ordered turns in canonical history and leave
    /// `turns` empty. Follow the history index, not unordered or detached entities.
    static func turns(in snapshot: [String: Any]) throws -> [[String: Any]] {
        if let historyState = snapshot["turnHistory"] as? [String: Any],
           historyState["kind"] as? String == "canonical" {
            guard let history = historyState["history"] as? [String: Any],
                  let entities = history["entitiesByKey"] as? [String: [String: Any]],
                  let islands = history["islands"] as? [[String: Any]] else { throw Failure.protocolMismatch }
            var result: [[String: Any]] = []
            var seen = Set<String>()
            for island in islands {
                guard let entries = island["entries"] as? [[String: Any]] else { throw Failure.protocolMismatch }
                for entry in entries {
                    guard let key = entry["value"] as? String,
                          let turn = entities[key] else { throw Failure.protocolMismatch }
                    if seen.insert(key).inserted { result.append(turn) }
                }
            }
            return result
        }
        guard let turns = snapshot["turns"] as? [[String: Any]] else { throw Failure.protocolMismatch }
        return turns
    }

    /// The mutation is constructed only from a freshly fetched question in this exact thread.
    static func submission(snapshot: [String: Any], session: String, callID: String,
                           question: PetQuestion, answer: String) throws -> (method: String, params: [String: Any]) {
        guard snapshot["id"] as? String == session else { throw Failure.protocolMismatch }
        let turns = try Self.turns(in: snapshot)
        guard let turn = turns.last(where: { $0["status"] as? String == "inProgress" }) else { throw Failure.expired }
        let items = turn["items"] as? [[String: Any]] ?? []
        if let item = items.first(where: { $0["id"] as? String == callID && $0["type"] as? String == "agentMessage" }),
           let questions = item["questions"] as? [[String: Any]], let first = questions.first,
           let title = first["title"] as? String,
           PetQuestion.from(input: ["title": title])?.text == question.text {
            let questionID = String(data: try JSONSerialization.data(withJSONObject: ["request_user_input_async", callID, 0], options: [.fragmentsAllowed]), encoding: .utf8)!
            for item in items where ["userMessage", "steeringUserMessage"].contains(item["type"] as? String ?? "") {
                if item["type"] as? String == "steeringUserMessage", item["status"] as? String != "accepted" { continue }
                let content = (item["content"] ?? item["input"]) as? [[String: Any]] ?? []
                for part in content {
                    if let text = part["text"] as? String,
                       let a = text.range(of: "<send_user_message_question_reply>"),
                       let b = text.range(of: "</send_user_message_question_reply>"), a.upperBound <= b.lowerBound,
                       let data = String(text[a.upperBound..<b.lowerBound]).data(using: .utf8),
                       let replies = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]],
                       replies.contains(where: { $0["questionItemId"] as? String == questionID }) { throw Failure.expired }
                }
            }
            let reply = [["questionItemId": questionID, "question": title, "answer": answer]]
            let json = String(data: try JSONSerialization.data(withJSONObject: reply, options: [.sortedKeys, .withoutEscapingSlashes]), encoding: .utf8)!
            let text = "<send_user_message_question_reply>\n\(json)\n</send_user_message_question_reply>"
            let id = UUID().uuidString
            return ("thread-follower-steer-turn", ["conversationId": session,
                "input": [["type": "text", "text": text, "text_elements": []]],
                "clientUserMessageId": id, "attachments": [],
                "restoreMessage": ["id": id, "cwd": snapshot["cwd"] ?? NSNull(),
                    "context": ["prompt": text, "addedFiles": [], "fileAttachments": [], "imageAttachments": [],
                                "commentAttachments": [], "turnTrigger": "send_user_message_async_question"]]])
        }
        // Blocking request_user_input is a server request, not a chat message.
        let requests = snapshot["requests"] as? [[String: Any]] ?? []
        let matching = requests.filter { request in
            guard request["method"] as? String == "item/tool/requestUserInput",
                  let params = request["params"] as? [String: Any],
                  params["itemId"] as? String == callID,
                  let questions = params["questions"] as? [[String: Any]], questions.count == 1,
                  PetQuestion.from(input: questions[0])?.text == question.text else { return false }
            return true
        }
        guard matching.count == 1, let request = matching.first, let id = request["id"],
              let params = request["params"] as? [String: Any],
              let questions = params["questions"] as? [[String: Any]],
              let questionID = questions.first?["id"] as? String else { throw Failure.expired }
        return ("thread-follower-submit-user-input", ["conversationId": session, "requestId": id,
            "response": ["answers": [questionID: ["answers": [answer]]]]])
    }

    func send(session: String, callID: String, question: PetQuestion, answer: String) throws {
        let connection = try Connection(path: socketPath)
        let ownerReply = try connection.request("thread-owner-discovery", params: ["hostId": "local", "conversationId": session])
        guard let owner = ownerReply["handledByClientId"] as? String else { throw Failure.unavailable }
        try connection.follow(session: session, owner: owner, following: true)
        defer { try? connection.follow(session: session, owner: owner, following: false) }
        let snapshot = try connection.snapshot(session: session, owner: owner)
        let submission = try Self.submission(snapshot: snapshot, session: session, callID: callID, question: question, answer: answer)
        let response = try connection.request(submission.method, params: submission.params, target: owner)
        guard let result = response["result"] as? [String: Any] else { throw Failure.protocolMismatch }
        if submission.method == "thread-follower-steer-turn" {
            // A successful steer includes the active turn ID, not merely an IPC ack.
            guard let accepted = result["result"] as? [String: Any], accepted["turnId"] is String else { throw Failure.protocolMismatch }
        } else {
            guard result["ok"] as? Bool == true else { throw Failure.protocolMismatch }
            // Server-request handlers can no-op for an expired request. Verify its completed item.
            _ = try connection.request("thread-follower-load-complete-history", params: ["conversationId": session], target: owner)
            let updated = try connection.snapshot(session: session, owner: owner)
            let turns = try Self.turns(in: updated)
            let confirmed = turns.flatMap { $0["items"] as? [[String: Any]] ?? [] }.contains {
                String(describing: $0["requestId"] ?? "") == String(describing: submission.params["requestId"] ?? "")
                    && $0["completed"] as? Bool == true
            }
            guard confirmed else { throw Failure.rejected("unconfirmed") }
        }
    }

    private final class Connection {
        private var fd: Int32 = -1
        private var client = "initializing-client"
        private var snapshots: [[String: Any]] = []
        private let deadline = Date().addingTimeInterval(12)
        init(path: String) throws {
            var info = stat()
            guard lstat(path, &info) == 0, info.st_uid == getuid(),
                  info.st_mode & S_IFMT == S_IFSOCK else { throw Failure.unavailable }
            var address = sockaddr_un()
            guard path.utf8.count < MemoryLayout.size(ofValue: address.sun_path) else { throw Failure.unavailable }
            fd = socket(AF_UNIX, SOCK_STREAM, 0)
            guard fd >= 0 else { throw Failure.unavailable }
            var noSignal: Int32 = 1
            setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &noSignal, socklen_t(MemoryLayout.size(ofValue: noSignal)))
            var timeout = timeval(tv_sec: 3, tv_usec: 0)
            setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue: timeout)))
            setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue: timeout)))
            address.sun_family = sa_family_t(AF_UNIX)
            address.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
            withUnsafeMutablePointer(to: &address.sun_path) { ptr in
                ptr.withMemoryRebound(to: CChar.self, capacity: 104) { _ = strcpy($0, path) }
            }
            let connected = withUnsafePointer(to: &address) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size)) }
            }
            guard connected == 0 else { Darwin.close(fd); fd = -1; throw Failure.unavailable }
            do {
                let response = try request("initialize", params: ["clientType": "yukio"], version: 0)
                guard let result = response["result"] as? [String: Any], let id = result["clientId"] as? String else { throw Failure.protocolMismatch }
                client = id
            } catch { Darwin.close(fd); fd = -1; throw error }
        }
        deinit { if fd >= 0 { Darwin.close(fd) } }
        func request(_ method: String, params: [String: Any], version: Int = 1, target: String? = nil) throws -> [String: Any] {
            let id = UUID().uuidString
            var message: [String: Any] = ["type": "request", "requestId": id, "sourceClientId": client,
                "version": version, "method": method, "params": params, "timeoutMs": 5000]
            if let target { message["targetClientId"] = target }
            try write(message)
            while Date() < deadline {
                let response = try receive()
                if response["requestId"] as? String == id, response["type"] as? String == "response" {
                    guard response["resultType"] as? String == "success" else { throw Failure.rejected(response["error"] as? String ?? "error") }
                    return response
                }
            }
            throw Failure.unavailable
        }
        func follow(session: String, owner: String, following: Bool) throws {
            try write(["type": "broadcast", "method": "thread-stream-following-changed", "sourceClientId": client,
                "targetClientIds": [owner], "version": 1,
                "params": ["conversationId": session, "hostId": "local", "following": following]])
        }
        func snapshot(session: String, owner: String) throws -> [String: Any] {
            while Date() < deadline {
                if let i = snapshots.firstIndex(where: { $0["conversationId"] as? String == session && $0["owner"] as? String == owner }) {
                    let params = snapshots.remove(at: i)
                    guard let change = params["change"] as? [String: Any], let state = change["conversationState"] as? [String: Any] else { throw Failure.protocolMismatch }
                    return state
                }
                _ = try receive()
            }
            throw Failure.unavailable
        }
        private func receive() throws -> [String: Any] {
            let header = try read(4)
            let length = header.enumerated().reduce(UInt32(0)) { $0 | UInt32($1.element) << (8 * $1.offset) }
            guard length > 0 && length <= 64 << 20,
                  let message = try JSONSerialization.jsonObject(with: read(Int(length))) as? [String: Any] else { throw Failure.protocolMismatch }
            if message["type"] as? String == "client-discovery-request", let id = message["requestId"] {
                try write(["type": "client-discovery-response", "requestId": id, "response": ["canHandle": false]])
            }
            if message["type"] as? String == "broadcast", message["method"] as? String == "thread-stream-state-changed",
               var params = message["params"] as? [String: Any], let change = params["change"] as? [String: Any],
               change["type"] as? String == "snapshot" {
                params["owner"] = message["sourceClientId"]
                snapshots.append(params)
            }
            return message
        }
        private func read(_ count: Int) throws -> Data {
            var data = Data(count: count), offset = 0
            while offset < count {
                guard Date() < deadline else { throw Failure.unavailable }
                let n = data.withUnsafeMutableBytes { Darwin.recv(fd, $0.baseAddress!.advanced(by: offset), count - offset, 0) }
                if n < 0 && errno == EINTR { continue }
                guard n > 0 else { throw Failure.unavailable }
                offset += n
            }
            return data
        }
        private func write(_ message: [String: Any]) throws {
            let body = try JSONSerialization.data(withJSONObject: message)
            var size = UInt32(body.count).littleEndian
            var data = withUnsafeBytes(of: &size) { Data($0) }; data.append(body)
            var offset = 0
            while offset < data.count {
                let n = data.withUnsafeBytes { Darwin.send(fd, $0.baseAddress!.advanced(by: offset), data.count - offset, 0) }
                if n < 0 && errno == EINTR { continue }
                guard n > 0 else { throw Failure.unavailable }
                offset += n
            }
        }
    }
}
