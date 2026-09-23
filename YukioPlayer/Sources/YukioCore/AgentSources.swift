import Foundation

/// 一行 JSON → 事件。三家的解析器都能这样用（Claude 的在 LiveSources 里自己接）。
public protocol LineParsing: AnyObject {
    func events(fromLine data: Data, now: Double) -> [PetEvent]
}

/// `events(fromLine:now:)` 本身就是协议要的样子。
extension CodexRolloutParser: LineParsing {}

/// Deep Code 的消息解析器是无状态的 struct，这里补上「这个文件属于哪条会话」。
public final class DeepCodeFileParser: LineParsing {
    private let parser = DeepCodeMessageParser()
    private let session: String

    public init(session: String) { self.session = session }

    public func events(fromLine data: Data, now: Double) -> [PetEvent] {
        parser.events(fromLine: data, fallbackSession: session, now: now)
    }
}

/// 只读跟随一棵目录下的 `.jsonl`：新文件只读末尾，之后只读新增内容。
///
/// Claude、Deep Code 的记录是 `<projects>/<项目>/<会话>.jsonl`（两层），
/// Codex 是 `<sessions>/<年>/<月>/<日>/rollout-….jsonl`（四层），只有深度和文件名过滤不同。
public final class JSONLTreeSource {
    public struct Status: Equatable, Sendable {
        public var directoryFound = false
        public var trackedFiles = 0
        public var lastEventAt: Double?
    }

    public let root: URL
    /// 从 root 往下最多找几层目录（1 = 只看 root 里的文件）。
    public let maxDepth: Int
    /// 启动时，这么久内修改过的会话会回放末尾以恢复状态。
    public var bootstrapWindowMs: Double = 15 * 60 * 1000
    /// 回放时最多读取的末尾字节数。
    public var bootstrapTailBytes: UInt64 = 1 << 20
    /// 超过这么久没修改的会话文件不追踪（被重新写入时会再次发现）。
    public var trackWindowMs: Double = 24 * 3600 * 1000
    public var rescanIntervalMs: Double = 2000

    public private(set) var status = Status()
    /// 找到过 .jsonl 的那些目录（Deep Code 的会话索引就摆在这些目录里）。
    public private(set) var folders: [URL] = []

    private let matches: (String) -> Bool
    private let makeParser: (URL) -> LineParsing
    private let onGone: (String) -> PetEvent?
    private var files: [String: (parser: LineParsing, tail: TailedFile)] = [:]
    private var started = false
    private var lastScan: Double = -.infinity

    public init(root: URL, maxDepth: Int, matches: @escaping (String) -> Bool,
                makeParser: @escaping (URL) -> LineParsing,
                onGone: @escaping (String) -> PetEvent? = { _ in nil }) {
        self.root = root
        self.maxDepth = maxDepth
        self.matches = matches
        self.makeParser = makeParser
        self.onGone = onGone
    }

    public func poll(now: Double) -> [PetEvent] {
        var out: [PetEvent] = []
        if now - lastScan >= rescanIntervalMs {
            lastScan = now
            scan(now: now, into: &out)
        }
        for (path, entry) in files {
            guard let objects = entry.tail.readNew() else {
                files.removeValue(forKey: path)
                // 会话文件被删除：该会话不可能再有后续事件。
                if let e = onGone(Self.sessionName(path)) { out.append(e) }
                continue
            }
            for obj in objects { out += entry.parser.events(fromLine: obj, now: now) }
        }
        status.trackedFiles = files.count
        if let last = out.last?.ts { status.lastEventAt = max(status.lastEventAt ?? 0, last) }
        return out
    }

    public static func sessionName(_ path: String) -> String {
        (path as NSString).lastPathComponent.replacingOccurrences(of: ".jsonl", with: "")
    }

    private func scan(now: Double, into out: inout [PetEvent]) {
        let fm = FileManager.default
        guard (try? fm.contentsOfDirectory(atPath: root.path)) != nil else {
            status.directoryFound = false
            return
        }
        status.directoryFound = true
        walk(root, depth: 1, now: now, into: &out)
        started = true
    }

