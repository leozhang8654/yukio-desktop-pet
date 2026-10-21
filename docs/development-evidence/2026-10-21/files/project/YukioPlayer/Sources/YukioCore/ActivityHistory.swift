import Foundation
import CryptoKit
import CoreFoundation
import SQLite3
import Darwin

public struct ActivityHistoryError: Error, LocalizedError {
    public let message: String
    public let sqliteCode: Int32?
    public var errorDescription: String? { message }
    init(_ message: String, sqliteCode: Int32? = nil) { self.message = message; self.sqliteCode = sqliteCode }
}

/// Local metadata journal. Call from one serial worker, never the animation loop.
/// Evidence and complete-record cursor/checkpoint are one SQLite transaction.
public final class ActivityHistory {
    private static let applicationID = 1498762063
    private var db: OpaquePointer?
    private let path: String
    private let readonly: Bool
    public static let maxLine = 8 << 20
    public static let maxBatch = 500

    public init(url: URL, readonly: Bool = false) throws {
        path = url.standardizedFileURL.path
        self.readonly = readonly
        if !readonly {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true,
                                                    attributes: [.posixPermissions: 0o700])
            let fd = Darwin.open(path, O_CREAT | O_EXCL | O_WRONLY, 0o600)
            if fd >= 0 { Darwin.close(fd) }
            else if errno != EEXIST { throw ActivityHistoryError("Cannot create activity database") }
        }
        var connection: OpaquePointer?
        let flags = readonly ? SQLITE_OPEN_READONLY : SQLITE_OPEN_READWRITE
        guard sqlite3_open_v2(path, &connection, flags | SQLITE_OPEN_FULLMUTEX, nil) == SQLITE_OK,
              let connection else {
            if let connection { sqlite3_close(connection) }
            throw ActivityHistoryError("Cannot open activity database")
        }
        db = connection
        sqlite3_busy_timeout(db, 1000)
        do {
            if !readonly { try execute("PRAGMA synchronous=FULL"); try execute("BEGIN IMMEDIATE") }
            let version = try query("PRAGMA user_version")[0][0] ?? ""
            let app = try query("PRAGMA application_id")[0][0] ?? ""
            let tables = try query("SELECT name FROM sqlite_master WHERE type='table'")
            if !readonly && version == "0" && app == "0" && tables.isEmpty {
                try execute("CREATE TABLE sources (source_id TEXT PRIMARY KEY, state TEXT NOT NULL)")
                try execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, session_id TEXT, record TEXT NOT NULL)")
                try execute("CREATE INDEX events_session ON events(session_id, sequence)")
                try execute("PRAGMA application_id=\(Self.applicationID)")
                try execute("PRAGMA user_version=1")
            } else if version != "1" || app != String(Self.applicationID) {
                throw ActivityHistoryError("Not a supported Yukio activity database; existing data was not replaced")
            }
            if !readonly { try execute("COMMIT") }
        } catch {
            if !readonly { try? execute("ROLLBACK") }
            sqlite3_close(db)
            db = nil
            throw error
        }
    }

    deinit { sqlite3_close(db) }

    private func statement(_ sql: String, _ values: [String?]) throws -> OpaquePointer {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK, let stmt else {
            throw ActivityHistoryError("Activity database statement failed (\(sqlite3_errcode(db)))", sqliteCode: sqlite3_errcode(db))
        }
        for (i, value) in values.enumerated() {
            let code: Int32
            if let value {
                code = value.withCString { sqlite3_bind_text(stmt, Int32(i + 1), $0, -1, unsafeBitCast(-1, to: sqlite3_destructor_type.self)) }
            } else { code = sqlite3_bind_null(stmt, Int32(i + 1)) }
            guard code == SQLITE_OK else { sqlite3_finalize(stmt); throw ActivityHistoryError("Activity database binding failed") }
        }
        return stmt
    }

    private func execute(_ sql: String, _ values: [String?] = []) throws {
        let stmt = try statement(sql, values)
        defer { sqlite3_finalize(stmt) }
        let code = sqlite3_step(stmt)
        guard code == SQLITE_DONE || code == SQLITE_ROW else {
            throw ActivityHistoryError("Activity database write failed (\(code)); batch not acknowledged", sqliteCode: code)
        }
    }

    private func query(_ sql: String, _ values: [String?] = []) throws -> [[String?]] {
        let stmt = try statement(sql, values)
        defer { sqlite3_finalize(stmt) }
        var rows: [[String?]] = []
        while true {
            let code = sqlite3_step(stmt)
            if code == SQLITE_DONE { return rows }
            guard code == SQLITE_ROW else { throw ActivityHistoryError("Activity database read failed (\(code)/\(sqlite3_extended_errcode(db)))", sqliteCode: code) }
            rows.append((0..<sqlite3_column_count(stmt)).map { column in
                sqlite3_column_text(stmt, column).map { String(cString: $0) }
            })
        }
    }

    private static func json(_ value: Any) throws -> String {
        String(decoding: try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .withoutEscapingSlashes]), as: UTF8.self)
    }
    private static func object(_ value: String) throws -> [String: Any] {
        guard let obj = try JSONSerialization.jsonObject(with: Data(value.utf8)) as? [String: Any] else {
            throw ActivityHistoryError("Invalid activity database record")
        }
        return obj
    }
    private static func hex(_ digest: SHA256.Digest) -> String { digest.map { String(format: "%02x", $0) }.joined() }

    /// Connection-local growth cap. Existing history is never shrunk or removed.
    public func setMaximumSize(_ bytes: Int64) throws -> Bool {
        guard !readonly, bytes > 0 else { throw ActivityHistoryError("Invalid database size limit") }
        let page = Int64(try query("PRAGMA page_size")[0][0]!)!
        let actual = Int64(try query("PRAGMA max_page_count=\(max(1, bytes / page))")[0][0]!)!
        return actual * page <= bytes
    }
    public func databaseBytes() throws -> Int64 {
        Int64(try query("PRAGMA page_count")[0][0]!)! * Int64(try query("PRAGMA page_size")[0][0]!)!
    }

    public func rows(after: Int64 = 0, limit: Int = 500, session: String? = nil) throws -> [[String: Any]] {
        guard after >= 0, (1...10000).contains(limit) else { throw ActivityHistoryError("Invalid history page") }
        var sql = "SELECT sequence, record FROM events WHERE sequence > ?"
        var values: [String?] = [String(after)]
        if let session { sql += " AND session_id = ?"; values.append(session) }
        sql += " ORDER BY sequence LIMIT ?"; values.append(String(limit))
        return try query(sql, values).map { row in
            var obj = try Self.object(row[1] ?? "")
            obj["sequence"] = Int64(row[0] ?? "")
            return obj
        }
    }

    private func insert(_ row: [String: Any]) throws {
        try execute("INSERT INTO events(event_id, session_id, record) VALUES (?, ?, ?)",
                    [row["event_id"] as? String, row["session_id"] as? String, try Self.json(row)])
    }

    private struct Cursor: Codable {
        let generation: Int
        let file_identity: String
        let offset: UInt64
        let line: Int
        let prefix_sha256: String
        let checkpoint: String
        let source_format: String?
    }

    private static func canonicalPath(_ path: String) throws -> String {
        guard let resolved = realpath(path, nil) else { throw ActivityHistoryError("History source is unavailable") }
        defer { free(resolved) }
        return String(cString: resolved)
    }

    private static func openSource(_ url: URL) throws -> FileHandle {
        let fd = Darwin.open(url.path, O_RDONLY | O_NONBLOCK)
        guard fd >= 0 else { throw ActivityHistoryError("History source is unavailable") }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        do { _ = try fileInfo(handle); return handle }
        catch { try? handle.close(); throw error }
    }

    /// Cheap idle check for the standalone follower. Changed files still undergo
    /// full prefix validation; no stat-only cursor is ever committed.
    public static func sourceRevision(_ url: URL) throws -> String {
        let handle = try openSource(url)
        defer { try? handle.close() }
        let s = try fileInfo(handle)
        return "\(s.st_dev):\(s.st_ino):\(s.st_size):\(s.st_mtimespec.tv_sec):\(s.st_mtimespec.tv_nsec):\(s.st_ctimespec.tv_sec):\(s.st_ctimespec.tv_nsec)"
    }

    private static func fileInfo(_ handle: FileHandle) throws -> stat {
        var info = stat()
        guard fstat(handle.fileDescriptor, &info) == 0, info.st_mode & S_IFMT == S_IFREG else {
            throw ActivityHistoryError("History sources must be regular files")
        }
        return info
    }
    private static func hashPrefix(_ handle: FileHandle, _ size: UInt64) throws -> SHA256 {
        try handle.seek(toOffset: 0)
        var hash = SHA256(), left = size
        while left > 0 {
            guard let data = try handle.read(upToCount: Int(min(left, 1 << 20))), !data.isEmpty else {
                throw ActivityHistoryError("Source changed while reading; no batch was saved")
            }
            hash.update(data: data); left -= UInt64(data.count)
        }
        return hash
    }

    /// Imports at most 500 complete lines. Calls can resume after process exit.
    /// Changed/truncated/replaced sources get a new generation, retaining old rows.
    public func ingest(source: URL, maxRecords: Int = maxBatch, sourceRoot: URL? = nil, sourceFormat: ActivitySourceFormat = .codex) throws -> [String: Any] {
        guard !readonly, (1...Self.maxBatch).contains(maxRecords) else { throw ActivityHistoryError("Invalid history write request") }
        let url = URL(fileURLWithPath: try Self.canonicalPath(source.path))
        if let sourceRoot {
            let root = try Self.canonicalPath(sourceRoot.path)
            let values = try source.resourceValues(forKeys: [.isSymbolicLinkKey])
            guard values.isSymbolicLink != true, url.path.hasPrefix(root == "/" ? root : root + "/") else {
                throw ActivityHistoryError("Source is outside the selected session directory")
            }
        }
        let databasePath = try Self.canonicalPath(path)
        guard ![databasePath, databasePath + "-journal", databasePath + "-wal", databasePath + "-shm"].contains(url.path) else {
            throw ActivityHistoryError("The activity database cannot be its own source")
        }
        // Never open/close a second descriptor for the SQLite database: closing
        // it can release this process's POSIX locks, including SQLite's locks.
        var databaseInfo = stat(), sourceInfo = stat()
        guard lstat(databasePath, &databaseInfo) == 0, lstat(url.path, &sourceInfo) == 0,
              sourceInfo.st_mode & S_IFMT == S_IFREG else {
            throw ActivityHistoryError("History sources must be available regular files")
        }
        guard sourceInfo.st_dev != databaseInfo.st_dev || sourceInfo.st_ino != databaseInfo.st_ino else {
            throw ActivityHistoryError("The activity database cannot be its own source")
        }
        let handle = try Self.openSource(url)
        defer { try? handle.close() }
        let info = try Self.fileInfo(handle)
        guard info.st_dev != databaseInfo.st_dev || info.st_ino != databaseInfo.st_ino else {
            throw ActivityHistoryError("The activity database cannot be its own source")
        }
        let sourceID = Self.hex(SHA256.hash(data: Data(url.path.utf8)))
        try execute("BEGIN IMMEDIATE")
        do {
            let saved = try query("SELECT state FROM sources WHERE source_id=?", [sourceID])
            let old = try saved.first.flatMap { row -> Cursor? in
                guard let json = row[0] else { return nil }
                return try JSONDecoder().decode(Cursor.self, from: Data(json.utf8))
            }
            guard (old?.source_format ?? "codex") == sourceFormat.rawValue || old == nil else {
                throw ActivityHistoryError("Source format differs from saved history; no data was changed")
            }
            let identity = "\(info.st_dev):\(info.st_ino)"
            var offset = old?.offset ?? 0, line = old?.line ?? 0, generation = old?.generation ?? 1
            var reason: String?
            if let old {
                if old.file_identity != identity { reason = "file_replaced" }
                else if UInt64(info.st_size) < offset { reason = "file_truncated" }
                else if Self.hex(try Self.hashPrefix(handle, offset).finalize()) != old.prefix_sha256 { reason = "prefix_changed" }
            }
            if reason != nil { offset = 0; line = 0; generation += 1 }
            var parser: CodexRolloutParser
            if let old, reason == nil, sourceFormat == .codex { parser = try CodexRolloutParser.fromHistoryCheckpoint(old.checkpoint) }
            else { parser = CodexRolloutParser(session: "source-" + sourceID) }
            var claude: ClaudeHistoryParser?
            if sourceFormat == .claude {
                claude = try old.flatMap { reason == nil ? try ClaudeHistoryParser.restore($0.checkpoint) : nil }
                    ?? ClaudeHistoryParser(fallbackSession: "source-" + sourceID)
            }
            var digest = try Self.hashPrefix(handle, offset)
            var count = 0, inserted = 0
            if let reason {
                try insert(["event_id": "\(sourceID):\(generation):reset", "source_id": sourceID,
                            "generation": generation, "kind": "source_reset", "reason": reason, "evidence_class": "observed",
                            "schema_version": 1, "source": sourceFormat.rawValue, "timestamp_available": false])
                inserted += 1
            }
            let reader = HistoryLineReader(handle: handle)
            while count < maxRecords, let raw = try reader.next() {
                guard raw.last == 10 else { break }
                let data = Data(raw.dropLast()), nextOffset = offset + UInt64(raw.count)
                line += 1; count += 1; digest.update(data: raw)
                if !data.allSatisfy({ [UInt8(13), 32, 9].contains($0) }) {
                    let evidenceID = "\(sourceID):\(generation):\(offset)"
                    var row = try claude?.observe(data, evidenceID: evidenceID) ?? Self.observation(data, parser: &parser)
                    row.merge(["event_id": "\(sourceID):\(generation):\(offset)", "schema_version": 1,
                               "source": sourceFormat.rawValue, "source_id": sourceID, "generation": generation,
                               "source_line": line, "source_offset": offset, "next_offset": nextOffset,
                               "source_record_sha256": Self.hex(SHA256.hash(data: data))]) { _, new in new }
                    try insert(row); inserted += 1
                }
                offset = nextOffset
            }
            guard Self.hex(try Self.hashPrefix(handle, offset).finalize()) == Self.hex(digest.finalize()) else {
                throw ActivityHistoryError("Source changed while reading; no batch was saved")
            }
            let current = try Self.openSource(url)
            defer { try? current.close() }
            let currentInfo = try Self.fileInfo(current)
            guard currentInfo.st_dev == info.st_dev, currentInfo.st_ino == info.st_ino else {
                throw ActivityHistoryError("Source replaced while reading; no batch was saved")
            }
            let state = Cursor(generation: generation, file_identity: identity, offset: offset, line: line,
                               prefix_sha256: Self.hex(digest.finalize()), checkpoint: try claude?.checkpoint() ?? parser.historyCheckpoint(), source_format: sourceFormat.rawValue)
            let json = String(decoding: try JSONEncoder().encode(state), as: UTF8.self)
            try execute("INSERT INTO sources VALUES (?, ?) ON CONFLICT(source_id) DO UPDATE SET state=excluded.state", [sourceID, json])
            try execute("COMMIT")
            return ["records_read": count, "events_saved": inserted, "offset": offset, "generation": generation,
                    "batch_full": count == maxRecords]
        } catch {
            try? execute("ROLLBACK")
            throw error
        }
    }
}

