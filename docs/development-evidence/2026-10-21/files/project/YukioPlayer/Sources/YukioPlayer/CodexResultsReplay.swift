import Foundation
import CryptoKit
import YukioCore

/// Local, metadata-only diagnostic export. This does not install a collector or
/// persist live history. The source line and hash let a developer find evidence.
func runCodexResults(path: String) -> Never {
    do {
        let url = URL(fileURLWithPath: path)
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let parser = CodexRolloutParser(session: CodexSessionsSource.sessionID(fromFileName: url.lastPathComponent))
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        var pending = Data()
        var lineNumber = 0
        func process(_ data: Data) throws {
            lineNumber += 1
            guard !data.allSatisfy({ [UInt8(13), 32, 9].contains($0) }) else { return }
            guard (try? JSONSerialization.jsonObject(with: data)) is [String: Any] else {
                throw NSError(domain: "YukioResults", code: 2,
                              userInfo: [NSLocalizedDescriptionKey: "Invalid JSON object at line \(lineNumber)"])
            }
            _ = parser.events(fromLine: data)
            for result in parser.lastToolResults {
                var row = try JSONSerialization.jsonObject(with: encoder.encode(result)) as! [String: Any]
                row["source_line"] = lineNumber
                row["source_record_sha256"] = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
                // A missing source timestamp must not look like a measured epoch time.
                let obj = try JSONSerialization.jsonObject(with: data) as! [String: Any]
                let payload = obj["payload"] as? [String: Any] ?? obj
                row["timestamp_available"] = PetEvent.parseTimestamp(obj["timestamp"] as? String) != nil
                    || PetEvent.parseTimestamp(payload["timestamp"] as? String) != nil
                let encoded = try JSONSerialization.data(withJSONObject: row, options: [.sortedKeys])
                FileHandle.standardOutput.write(encoded + Data([10]))
            }
        }
        while let chunk = try handle.read(upToCount: 64 * 1024), !chunk.isEmpty {
            pending.append(chunk)
            while let end = pending.firstIndex(of: 10) {
                guard end - pending.startIndex <= 8 << 20 else { throw ReplayError.oversized }
                try process(Data(pending[..<end]))
                pending.removeSubrange(...end)
            }
            guard pending.count <= 8 << 20 else { throw ReplayError.oversized }
        }
        if !pending.isEmpty { try process(pending) }
        exit(0)
    } catch {
        FileHandle.standardError.write(Data("Codex results export failed: \(error.localizedDescription)\n".utf8))
        exit(1)
    }
}

private enum ReplayError: LocalizedError {
    case oversized
    var errorDescription: String? { "A source line exceeds the 8 MiB diagnostic limit" }
}
