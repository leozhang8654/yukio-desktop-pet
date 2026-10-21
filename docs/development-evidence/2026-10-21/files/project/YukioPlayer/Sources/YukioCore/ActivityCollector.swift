import Foundation
import Darwin
import SQLite3

/// A serial, headless worker. Never run discovery or ingestion on the animation loop.
public final class ActivityCollector {
    private struct Entry {
        var revision = "", seen = "", pending = true, failures = 0, retryAt = 0.0
    }
    private let sourceFormat: ActivitySourceFormat
    private let store: ActivityHistory
    private let root: URL
    private let maxBytes: Int64
    private let maxFiles: Int, maxEntries: Int, filesPerPoll: Int, recordsPerFile: Int
    private let recentSeconds: TimeInterval
    private var entries: [String: Entry] = [:], queue: [String] = []
    private var paused: Bool
    private var total = 0
    private let startedAt = ActivityCollector.timestamp()
    public private(set) var last: [String: Any] = [:]

    public init(store: ActivityHistory, sessionsDirectory: URL, maxBytes: Int64 = 256 << 20,
                maxFiles: Int = 512, maxEntries: Int = 50000, filesPerPoll: Int = 8,
                recordsPerFile: Int = 500, recentSeconds: TimeInterval = 86400, sourceFormat: ActivitySourceFormat = .codex) throws {
        guard (1...512).contains(maxFiles), (1...50000).contains(maxEntries), (1...8).contains(filesPerPoll),
              (1...500).contains(recordsPerFile), recentSeconds > 0, recentSeconds.isFinite else {
            throw ActivityHistoryError("Invalid collector limits")
        }
        self.sourceFormat = sourceFormat
        self.store = store; root = sessionsDirectory.resolvingSymlinksInPath().standardizedFileURL
        self.maxBytes = maxBytes; self.maxFiles = maxFiles; self.maxEntries = maxEntries
        self.filesPerPoll = filesPerPoll; self.recordsPerFile = recordsPerFile; self.recentSeconds = recentSeconds
        paused = try !store.setMaximumSize(maxBytes)
        last = try status("starting", available: false, complete: true, discovered: 0, issue: nil)
    }
    public static func timestamp() -> String { ISO8601DateFormatter().string(from: Date()) }