private final class HistoryLineReader {
    let handle: FileHandle
    var pending = Data()
    init(handle: FileHandle) { self.handle = handle }
    func next() throws -> Data? {
        while true {
            if let end = pending.firstIndex(of: 10) {
                guard end - pending.startIndex <= ActivityHistory.maxLine else { throw oversized() }
                let line = Data(pending[...end]); pending.removeSubrange(...end)
                return line
            }
            guard pending.count <= ActivityHistory.maxLine else { throw oversized() }
            guard let chunk = try handle.read(upToCount: 65536), !chunk.isEmpty else {
                if pending.isEmpty { return nil }
                let line = pending; pending = Data(); return line
            }
            pending.append(chunk)
        }
    }
    private func oversized() -> Error { ActivityHistoryError("Source record exceeds 8 MiB; no batch was saved") }
}

private extension ActivityHistory {
    static func metadataRecord(_ obj: [String: Any]) -> [String: Any] {
        func fields(_ value: [String: Any], _ keys: [String]) -> [String: Any] {
            var result: [String: Any] = [:]
            for key in keys { if let s = value[key] as? String, s.unicodeScalars.count <= 1024 { result[key] = s } }
            return result
        }
        func outcomeFields(_ value: [String: Any]) -> [String: Any] {
            var out = fields(value, ["status"])
            for key in ["success", "isError"] {
                if let n = value[key] as? NSNumber, CFGetTypeID(n) == CFBooleanGetTypeID() { out[key] = n.boolValue }
            }
            if let code = CodexResultTracker.outcome(value).1 { out["exit_code"] = code }
            if let result = value["result"] as? [String: Any], let n = result["isError"] as? NSNumber,
               CFGetTypeID(n) == CFBooleanGetTypeID() { out["result"] = ["isError": n.boolValue] }
            return out
        }
        var out = fields(obj, ["type", "timestamp"])
        let payload = obj["payload"] as? [String: Any] ?? obj
        var p = fields(payload, ["type", "timestamp", "session_id", "thread_id", "id", "turn_id", "call_id", "name", "namespace", "role"])
        if payload["output"] != nil { p["output"] = outcomeFields(CodexRolloutParser.dictionary(payload["output"]) ?? [:]) }
        if let item = payload["item"] as? [String: Any] {
            p["item"] = fields(item, ["type", "id", "call_id"]).merging(outcomeFields(item)) { _, new in new }
        }
        out["payload"] = p
        return out
    }

