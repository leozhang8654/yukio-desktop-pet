import Foundation

/// 把转录里的会话 ID 对应到桌面版 Claude 里的那一条聊天，并给出打开它的深链。
///
/// 桌面版把每条 Claude Code 会话记在
/// `~/Library/Application Support/Claude/claude-code-sessions/<账号>/<组织>/local_<id>.json`，
/// 文件开头的 `cliSessionId` 就是 `~/.claude/projects/*/<会话>.jsonl` 的会话 ID：
///
/// ```
/// {"sessionId":"local_3987aafa-…","cliSessionId":"c0a80650-…","cwd":"/Users/…", …}
/// ```
///
/// 只读这些文件，不写入。这是桌面版的内部记录，不是公开接口，字段可能随版本变化；
/// 认不出会话时返回 nil，调用方退回到只把 Claude 带到前面。
public struct ClaudeSessionLinks: Sendable {
    public let sessionsDir: URL
    /// 每份记录只读开头这么多字节：要找的两个字段都在最前面，后面是几百 KB 的快照。
    public var headBytes = 64 << 10
    /// 最多翻这么多份记录（按最近修改排序，刚结束的那条通常是第一份）。
    public var maxFiles = 400

    public init(sessionsDir: URL = ClaudeSessionLinks.defaultSessionsDir()) {
        self.sessionsDir = sessionsDir
    }

    public static func defaultSessionsDir() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Claude/claude-code-sessions")
    }

    /// 转录会话 ID → 桌面版会话 ID（`local_…`）。找不到时 nil。
    public func desktopSessionID(forTranscriptSession session: String) -> String? {
        guard Self.isTranscriptSessionID(session) else { return nil }
        for url in records() {
            guard let head = Self.readHead(url, bytes: headBytes),
                  Self.value(of: "cliSessionId", in: head) == session else { continue }
            if let id = Self.value(of: "sessionId", in: head), Self.isDesktopSessionID(id) { return id }
            // 字段缺失时退回文件名：记录就是以会话 ID 命名的。
            let stem = url.deletingPathExtension().lastPathComponent
            return Self.isDesktopSessionID(stem) ? stem : nil
        }
        return nil
    }

    /// 点击举着的牌子时要打开的链接。认不出会话时 nil。
    public func chatURL(forTranscriptSession session: String) -> URL? {
        desktopSessionID(forTranscriptSession: session).flatMap(Self.chatURL(desktopSession:))
    }

    /// 桌面版 Claude 注册的深链：打开这条聊天，并把 Claude 带到前面。
    public static func chatURL(desktopSession id: String) -> URL? {
        guard isDesktopSessionID(id) else { return nil }
        return URL(string: "claude://code/continue?session=\(id)")
    }

    /// 全部会话记录，最近修改的在前。
    private func records() -> [URL] {
        let fm = FileManager.default
        let keys: [URLResourceKey] = [.isDirectoryKey, .contentModificationDateKey]
        guard let all = fm.enumerator(at: sessionsDir, includingPropertiesForKeys: keys,
                                      options: [.skipsHiddenFiles]) else { return [] }
        var found: [(URL, Date)] = []
        for case let url as URL in all {
            guard url.pathExtension == "json", url.lastPathComponent.hasPrefix("local_"),
                  let v = try? url.resourceValues(forKeys: Set(keys)), v.isDirectory != true else { continue }
            found.append((url, v.contentModificationDate ?? .distantPast))
        }
        return found.sorted { $0.1 > $1.1 }.prefix(maxFiles).map(\.0)
    }

    private static func readHead(_ url: URL, bytes: Int) -> Data? {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? handle.close() }
        return try? handle.read(upToCount: bytes)
    }

    /// 取出 JSON 顶层 `"键":"值"` 里的值。整份记录有几百 KB，只为两个字段解析全部内容不值得；
    /// 这两个键在记录里各只出现一次，就地找。
    static func value(of key: String, in data: Data) -> String? {
        let bytes = [UInt8](data)
        let needle = [UInt8]("\"\(key)\"".utf8)
        guard var i = firstRange(of: needle, in: bytes)?.upperBound else { return nil }
        func skipSpaces() { while i < bytes.count, bytes[i] == 0x20 || bytes[i] == 0x09 || bytes[i] == 0x0A || bytes[i] == 0x0D { i += 1 } }
        skipSpaces()
        guard i < bytes.count, bytes[i] == UInt8(ascii: ":") else { return nil }
        i += 1
        skipSpaces()
        guard i < bytes.count, bytes[i] == UInt8(ascii: "\"") else { return nil }
        i += 1
        var out: [UInt8] = []
        while i < bytes.count {
            let b = bytes[i]
            if b == UInt8(ascii: "\\") { return nil }   // 这两个字段是 ID，不含转义
            if b == UInt8(ascii: "\"") { return String(decoding: out, as: UTF8.self) }
            out.append(b)
            i += 1
        }
        return nil
    }

    private static func firstRange(of needle: [UInt8], in haystack: [UInt8]) -> Range<Int>? {
        guard !needle.isEmpty, haystack.count >= needle.count else { return nil }
        for start in 0...(haystack.count - needle.count) {
            var k = 0
            while k < needle.count && haystack[start + k] == needle[k] { k += 1 }
            if k == needle.count { return start..<(start + needle.count) }
        }
        return nil
    }

    /// 转录会话 ID：Claude Code 写的是 UUID。限定字符，免得把任意文本拼进查找与链接。
    static func isTranscriptSessionID(_ s: String) -> Bool {
        s.count >= 8 && s.count <= 64 && s.allSatisfy { $0.isASCII && ($0.isHexDigit || $0 == "-") }
    }

    /// 桌面版会话 ID：`local_` 加限定字符，与桌面版对深链的校验一致。
    static func isDesktopSessionID(_ s: String) -> Bool {
        guard s.hasPrefix("local_") else { return false }
        let rest = s.dropFirst("local_".count)
        return !rest.isEmpty && rest.count <= 64
            && rest.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-") }
    }
}