    private func walk(_ dir: URL, depth: Int, now: Double, into out: inout [PetEvent]) {
        let fm = FileManager.default
        let keys: [URLResourceKey] = [.isDirectoryKey, .contentModificationDateKey, .fileSizeKey]
        guard let entries = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: keys,
                                                        options: [.skipsHiddenFiles]) else { return }
        for url in entries {
            guard let v = try? url.resourceValues(forKeys: Set(keys)) else { continue }
            if v.isDirectory == true {
                if depth < maxDepth { walk(url, depth: depth + 1, now: now, into: &out) }
                continue
            }
            guard url.pathExtension == "jsonl", matches(url.lastPathComponent) else { continue }
            if !folders.contains(dir) { folders.append(dir) }
            guard files[url.path] == nil, let mtime = v.contentModificationDate?.timeIntervalSince1970 else { continue }
            let age = now - mtime * 1000
            if age > trackWindowMs { continue }
            // 启动时只回放最近活跃的会话；运行中新发现的文件也只回放末尾，
            // 历史事件带旧时间戳，不会被当成实时活动。
            let size = UInt64(v.fileSize ?? 0)
            let recent = !started ? age <= bootstrapWindowMs : true
            let tail = recent ? (size > bootstrapTailBytes ? size - bootstrapTailBytes : 0) : size
            let file = TailedFile(url: url, offset: tail, skipPartialLine: recent && tail > 0)
            let parser = makeParser(url)
            files[url.path] = (parser, file)
            if recent, let objects = file.readNew() {
                for obj in objects { out += parser.events(fromLine: obj, now: now) }
            }
        }
    }
}

/// GPT（Codex）：只读跟随 `~/.codex/sessions/<年>/<月>/<日>/rollout-<时间>-<会话 ID>.jsonl`。
public final class CodexSessionsSource {
    public let sessionsDir: URL
    private let tree: JSONLTreeSource

    public init(sessionsDir: URL = CodexSessionsSource.defaultSessionsDir()) {
        self.sessionsDir = sessionsDir
        tree = JSONLTreeSource(
            root: sessionsDir,
            // sessions/<年>/<月>/<日>/<文件>：多留一层，以后换目录结构也还能找到。
            maxDepth: 5,
            // 平时都是 rollout-….jsonl；将来改名了也照跟，反正这棵目录里只有会话记录。
            matches: { _ in true },
            makeParser: { url in CodexRolloutParser(session: Self.sessionID(fromFileName: url.lastPathComponent)) },
            onGone: { name in
                PetEvent(ts: 0, source: CodexRolloutParser.source,
                         session: Self.sessionID(fromFileName: name), kind: .taskAbort)
            })
    }

    public static func defaultSessionsDir() -> URL {
        let env = ProcessInfo.processInfo.environment
        let base = env["CODEX_HOME"].map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex")
        return base.appendingPathComponent("sessions")
    }

    /// `rollout-2026-09-22T19-10-20-<会话 ID>[_<分支 ID>].jsonl` → 会话 ID。
    /// 记录里的 session_meta 一到就以它为准，这里只是先有个名字。
    public static func sessionID(fromFileName name: String) -> String {
        let base = ((name as NSString).lastPathComponent as NSString).deletingPathExtension
        let last = base.components(separatedBy: "_").last ?? base
        let tail = String(last.suffix(36))
        let parts = tail.components(separatedBy: "-")
        let uuidShape = parts.count == 5 && parts.map(\.count) == [8, 4, 4, 4, 12]
        return uuidShape ? tail : base
    }

    public var status: JSONLTreeSource.Status { tree.status }

    public func poll(now: Double) -> [PetEvent] {
        var out = tree.poll(now: now)
        // 文件被删时用当前时间报中断（记录里没有时间可用）。
        for i in out.indices where out[i].ts == 0 && out[i].kind == .taskAbort { out[i].ts = now }
        return out
    }
}

/// DeepSeek 的 Deep Code CLI：`~/.deepcode/projects/<项目码>/` 下的消息文件与会话索引。
///
/// 除了消息文件，还读每个项目的 `sessions-index.json`：标题、以及「等你批准 / 已中断 /
/// 本轮失败」这些只写在索引里的状态。
public final class DeepCodeSource {
    public let projectsDir: URL
    private let tree: JSONLTreeSource
    private let index: DeepCodeIndexParser
    private var indexMTime: [String: Double] = [:]

    public init(projectsDir: URL = DeepCodeSource.defaultProjectsDir()) {
        self.projectsDir = projectsDir
        let index = DeepCodeIndexParser()
        self.index = index
        tree = JSONLTreeSource(
            root: projectsDir,
            maxDepth: 2,
            matches: { _ in true },
            makeParser: { url in
                DeepCodeFileParser(session: url.deletingPathExtension().lastPathComponent)
            },
            onGone: { [index] name in
                index.forget(session: name)
                return PetEvent(ts: 0, source: DeepCodeMessageParser.source, session: name, kind: .taskAbort)
            })
    }