    private func scan(now: Date) -> (found: [String: (TimeInterval, String)], available: Bool, complete: Bool) {
        var found: [String: (TimeInterval, String)] = [:], complete = true, count = 0
        guard let rootValues = try? root.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey]),
              rootValues.isDirectory == true, rootValues.isSymbolicLink != true else { return (found, false, false) }
        guard let walk = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil,
            errorHandler: { _, _ in complete = false; return true }) else { return (found, false, false) }
        for case let url as URL in walk {
            count += 1
            if count > maxEntries { complete = false; break }
            var info = stat()
            guard lstat(url.path, &info) == 0 else { complete = false; continue }
            let type = info.st_mode & S_IFMT
            if type == S_IFLNK { walk.skipDescendants(); continue }
            if type == S_IFDIR {
                if walk.level > 5 { walk.skipDescendants(); complete = false }
                continue
            }
            guard type == S_IFREG, url.pathExtension == "jsonl" else { continue }
            let revision = "\(info.st_dev):\(info.st_ino):\(info.st_size):\(info.st_mtimespec.tv_sec):\(info.st_mtimespec.tv_nsec):\(info.st_ctimespec.tv_sec):\(info.st_ctimespec.tv_nsec)"
            let modified = Double(info.st_mtimespec.tv_sec) + Double(info.st_mtimespec.tv_nsec) / 1e9
            let old = entries[url.path]
            if modified >= now.timeIntervalSince1970 - recentSeconds || old.map({ $0.pending || $0.failures > 0 || $0.seen != revision }) == true {
                found[url.path] = (modified, revision)
            }
        }
        return (found, true, complete)
    }

    public func poll(now: Date = Date(), monotonic: TimeInterval = ProcessInfo.processInfo.systemUptime) throws -> [String: Any] {
        let scan = scan(now: now)
        var complete = scan.complete
        if complete { for path in Array(entries.keys) where scan.found[path] == nil { entries.removeValue(forKey: path) } }
        let candidates = scan.found.keys.sorted {
            let a = scan.found[$0]!.0, b = scan.found[$1]!.0
            return a == b ? $0 < $1 : a > b
        }
        for path in candidates {
            if entries[path] == nil {
                if entries.count >= maxFiles { complete = false; continue }
                entries[path] = Entry(); queue.append(path)
            }
            var entry = entries[path]!
            let revision = scan.found[path]!.1
            if entry.revision != revision { entry.retryAt = 0 }
            entry.revision = revision; entries[path] = entry
        }
        queue.removeAll { entries[$0] == nil }
        if try store.databaseBytes() > maxBytes { paused = true }
        var attempted = 0, saved = 0
        if scan.available && !paused {
            for _ in 0..<queue.count {
                if attempted >= filesPerPoll { break }
                let path = queue.removeFirst(); queue.append(path)
                var entry = entries[path]!
                if scan.found[path] == nil || monotonic < entry.retryAt || (!entry.pending && entry.failures == 0 && entry.seen == entry.revision) { continue }
                attempted += 1
                do {
                    let result = try store.ingest(source: URL(fileURLWithPath: path), maxRecords: recordsPerFile, sourceRoot: root, sourceFormat: sourceFormat)
                    saved += result["events_saved"] as? Int ?? 0
                    entry.pending = result["batch_full"] as? Bool == true
                    entry.seen = entry.revision; entry.failures = 0; entry.retryAt = 0
                } catch {
                    if let code = (error as? ActivityHistoryError)?.sqliteCode {
                        if code == SQLITE_FULL { paused = true; break }
                        if code != SQLITE_BUSY && code != SQLITE_LOCKED { throw error }
                    }
                    entry.failures += 1
                    entry.retryAt = monotonic + min(60, pow(2, Double(min(entry.failures, 6))))
                }
                entries[path] = entry
            }
        }
        total += saved
        let errors = entries.values.contains { $0.failures > 0 }
        let pending = entries.values.contains { $0.pending || $0.failures > 0 || $0.seen != $0.revision }
        let issue: String? = paused ? "storage_full" : !scan.available ? "source_unavailable" : !complete ? "scan_incomplete" : errors ? "source_errors" : nil
        let state = paused ? "paused_capacity" : !scan.available ? "source_unavailable" : issue != nil ? "degraded" : saved > 0 || pending ? "active" : "waiting"
        last = try status(state, available: scan.available, complete: complete, discovered: scan.found.count, issue: issue)
        return last
    }
    private func status(_ state: String, available: Bool, complete: Bool, discovered: Int, issue: String?) throws -> [String: Any] {
        ["collector_schema": 1, "state": state, "updated_at": Self.timestamp(), "started_at": startedAt,
         "discovered_files": discovered, "tracked_files": entries.count,
         "pending_files": entries.values.filter { $0.pending || $0.failures > 0 || $0.seen != $0.revision }.count,
         "error_files": entries.values.filter { $0.failures > 0 }.count,
         "events_saved_this_run": total, "database_bytes": try store.databaseBytes(), "max_database_bytes": maxBytes,
         "scan_complete": complete, "last_scan_at": Self.timestamp(), "source_available": available,
         "issue": issue as Any? ?? NSNull(), "mode": "live", "backend": "swift", "source_format": sourceFormat.rawValue]
    }
    public func stopped() -> [String: Any] {
        last["state"] = "stopped"; last["updated_at"] = Self.timestamp(); return last
    }

    public static func validateStatusURL(_ url: URL, database: URL, sessionsDirectory: URL) throws {
        let path = url.resolvingSymlinksInPath().standardizedFileURL.path
        let root = sessionsDirectory.resolvingSymlinksInPath().standardizedFileURL.path
        let db = database.resolvingSymlinksInPath().standardizedFileURL.path
        let values = try? url.resourceValues(forKeys: [.isSymbolicLinkKey, .fileSizeKey])
        guard path != root, !path.hasPrefix(root == "/" ? root : root + "/"),
              ![db, db + "-journal", db + "-wal", db + "-shm", db + ".collector.lock"].contains(path), values?.isSymbolicLink != true else {
            throw ActivityHistoryError("Status must be separate from the source directory and database")
        }
        if FileManager.default.fileExists(atPath: url.path) {
            guard (values?.fileSize ?? 65537) <= 65536,
                  let data = try? Data(contentsOf: url), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  object["collector_schema"] as? Int == 1 else {
                throw ActivityHistoryError("Refusing to replace an unrelated status file")
            }
        }
    }
    public static func writeStatus(_ status: [String: Any], to url: URL) throws {
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let temp = url.deletingLastPathComponent().appendingPathComponent(".collector-\(UUID().uuidString)")
        let fd = Darwin.open(temp.path, O_CREAT | O_EXCL | O_WRONLY, 0o600)
        guard fd >= 0 else { throw ActivityHistoryError("Cannot create collector status") }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        defer { try? handle.close(); try? FileManager.default.removeItem(at: temp) }
        let data = try JSONSerialization.data(withJSONObject: status, options: [.sortedKeys])
        try handle.write(contentsOf: data); try handle.synchronize()
        guard rename(temp.path, url.path) == 0 else { throw ActivityHistoryError("Cannot publish collector status") }
    }
}
