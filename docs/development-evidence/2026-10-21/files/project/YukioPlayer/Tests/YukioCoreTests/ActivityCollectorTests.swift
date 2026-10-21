import Foundation
import Testing
@testable import YukioCore

@Suite struct ActivityCollectorTests {
    func environment(_ body: (URL, URL, ActivityHistory) throws -> Void) throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("yukio-collector-\(UUID().uuidString)")
        let sessions = root.appendingPathComponent("sessions")
        try FileManager.default.createDirectory(at: sessions, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        try body(root, sessions, ActivityHistory(url: root.appendingPathComponent("history.db")))
    }
    @discardableResult func file(_ dir: URL, _ name: String, _ text: String) throws -> URL {
        let url = dir.appendingPathComponent(name)
        try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(text.utf8).write(to: url); return url
    }
    let message = "{\"type\":\"message\"}\n"

    @Test func discoversNewAndReactivatedSessionsWithoutDuplicates() throws {
        try environment { _, root, db in
            let old = try file(root, "old.jsonl", message)
            try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSinceNow: -90000)], ofItemAtPath: old.path)
            let c = try ActivityCollector(store: db, sessionsDirectory: root)
            #expect(try c.poll()["discovered_files"] as? Int == 0)
            try file(root, "2026/10/20/new.jsonl", message)
            #expect(try c.poll()["events_saved_this_run"] as? Int == 1)
            #expect(try c.poll()["events_saved_this_run"] as? Int == 1)
            try FileManager.default.setAttributes([.modificationDate: Date()], ofItemAtPath: old.path)
            #expect(try c.poll()["events_saved_this_run"] as? Int == 2)
        }
    }
    @Test func roundRobinAndRestartPartialResultIsolation() throws {
        try environment { _, root, db in
            let large = try file(root, "a.jsonl", String(repeating: message, count: 9))
            let small = try file(root, "b.jsonl", "{\"type\":\"session_meta\",\"id\":\"short\"}\n")
            for url in [large, small] { try FileManager.default.setAttributes([.modificationDate: Date(timeIntervalSince1970: 100)], ofItemAtPath: url.path) }
            let c = try ActivityCollector(store: db, sessionsDirectory: root, filesPerPoll: 1, recordsPerFile: 2)
            _ = try c.poll(now: Date(timeIntervalSince1970: 100)); _ = try c.poll(now: Date(timeIntervalSince1970: 100))
            #expect(try db.rows(session: "short").count == 1); #expect(try db.rows().count < 10)
        }
        try environment { _, root, db in
            let a = try file(root, "a.jsonl", "{\"type\":\"session_meta\",\"id\":\"a\"}\n{\"type\":\"function_call\",\"call_id\":\"same\",\"name\":\"shell\"}\n")
            try file(root, "b.jsonl", "{\"type\":\"session_meta\",\"id\":\"b\"}\n{\"type\":\"item_completed\",\"item\":{\"type\":\"CommandExecution\",\"id\":\"same\",\"exit_code\":1}}\n")
            _ = try ActivityCollector(store: db, sessionsDirectory: root).poll()
            try ActivityHistoryTests().append("{\"type\":\"function_call_output\",\"call_id\":\"same\",\"output\":{\"success\":true}}", to: a)
            let c = try ActivityCollector(store: db, sessionsDirectory: root); _ = try c.poll()
            #expect(try db.rows().count == 4)
            try ActivityHistoryTests().append("\n", to: a); _ = try c.poll()
            #expect(try c.poll()["events_saved_this_run"] as? Int == 1)
            #expect((try db.rows(session: "a").last?["result"] as? [String: Any])?["call_outcome"] as? String == "succeeded")
            #expect((try db.rows(session: "b").last?["result"] as? [String: Any])?["association"] as? String == "unlinked")
        }
    }
    @Test func badFileIsolationBackoffAndRecovery() throws {
        try environment { _, root, db in
            try file(root, "bad.jsonl", String(repeating: "x", count: ActivityHistory.maxLine + 1) + "\n")
            try file(root, "good.jsonl", message)
            let c = try ActivityCollector(store: db, sessionsDirectory: root)
            #expect(try c.poll(monotonic: 10)["state"] as? String == "degraded")
            #expect(try db.rows().count == 1)
            #expect(try c.poll(monotonic: 11)["events_saved_this_run"] as? Int == 1)
            try file(root, "bad.jsonl", message)
            #expect(try c.poll(monotonic: 11)["error_files"] as? Int == 0)
            #expect(try db.rows().count == 2)
        }
    }
    @Test func missingRootAndDeletedSourceKeepHistory() throws {
        try environment { _, root, db in
            try FileManager.default.removeItem(at: root)
            let c = try ActivityCollector(store: db, sessionsDirectory: root)
            #expect(try c.poll()["state"] as? String == "source_unavailable")
            let url = try file(root, "one.jsonl", message)
            #expect(try c.poll()["events_saved_this_run"] as? Int == 1)
            try FileManager.default.removeItem(at: url)
            #expect(try c.poll()["discovered_files"] as? Int == 0)
            #expect(try db.rows().count == 1)
        }
    }
    @Test func linksAndDiscoveryLimitsAreExplicit() throws {
        try environment { dir, root, db in
            let outside = try file(dir, "private.jsonl", message)
            try FileManager.default.createSymbolicLink(at: root.appendingPathComponent("link.jsonl"), withDestinationURL: outside)
            try FileManager.default.createSymbolicLink(at: root.appendingPathComponent("loop"), withDestinationURL: root)
            #expect(try ActivityCollector(store: db, sessionsDirectory: root).poll()["discovered_files"] as? Int == 0)
            #expect(throws: (any Error).self) { try db.ingest(source: outside, sourceRoot: root) }
            try file(root, "one.jsonl", message); try file(root, "two.jsonl", message)
            let status = try ActivityCollector(store: db, sessionsDirectory: root, maxFiles: 1).poll()
            #expect(status["scan_complete"] as? Bool == false); #expect(status["state"] as? String == "degraded")
            #expect(status["discovered_files"] as? Int == 2); #expect(status["tracked_files"] as? Int == 1)
            #expect(try ActivityCollector(store: db, sessionsDirectory: root, maxEntries: 1).poll()["scan_complete"] as? Bool == false)
        }
    }
    @Test func storageFullAndOverBudgetPreserveHistory() throws {
        try environment { _, root, db in
            try file(root, "full.jsonl", String(repeating: message, count: 100))
            let before = try db.databaseBytes()
            let c = try ActivityCollector(store: db, sessionsDirectory: root, maxBytes: before)
            #expect(try c.poll()["state"] as? String == "paused_capacity")
            #expect(try db.rows().isEmpty); #expect(try db.databaseBytes() == before)
            #expect(try c.poll()["events_saved_this_run"] as? Int == 0)
            #expect(try ActivityCollector(store: db, sessionsDirectory: root).poll()["events_saved_this_run"] as? Int == 100)
            #expect(try ActivityCollector(store: db, sessionsDirectory: root, maxBytes: 1).poll()["state"] as? String == "paused_capacity")
            #expect(try db.rows().count == 100)
        }
    }
    @Test func statusPrivacyAndUnrelatedFileProtection() throws {
        try environment { dir, root, db in
            let database = dir.appendingPathComponent("history.db")
            let unrelated = try file(dir, "important.txt", "important")
            #expect(throws: (any Error).self) { try ActivityCollector.validateStatusURL(unrelated, database: database, sessionsDirectory: root) }
            #expect(try String(contentsOf: unrelated) == "important")
            #expect(throws: (any Error).self) { try ActivityCollector.validateStatusURL(database, database: database, sessionsDirectory: root) }
            #expect(throws: (any Error).self) { try ActivityCollector.validateStatusURL(root.appendingPathComponent("status.json"), database: database, sessionsDirectory: root) }
            let status = dir.appendingPathComponent("collector.json")
            try ActivityCollector.validateStatusURL(status, database: database, sessionsDirectory: root)
            let c = try ActivityCollector(store: db, sessionsDirectory: root)
            try ActivityCollector.writeStatus(c.poll(), to: status)
            try ActivityCollector.writeStatus(c.stopped(), to: status)
            let text = try String(contentsOf: status)
            #expect(!text.contains(dir.path)); #expect(!text.contains("session_id")); #expect(text.contains("stopped"))
            try ActivityCollector.validateStatusURL(status, database: database, sessionsDirectory: root)
            #expect((try FileManager.default.attributesOfItem(atPath: status.path)[.posixPermissions] as? NSNumber)?.intValue == 0o600)
        }
    }
}
