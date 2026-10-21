import Foundation
import SQLite3
import Darwin
import Testing
@testable import YukioCore

@Suite struct ActivityHistoryTests {
    func withFiles(_ body: (URL, URL) throws -> Void) throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("yukio-history-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        try body(dir.appendingPathComponent("history.db"), dir.appendingPathComponent("synthetic.jsonl"))
    }
    func append(_ text: String, to source: URL) throws {
        let handle = try FileHandle(forWritingTo: source)
        defer { try? handle.close() }
        try handle.seekToEnd(); try handle.write(contentsOf: Data(text.utf8))
    }
    func sql(_ path: URL, _ statement: String) throws {
        var db: OpaquePointer?
        #expect(sqlite3_open(path.path, &db) == SQLITE_OK)
        defer { sqlite3_close(db) }
        #expect(sqlite3_exec(db, statement, nil, nil, nil) == SQLITE_OK)
    }
    let start = "{\"type\":\"session_meta\",\"id\":\"s\"}\n{\"type\":\"task_started\",\"turn_id\":\"t\"}\n{\"type\":\"function_call\",\"name\":\"shell\",\"call_id\":\"a\"}\n"

    @Test func restartKeepsCallAndConflictEvidence() throws {
        try withFiles { db, source in
            try Data(start.utf8).write(to: source)
            _ = try ActivityHistory(url: db).ingest(source: source)
            try append("{\"type\":\"item_completed\",\"item\":{\"type\":\"CommandExecution\",\"id\":\"a\",\"exit_code\":1}}\n", to: source)
            _ = try ActivityHistory(url: db).ingest(source: source)
            let first = try ActivityHistory(url: db, readonly: true).rows().last!["result"] as! [String: Any]
            #expect(first["association"] as? String == "matching_item_id")
            try append("{\"type\":\"function_call_output\",\"call_id\":\"a\",\"output\":{\"success\":true}}\n", to: source)
            _ = try ActivityHistory(url: db).ingest(source: source)
            let result = try ActivityHistory(url: db, readonly: true).rows().last!["result"] as! [String: Any]
            #expect(result["turn_id"] as? String == "t")
            #expect(result["conflicting_results"] as? Bool == true)
            #expect(result["call_outcome"] as? String == "unknown")
        }
    }

    @Test func partialLineAndRepeatedReadAfterRestart() throws {
        try withFiles { db, source in
            try Data((start + "{\"type\":\"function_call_output\",\"call_id\":\"a\",\"output\":{\"success\":true}}").utf8).write(to: source)
            let first = try ActivityHistory(url: db).ingest(source: source)
            #expect(first["offset"] as? UInt64 == UInt64(start.utf8.count))
            #expect(try ActivityHistory(url: db).ingest(source: source)["events_saved"] as? Int == 0)
            try append("\n", to: source)
            #expect(try ActivityHistory(url: db).ingest(source: source)["events_saved"] as? Int == 1)
            #expect(try ActivityHistory(url: db, readonly: true).rows().count == 4)
        }
    }

    @Test func rewriteReplacementAndTruncationPreserveHistory() throws {
        try withFiles { db, source in
            try Data(start.utf8).write(to: source)
            _ = try ActivityHistory(url: db).ingest(source: source)
            try Data(start.replacingOccurrences(of: "\"a\"", with: "\"b\"").utf8).write(to: source)
            #expect(try ActivityHistory(url: db).ingest(source: source)["generation"] as? Int == 2)
            #expect(try ActivityHistory(url: db, readonly: true).rows()[3]["reason"] as? String == "prefix_changed")
            try Data(start.utf8).write(to: source, options: .atomic)
            #expect(try ActivityHistory(url: db).ingest(source: source)["generation"] as? Int == 3)
            #expect(try ActivityHistory(url: db, readonly: true).rows()[7]["reason"] as? String == "file_replaced")
            try Data([10]).write(to: source)
            #expect(try ActivityHistory(url: db).ingest(source: source)["generation"] as? Int == 4)
            #expect(try ActivityHistory(url: db, readonly: true).rows().last?["reason"] as? String == "file_truncated")
        }
    }

