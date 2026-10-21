import Foundation
import Testing
@testable import YukioCore

private let fixtureURL = URL(fileURLWithPath: #filePath)
    .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    .deletingLastPathComponent().appendingPathComponent("tests/fixtures/codex-results-v1.json")

private func cases() throws -> [[String: Any]] {
    let root = try JSONSerialization.jsonObject(with: Data(contentsOf: fixtureURL)) as! [String: Any]
    return root["cases"] as! [[String: Any]]
}

@Suite struct CodexResultCorrelationTests {
    @Test(arguments: try! cases().map { $0["name"] as! String })
    func sharedResultContract(name: String) throws {
        let fixture = try cases().first { $0["name"] as? String == name }!
        let parser = CodexRolloutParser(session: "synthetic-session")
        for step in fixture["steps"] as! [[String: Any]] {
            let data = try JSONSerialization.data(withJSONObject: step["record"]!)
            let events = parser.events(fromLine: data, now: 1234)
            #expect(events.map { $0.kind.rawValue } == step["kinds"] as! [String], "\(name)")
            if let expected = step["result"] as? [String: Any] {
                let result = try #require(parser.lastToolResults.first)
                let actual = try JSONSerialization.jsonObject(with: JSONEncoder().encode(result)) as! [String: Any]
                for (key, value) in expected {
                    #expect((actual[key] as? NSObject) == (value as? NSObject), "\(name): \(key)")
                }
                if result.association == "unlinked" { #expect(result.callID == nil) }
            }
        }
    }

    @Test func malformedLineClearsLastResult() {
        let parser = CodexRolloutParser(session: "s")
        _ = parser.events(from: ["type": "function_call_output", "call_id": "a", "output": ["success": false]])
        #expect(parser.lastToolResults.count == 1)
        _ = parser.events(fromLine: Data("{broken".utf8))
        #expect(parser.lastToolResults.isEmpty)
    }

    @Test func boundedCorrelationEvictsWithoutGuessing() {
        let tracker = CodexResultTracker(capacity: 2)
        tracker.start("a"); tracker.start("b"); tracker.start("c")
        let old = tracker.record(session: "s", payload: [:], item: ["id": "a", "status": "failed"],
                                 sourceKind: "item_completed", timestamp: 0)
        #expect(old.association == "unlinked")
        #expect(old.outcome == .failed)
    }
}