    static func observation(_ data: Data, parser: inout CodexRolloutParser) throws -> [String: Any] {
        guard let raw = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            parser = CodexRolloutParser(session: parser.session)
            return ["kind": "invalid_record", "evidence_class": "observed", "timestamp_available": false, "session_id": parser.session]
        }
        let obj = metadataRecord(raw), p = obj["payload"] as! [String: Any]
        let sourceKind = p["type"] as? String ?? obj["type"] as? String ?? ""
        _ = parser.events(from: obj)
        let kinds = ["function_call": "tool_requested", "custom_tool_call": "tool_requested", "local_shell_call": "tool_requested",
                     "function_call_output": "tool_result", "custom_tool_call_output": "tool_result", "local_shell_call_output": "tool_result",
                     "task_started": "turn_started", "turn_context": "turn_context", "task_complete": "turn_ended",
                     "turn_aborted": "turn_cancelled", "error": "source_error", "stream_error": "source_error",
                     "session_meta": "session_observed", "message": "message_observed", "reasoning": "reasoning_record_observed",
                     "item_started": "item_started", "item_updated": "item_updated", "item_completed": "item_completed",
                     "web_search_call": "web_search_observed"]
        var row: [String: Any] = ["kind": kinds[sourceKind] ?? "unrecognized_record", "source_kind": sourceKind,
                                  "evidence_class": "observed", "session_id": parser.session, "timestamp_available": false]
        if let timestamp = PetEvent.parseTimestamp(obj["timestamp"] as? String) ?? PetEvent.parseTimestamp(p["timestamp"] as? String) {
            row["timestamp_ms"] = timestamp; row["timestamp_available"] = true
        }
        for key in ["thread_id", "turn_id", "call_id", "id", "name"] {
            if let value = p[key] { row[["thread_id": "reported_thread_id", "id": "reported_id", "name": "tool_name"][key] ?? key] = value }
        }
        if let turn = parser.historyTurnID { row["context_turn_id"] = turn }
        if let item = p["item"] as? [String: Any] {
            for key in ["id", "type"] { if let value = item[key] { row["item_" + key] = value } }
        }
        if let result = parser.lastToolResults.first {
            row["kind"] = "tool_result"
            row["result"] = try JSONSerialization.jsonObject(with: JSONEncoder().encode(result))
        }
        if let thread = p["thread_id"] as? String, !thread.isEmpty, thread != parser.session {
            row["kind"] = "foreign_session_record"; row["source_session_id"] = parser.session; row["session_id"] = thread
            row.removeValue(forKey: "context_turn_id")
        }
        return row
    }
}
