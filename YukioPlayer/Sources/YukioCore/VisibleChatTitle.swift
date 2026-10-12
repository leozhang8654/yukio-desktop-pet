import Foundation

/// Narrow fallback for the official ChatGPT side panel, which exposes its selected
/// title button but no conversation URL. Never match partial or duplicate titles.
public enum VisibleChatTitle {
    public static func session(header: String, candidates: [(id: String, title: String?)]) -> String? {
        var title = header.trimmingCharacters(in: .whitespacesAndNewlines)
        for suffix in [" No chats in progress", " 1 chat in progress"] {
            if title.hasSuffix(suffix) { title.removeLast(suffix.count) }
        }
        if let range = title.range(of: #" \d+ chats in progress$"#, options: .regularExpression) {
            title.removeSubrange(range)
        }
        guard title.count >= 2, !title.contains("…"), !title.hasSuffix("..."),
              !["New chat", "ChatGPT", "新聊天", "新对话"].contains(title) else { return nil }
        let matches = candidates.filter { $0.title?.trimmingCharacters(in: .whitespacesAndNewlines) == title }
        let ids = Set(matches.map(\.id))
        return ids.count == 1 ? ids.first : nil
    }
}