    @Test func rollbackCursorFailureAndRetry() throws {
        try withFiles { db, source in
            try Data(start.utf8).write(to: source)
            let store = try ActivityHistory(url: db)
            try sql(db, "CREATE TRIGGER fail_cursor BEFORE INSERT ON sources BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END")
            #expect(throws: (any Error).self) { try store.ingest(source: source) }
            #expect(try store.rows().isEmpty)
            try sql(db, "DROP TRIGGER fail_cursor")
            #expect(try store.ingest(source: source)["events_saved"] as? Int == 3)
            #expect(try store.ingest(source: source)["events_saved"] as? Int == 0)
        }
    }

    @Test func privacyAndMissingTimestamp() throws {
        try withFiles { db, source in
            let secret = "PRIVATE_BODY_012345"
            let text = "{\"type\":\"message\",\"role\":\"user\",\"content\":\"\(secret)\"}\n{\"type\":\"function_call_output\",\"call_id\":\"a\",\"output\":{\"success\":true,\"text\":\"\(secret)\"}}\n"
            try Data(text.utf8).write(to: source)
            _ = try ActivityHistory(url: db).ingest(source: source)
            #expect(try Data(contentsOf: db).range(of: Data(secret.utf8)) == nil)
            let rows = try ActivityHistory(url: db, readonly: true).rows()
            #expect(rows[0]["timestamp_available"] as? Bool == false)
            #expect(rows[0]["timestamp_ms"] == nil)
            let attrs = try FileManager.default.attributesOfItem(atPath: db.path)
            #expect((attrs[.posixPermissions] as? NSNumber)?.intValue == 0o600)
        }
    }

    @Test func malformedGapClearsMatchingContextAndOversizeRollsBack() throws {
        try withFiles { db, source in
            try Data((start + "{broken\n{\"type\":\"item_completed\",\"item\":{\"type\":\"CommandExecution\",\"id\":\"a\",\"exit_code\":1}}\n").utf8).write(to: source)
            _ = try ActivityHistory(url: db).ingest(source: source)
            let rows = try ActivityHistory(url: db, readonly: true).rows()
            #expect(rows[3]["kind"] as? String == "invalid_record")
            #expect((rows[4]["result"] as? [String: Any])?["association"] as? String == "unlinked")
            try append(String(repeating: " ", count: ActivityHistory.maxLine + 1) + "\n", to: source)
            #expect(throws: (any Error).self) { try ActivityHistory(url: db).ingest(source: source) }
            #expect(try ActivityHistory(url: db, readonly: true).rows().count == 5)
        }
    }

    @Test func separateSourcesAndQueryPages() throws {
        try withFiles { db, source in
            try Data(start.utf8).write(to: source)
            #expect(try ActivityHistory(url: db).ingest(source: source, maxRecords: 2)["batch_full"] as? Bool == true)
            _ = try ActivityHistory(url: db).ingest(source: source)
            let other = source.deletingLastPathComponent().appendingPathComponent("other.jsonl")
            try Data("{\"type\":\"session_meta\",\"id\":\"other\"}\n{\"type\":\"item_completed\",\"item\":{\"type\":\"CommandExecution\",\"id\":\"a\",\"exit_code\":1}}\n".utf8).write(to: other)
            _ = try ActivityHistory(url: db).ingest(source: other)
            let store = try ActivityHistory(url: db, readonly: true)
            #expect(try store.rows(session: "s").count == 3)
            #expect(try store.rows(after: 3).count == 2)
            let result = try store.rows(session: "other").last!["result"] as! [String: Any]
            #expect(result["association"] as? String == "unlinked")
            try FileManager.default.removeItem(at: source)
            #expect(throws: (any Error).self) { try ActivityHistory(url: db).ingest(source: source) }
            #expect(try store.rows().count == 5)
        }
    }

