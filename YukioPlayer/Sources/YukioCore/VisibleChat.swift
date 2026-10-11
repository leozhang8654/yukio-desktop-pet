import Foundation

/// A document currently displayed on screen, never a history link.
public struct VisibleChat: Equatable, Sendable {
    public let provider: AgentProvider
    public let id: String

    public init?(url text: String) {
        guard let url = URLComponents(string: text), url.user == nil, url.password == nil,
              url.port == nil else { return nil }
        let path = url.path.split(separator: "/").map(String.init)
        let host = url.host?.lowercased()
        var identity: String?
        if url.scheme == "https", host == "claude.ai" {
            provider = .claude
            if path.count == 2, path[0] == "chat" { identity = path[1] }
            if path.count == 3, path[0] == "cic", path[1] == "task" { identity = path[2] }
            if path.count == 2, ["code", "cowork"].contains(path[0]) { identity = path[1] }
        } else if url.scheme == "https", ["chatgpt.com", "chat.openai.com"].contains(host ?? "") {
            provider = .gpt
            if path.count == 2, path[0] == "c" { identity = path[1] }
            // Custom GPT / project conversations retain the /c/<id> suffix.
            if path.count == 4, path[0] == "g", path[2] == "c" { identity = path[3] }
            if path.count == 3, path[0] == "codex", path[1] == "tasks" { identity = path[2] }
        } else if url.scheme == "codex", host == "threads", path.count == 1 {
            provider = .gpt
            identity = path[0]
        } else if url.scheme == "claude", host == "code", path == ["continue"] {
            provider = .claude
            let ids = (url.queryItems ?? []).filter { $0.name == "session" }
            if ids.count == 1 { identity = ids[0].value }
        } else { return nil }
        guard let identity, Self.validID(identity) else { return nil }
        id = UUID(uuidString: identity)?.uuidString.lowercased() ?? identity
    }

    private static func validID(_ value: String) -> Bool {
        if UUID(uuidString: value) != nil { return true }
        // Claude local/remote sessions and cloud Codex tasks have explicit prefixes.
        guard ["local_", "session_", "cse_", "task_"].contains(where: value.hasPrefix),
              value.count >= 12, value.count <= 100 else { return false }
        return value.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "_" || $0 == "-") }
    }

    public func matches(session: String, provider: AgentProvider?, aliases: [String: String] = [:]) -> Bool {
        guard self.provider == provider else { return false }
        let normalized = UUID(uuidString: session)?.uuidString.lowercased() ?? session
        return id == normalized || aliases[id] == session
    }
}