    public static func defaultProjectsDir() -> URL {
        let env = ProcessInfo.processInfo.environment
        let base = env["DEEPCODE_CONFIG_DIR"].map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".deepcode")
        return base.appendingPathComponent("projects")
    }

    public var status: JSONLTreeSource.Status { tree.status }

    public func poll(now: Double) -> [PetEvent] {
        var out = tree.poll(now: now)
        for i in out.indices where out[i].ts == 0 && out[i].kind == .taskAbort { out[i].ts = now }
        // 每次都看一眼各项目的索引（一次 stat，很便宜）：「等你批准」只写在索引里，
        // 要是等到两秒一次的重新扫描才发现，问号卡就慢半拍。
        for folder in tree.folders { out += pollIndex(folder, now: now) }
        return out
    }

    private func pollIndex(_ folder: URL, now: Double) -> [PetEvent] {
        let path = folder.appendingPathComponent("sessions-index.json")
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: path.path),
              let mtime = (attrs[.modificationDate] as? Date)?.timeIntervalSince1970 else { return [] }
        if indexMTime[path.path] == mtime { return [] }
        let firstLook = indexMTime[path.path] == nil
        indexMTime[path.path] = mtime
        guard let data = FileManager.default.contents(atPath: path.path),
              let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let entries = obj["entries"] as? [[String: Any]] else { return [] }
        var out: [PetEvent] = []
        for entry in entries {
            let events = index.events(entry: entry, now: now)
            // 首次读取只记住当前状态与标题，不把历史状态当成刚发生的事，但标题要留下（气泡的大任务）。
            out += firstLook ? events.filter { $0.kind == .sessionTitle } : events
        }
        return out
    }
}

/// 按设置挑来源，并把三家的事件汇到一起。
///
/// 切换时把旧来源整个丢掉：跟着的聊天、举着的牌子都属于那一家，换人就从新的记录重新回放。
public final class AgentSources {
    public struct FeedStatus: Equatable, Sendable {
        public let provider: AgentProvider
        public let label: String
        public let path: String
        public let found: Bool
        public let trackedFiles: Int
    }

    public private(set) var provider: AgentProvider
    private var claude: ClaudeTranscriptSource?
    private var deepcode: DeepCodeSource?
    private var codex: CodexSessionsSource?
    /// Claude 官方 hooks 的收件箱（只有跟 Claude 时才挂着）。
    public private(set) var hooks: HookInboxSource?

    public init(provider: AgentProvider = .auto) {
        self.provider = provider
        build()
    }

    private func build() {
        let ids = provider.sourceIDs
        claude = ids.contains(ClaudeTranscriptParser.source) ? ClaudeTranscriptSource() : nil
        hooks = ids.contains(ClaudeHookParser.source) ? HookInboxSource() : nil
        deepcode = ids.contains(DeepCodeMessageParser.source) ? DeepCodeSource() : nil
        codex = ids.contains(CodexRolloutParser.source) ? CodexSessionsSource() : nil
    }

    /// 换一家跟。调用方随后要 `router.reset(now:)` 再 `poll`：新的一家从它自己的记录重新回放。
    public func switchTo(_ provider: AgentProvider) {
        guard provider != self.provider else { return }
        self.provider = provider
        build()
    }

    public func poll(now: Double) -> [PetEvent] {
        var out: [PetEvent] = []
        if let claude { out += claude.poll(now: now) }
        if let hooks { out += hooks.poll(now: now) }
        if let deepcode { out += deepcode.poll(now: now) }
        if let codex { out += codex.poll(now: now) }
        return out
    }

    /// 菜单里那几行：跟着谁、记录目录在不在。
    public var statuses: [FeedStatus] {
        var out: [FeedStatus] = []
        if let claude {
            out.append(.init(provider: .claude, label: AgentProvider.claude.displayName,
                             path: claude.projectsDir.path, found: claude.status.directoryFound,
                             trackedFiles: claude.status.trackedFiles))
        }
        if let deepcode {
            out.append(.init(provider: .deepseek, label: AgentProvider.deepseek.displayName,
                             path: deepcode.projectsDir.path, found: deepcode.status.directoryFound,
                             trackedFiles: deepcode.status.trackedFiles))
        }
        if let codex {
            out.append(.init(provider: .gpt, label: AgentProvider.gpt.displayName,
                             path: codex.sessionsDir.path, found: codex.status.directoryFound,
                             trackedFiles: codex.status.trackedFiles))
        }
        return out
    }

    /// 一家的记录目录都没找到：菜单里要提示「没装／没跑过」。
    public var anyFound: Bool { statuses.contains { $0.found } }
}
