import Foundation

/// 追踪单个文件新增的字节，切出完整 JSON 对象。
final class TailedFile {
    let url: URL
    private(set) var offset: UInt64
    private var stream = JSONObjectStream()
    private var skipPartialLine: Bool

    /// skipPartialLine：从文件中间（而非行首或文件末尾）开始读时为 true，丢弃到第一个换行为止。
    init(url: URL, offset: UInt64, skipPartialLine: Bool = false) {
        self.url = url
        self.offset = offset
        self.skipPartialLine = skipPartialLine
    }

    /// 文件已不存在时返回 nil。
    func readNew(maxBytes: Int = 8 << 20) -> [Data]? {
        guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
              let size = (attrs[.size] as? NSNumber)?.uint64Value else { return nil }
        if size < offset {
            // 文件被截断或重写：从头开始。
            offset = 0
            stream = JSONObjectStream()
            skipPartialLine = false
        }
        guard size > offset, let handle = try? FileHandle(forReadingFrom: url) else { return [] }
        defer { try? handle.close() }
        do {
            try handle.seek(toOffset: offset)
            guard var data = try handle.read(upToCount: maxBytes), !data.isEmpty else { return [] }
            offset += UInt64(data.count)
            if skipPartialLine {
                guard let nl = data.firstIndex(of: UInt8(ascii: "\n")) else { return [] }
                data = data.subdata(in: data.index(after: nl)..<data.endIndex)
                skipPartialLine = false
            }
            return stream.append(data)
        } catch {
            return []
        }
    }

    func resetTo(offset newOffset: UInt64) {
        offset = newOffset
        stream = JSONObjectStream()
        skipPartialLine = false
    }
}

/// 只读跟随 Claude Code 会话转录：~/.claude/projects/<项目>/<会话>.jsonl。
///
/// 启动时回放最近活动文件的末尾以恢复“正在做什么”，之后只读新增内容。
/// 不写入 Claude 的任何文件，不需要修改 Claude 设置。
public final class ClaudeTranscriptSource {
    public struct Status: Equatable, Sendable {
        public var directoryFound = false
        public var trackedFiles = 0
        public var lastEventAt: Double?
    }

    public let projectsDir: URL
    /// 启动时，这么久内修改过的会话会回放末尾以恢复状态。
    public var bootstrapWindowMs: Double = 15 * 60 * 1000
    /// 回放时最多读取的末尾字节数。
    public var bootstrapTailBytes: UInt64 = 1 << 20
    /// 超过这么久没修改的会话文件不追踪（被重新写入时会再次发现）。
    public var trackWindowMs: Double = 24 * 3600 * 1000
    public var rescanIntervalMs: Double = 2000

    public private(set) var status = Status()
    private var files: [String: TailedFile] = [:]
    private var started = false
    private var lastScan: Double = -.infinity
    private let parser = ClaudeTranscriptParser()

    public init(projectsDir: URL = ClaudeTranscriptSource.defaultProjectsDir()) {
        self.projectsDir = projectsDir
    }

    public static func defaultProjectsDir() -> URL {
        let env = ProcessInfo.processInfo.environment
        let base = env["CLAUDE_CONFIG_DIR"].map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".claude")
        return base.appendingPathComponent("projects")
    }

    /// 读取自上次调用以来的新事件。调用方用事件自身的时间戳 ingest。
    public func poll(now: Double) -> [PetEvent] {
        var out: [PetEvent] = []
        if now - lastScan >= rescanIntervalMs {
            lastScan = now
            scan(now: now, into: &out)
        }
        for (path, file) in files {
            guard let objects = file.readNew() else {
                files.removeValue(forKey: path)
                // 会话文件被删除：该会话不可能再有后续事件。
                let session = file.url.deletingPathExtension().lastPathComponent
                out.append(PetEvent(ts: now, source: ClaudeTranscriptParser.source, session: session, kind: .taskAbort))
                continue
            }
            for obj in objects { out += parser.events(fromLine: obj) }
        }
        status.trackedFiles = files.count
        if let last = out.last?.ts { status.lastEventAt = max(status.lastEventAt ?? 0, last) }
        return out
    }

    private func scan(now: Double, into out: inout [PetEvent]) {
        let fm = FileManager.default
        let keys: [URLResourceKey] = [.isDirectoryKey, .contentModificationDateKey, .fileSizeKey]
        guard let projects = try? fm.contentsOfDirectory(at: projectsDir, includingPropertiesForKeys: [.isDirectoryKey],
                                                         options: [.skipsHiddenFiles]) else {
            status.directoryFound = false
            return
        }
        status.directoryFound = true
        for dir in projects where (try? dir.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true {
            guard let entries = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: keys,
                                                            options: [.skipsHiddenFiles]) else { continue }
            for url in entries where url.pathExtension == "jsonl" && files[url.path] == nil {
                guard let v = try? url.resourceValues(forKeys: Set(keys)), v.isDirectory != true,
                      let mtime = v.contentModificationDate?.timeIntervalSince1970 else { continue }
                let age = now - mtime * 1000
                let size = UInt64(v.fileSize ?? 0)
                if age > trackWindowMs { continue }
                // 启动时只回放最近活跃的会话；运行中新发现的文件（新会话或恢复的旧会话）
                // 也只回放末尾，历史事件带旧时间戳，不会被当成实时活动。
                let recent = !started ? age <= bootstrapWindowMs : true
                let tail = recent ? (size > bootstrapTailBytes ? size - bootstrapTailBytes : 0) : size
                let file = TailedFile(url: url, offset: tail, skipPartialLine: recent && tail > 0)
                files[url.path] = file
                if recent, let objects = file.readNew() {
                    for obj in objects { out += parser.events(fromLine: obj) }
                }
            }
        }
        started = true
    }
}

/// 可选：Claude Code 官方 hooks 写入的收件箱文件（见 integrations/claude-hooks）。
/// 文件不存在时什么也不做。只读取启动之后新增的记录。
public final class HookInboxSource {
    public let url: URL
    public var rotateBytes: UInt64 = 5 << 20
    public private(set) var eventsReceived = 0
    private var tail: TailedFile?
    private let parser = ClaudeHookParser()

    public init(url: URL = HookInboxSource.defaultURL()) {
        self.url = url
    }

    public static func defaultURL() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/YukioPlayer/claude-hooks.jsonl")
    }

    public var isPresent: Bool { FileManager.default.fileExists(atPath: url.path) }

    public func poll(now: Double) -> [PetEvent] {
        if tail == nil {
            guard let attrs = try? FileManager.default.attributesOfItem(atPath: url.path),
                  let size = (attrs[.size] as? NSNumber)?.uint64Value else { return [] }
            tail = TailedFile(url: url, offset: size)
            return []
        }
        guard let file = tail, let objects = file.readNew() else {
            tail = nil
            return []
        }
        var out: [PetEvent] = []
        for data in objects {
            guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { continue }
            out += parser.events(from: obj, receivedAt: now)
        }
        eventsReceived += out.count
        // 收件箱只是管道：读完且过大时清空，避免无限增长。
        if file.offset > rotateBytes, let h = try? FileHandle(forWritingTo: url) {
            try? h.truncate(atOffset: 0)
            try? h.close()
            file.resetTo(offset: 0)
        }
        return out
    }
}
