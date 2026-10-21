import Foundation
import YukioCore

/// Headless local collector; it can run alongside the installed desktop pet.
func runActivityHistory(arguments: [String]) -> Never {
    do {
        let flags = ["--activity-import", "--activity-follow", "--activity-history"]
        let command = flags.first { arguments.contains($0) }!
        let index = arguments.firstIndex(of: command)!
        let needed = command == "--activity-history" ? 1 : 2
        guard arguments.count > index + needed,
              !arguments[(index + 1)...(index + needed)].contains(where: { $0.hasPrefix("--") }) else {
            throw CLIHistoryError("Usage: --activity-import DB SOURCE | --activity-follow DB SOURCE [--seconds N] | --activity-history DB [--after N] [--limit N] [--session ID]")
        }
        func option(_ key: String, _ fallback: String?) throws -> String? {
            guard let i = arguments.firstIndex(of: key) else { return fallback }
            guard i + 1 < arguments.count, !arguments[i + 1].hasPrefix("--") else { throw CLIHistoryError("Missing value for \(key)") }
            return arguments[i + 1]
        }
        guard let format = ActivitySourceFormat(rawValue: try option("--source-format", "codex")!) else {
            throw CLIHistoryError("Unsupported activity source format")
        }
        guard let seconds = Double(try option("--seconds", "0")!), seconds.isFinite, seconds >= 0 else {
            throw CLIHistoryError("Seconds must be finite and nonnegative")
        }
        let store = try ActivityHistory(url: URL(fileURLWithPath: arguments[index + 1]), readonly: command == "--activity-history")
        func emit(_ row: [String: Any]) throws {
            let data = try JSONSerialization.data(withJSONObject: row, options: [.sortedKeys, .withoutEscapingSlashes])
            try FileHandle.standardOutput.write(contentsOf: data + Data([10]))
        }
        if command == "--activity-history" {
            guard let after = Int64(try option("--after", "0")!), let limit = Int(try option("--limit", "500")!) else {
                throw CLIHistoryError("Invalid history page")
            }
            for row in try store.rows(after: after, limit: limit, session: try option("--session", nil)) { try emit(row) }
        } else {
            let start = ProcessInfo.processInfo.systemUptime
            let source = URL(fileURLWithPath: arguments[index + 2])
            var revision: String?, batchFull = true
            while true {
                let current = try ActivityHistory.sourceRevision(source)
                if current != revision || batchFull {
                    let result = try store.ingest(source: source, sourceFormat: format)
                    try emit(result)
                    batchFull = result["batch_full"] as? Bool == true
                    if !batchFull { revision = current }
                }
                let elapsed = ProcessInfo.processInfo.systemUptime - start
                if command == "--activity-follow" && seconds > 0 && elapsed >= seconds { break }
                if batchFull { continue }
                if command == "--activity-import" { break }
                Thread.sleep(forTimeInterval: seconds > 0 ? min(2, max(0, seconds - elapsed)) : 2)
            }
        }
        exit(0)
    } catch {
        let message = "Activity history failed: \(error.localizedDescription)\n"
        FileHandle.standardError.write(Data(message.utf8))
        exit(1)
    }
}
private struct CLIHistoryError: Error, LocalizedError {
    let errorDescription: String?
    init(_ message: String) { errorDescription = message }
}
