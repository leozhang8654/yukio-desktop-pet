import Foundation
import Darwin
import YukioCore

private final class CollectorStop: @unchecked Sendable {
    private let lock = NSLock()
    private var stopped = false
    func stop() { lock.lock(); stopped = true; lock.unlock() }
    var requested: Bool { lock.lock(); defer { lock.unlock() }; return stopped }
}

func runActivityCollector(arguments: [String]) -> Never {
    var collector: ActivityCollector?, statusURL: URL?
    var leases: [FileHandle] = []
    var failure = false
    do {
        let allowed = ["--activity-collect", "--sessions-dir", "--status-file", "--seconds", "--max-database-mb", "--source-format"]
        var options: [String: String] = [:], index = 1
        while index < arguments.count {
            let key = arguments[index]
            guard allowed.contains(key), options[key] == nil, index + 1 < arguments.count,
                  !arguments[index + 1].hasPrefix("--") else { throw NSError(domain: "Collector options", code: 1) }
            options[key] = arguments[index + 1]; index += 2
        }
        guard let path = options["--activity-collect"], let seconds = Double(options["--seconds"] ?? "0"),
              seconds.isFinite, seconds >= 0, let mb = Int64(options["--max-database-mb"] ?? "256"), (1...4096).contains(mb) else {
            throw NSError(domain: "Collector options", code: 1)
        }
        guard let format = ActivitySourceFormat(rawValue: options["--source-format"] ?? "codex") else {
            throw NSError(domain: "Collector format", code: 1)
        }
        let db = URL(fileURLWithPath: path)
        let root = options["--sessions-dir"].map { URL(fileURLWithPath: $0) } ?? (format == .claude ? ClaudeTranscriptSource.defaultProjectsDir() : CodexSessionsSource.defaultSessionsDir())
        let destination = options["--status-file"].map { URL(fileURLWithPath: $0) }
        if let destination { try ActivityCollector.validateStatusURL(destination, database: db, sessionsDirectory: root) }
        for target in [db] + (destination.map { [$0] } ?? []) {
            let lockPath = target.resolvingSymlinksInPath().standardizedFileURL.path + ".collector.lock"
            try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let fd = Darwin.open(lockPath, O_RDWR | O_CREAT | O_NOFOLLOW, 0o600)
            guard fd >= 0 else { throw NSError(domain: "Collector lease", code: 1) }
            leases.append(FileHandle(fileDescriptor: fd, closeOnDealloc: true))
            guard flock(fd, LOCK_EX | LOCK_NB) == 0 else { throw NSError(domain: "Collector lease", code: 2) }
        }
        let store = try ActivityHistory(url: db)
        collector = try ActivityCollector(store: store, sessionsDirectory: root, maxBytes: mb << 20, sourceFormat: format)
        statusURL = destination
        let stop = CollectorStop()
        signal(SIGINT, SIG_IGN); signal(SIGTERM, SIG_IGN)
        let signals = [SIGINT, SIGTERM].map { sig in
            let source = DispatchSource.makeSignalSource(signal: sig, queue: .global())
            source.setEventHandler { stop.stop() }; source.resume(); return source
        }
        defer { signals.forEach { $0.cancel() } }
        let start = ProcessInfo.processInfo.systemUptime
        while !stop.requested {
            let snapshot = try collector!.poll()
            if let statusURL { try ActivityCollector.writeStatus(snapshot, to: statusURL) }
            let elapsed = ProcessInfo.processInfo.systemUptime - start
            if seconds > 0 && elapsed >= seconds { break }
            Thread.sleep(forTimeInterval: seconds > 0 ? min(2, max(0, seconds - elapsed)) : 2)
        }
    } catch {
        failure = true
        FileHandle.standardError.write(Data("Activity collector could not continue; check local paths, database ownership and storage.\n".utf8))
    }
    if let collector {
        var snapshot = failure ? collector.last : collector.stopped()
        if failure { snapshot["state"] = "failed"; snapshot["issue"] = "collector_error"; snapshot["updated_at"] = ActivityCollector.timestamp() }
        do {
            if let statusURL { try ActivityCollector.writeStatus(snapshot, to: statusURL) }
            try FileHandle.standardOutput.write(contentsOf: JSONSerialization.data(withJSONObject: snapshot, options: [.sortedKeys]) + Data([10]))
        } catch { failure = true }
    }
    for lease in leases { try? lease.close() }
    exit(failure ? 1 : 0)
}