    @Test func refuseOtherOrFutureDatabaseWithoutOverwriting() throws {
        try withFiles { db, _ in
            try sql(db, "CREATE TABLE important(content TEXT)")
            let before = try Data(contentsOf: db)
            #expect(throws: (any Error).self) { try ActivityHistory(url: db) }
            #expect(try Data(contentsOf: db) == before)
            let future = db.deletingLastPathComponent().appendingPathComponent("future.db")
            _ = try ActivityHistory(url: future)
            try sql(future, "PRAGMA user_version=99")
            let futureBefore = try Data(contentsOf: future)
            #expect(throws: (any Error).self) { try ActivityHistory(url: future) }
            #expect(try Data(contentsOf: future) == futureBefore)
        }
    }

    @Test func nonregularAndHardLinkedDatabaseSourcesAreRejected() throws {
        try withFiles { db, source in
            var store: ActivityHistory? = try ActivityHistory(url: db)
            #expect(mkfifo(source.path, 0o600) == 0)
            #expect(throws: (any Error).self) { try store!.ingest(source: source) }
            #expect(try store!.rows().isEmpty)
            try FileManager.default.removeItem(at: source)
            #expect(Darwin.link(db.path, source.path) == 0)
            do {
                _ = try store!.ingest(source: source)
                Issue.record("Database hard link was accepted as a source")
            } catch let error as ActivityHistoryError {
                // Require our identity guard, not a coincidental SQLite I/O error.
                #expect(error.message == "The activity database cannot be its own source")
                #expect(error.sqliteCode == nil)
            }
            // macOS SQLite may invalidate an open DB after its hard links change
            // (SQLITE_IOERR_VNODE). Preserve that protection: close, remove only
            // this synthetic alias, then reopen to verify the history is intact.
            store = nil
            try FileManager.default.removeItem(at: source)
            #expect(try ActivityHistory(url: db, readonly: true).rows().isEmpty)
        }
    }

    @Test func foreignThreadIsNotGroupedUnderCurrentSession() throws {
        try withFiles { db, source in
            try Data((start + "{\"type\":\"function_call\",\"name\":\"shell\",\"call_id\":\"foreign\",\"thread_id\":\"other\"}\n").utf8).write(to: source)
            _ = try ActivityHistory(url: db).ingest(source: source)
            let row = try ActivityHistory(url: db, readonly: true).rows(session: "other")[0]
            #expect(row["kind"] as? String == "foreign_session_record")
            #expect(row["source_session_id"] as? String == "s")
            #expect(row["context_turn_id"] == nil)
        }
    }

    @Test func sharedContractsSurviveEveryRestart() throws {
        let fixture = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("tests/fixtures/codex-results-v1.json")
        let cases = (try JSONSerialization.jsonObject(with: Data(contentsOf: fixture)) as! [String: Any])["cases"] as! [[String: Any]]
        for item in cases {
            try withFiles { db, source in
                try Data("{\"type\":\"session_meta\",\"id\":\"synthetic-session\"}\n".utf8).write(to: source)
                _ = try ActivityHistory(url: db).ingest(source: source)
                for step in item["steps"] as! [[String: Any]] {
                    let record = try JSONSerialization.data(withJSONObject: step["record"]!)
                    try append(String(decoding: record, as: UTF8.self) + "\n", to: source)
                    _ = try ActivityHistory(url: db).ingest(source: source)
                    if let expected = step["result"] as? [String: Any] {
                        let actual = try ActivityHistory(url: db, readonly: true).rows().last!["result"] as! [String: Any]
                        for (key, value) in expected {
                            #expect((actual[key] as? NSObject) == (value as? NSObject), "\(item["name"]!): \(key)")
                        }
                    }
                }
            }
        }
    }
}
