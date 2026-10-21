import Foundation

/// Extracts selection/focus metadata from Codex's local desktop diagnostics.
/// Message bodies and window titles are not retained.
/// Only explicit view-activity events select a thread; background task events cannot select one.
/// This is an internal log format. Missing/changed data fails open: keep completion reminders.
public struct CodexOpenChatState {
    private var selected: [String: String] = [:]
    private var focusedWindow: String?
    private var focusObservedAt: Double = -.infinity

    private let timestampFormatter: ISO8601DateFormatter

    public init() {
        timestampFormatter = ISO8601DateFormatter()
        timestampFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    }

    public mutating func ingest(_ line: String) {
        guard line.contains(" [electron-message-handler] "),
              let split = line.range(of: " [electron-message-handler] "),
              let timestamp = line.split(separator: " ").first,
              let date = timestampFormatter.date(from: String(timestamp)) else { return }
        let at = date.timeIntervalSince1970 * 1000
        let body = String(line[split.upperBound...])
        // Metadata is appended to diagnostic lines by the desktop logger.
        let fields = body.split(separator: " ").reduce(into: [String: String]()) { result, token in
            let pair = token.split(separator: "=", maxSplits: 1)
            if pair.count == 2 { result[String(pair[0])] = String(pair[1]) }
        }
        guard fields["rendererWindowAppearance"] == "primary",
              let window = fields["rendererWindowId"], Int(window) != nil,
              let focused = fields["rendererWindowFocused"], ["true", "false"].contains(focused),
              let visible = fields["rendererWindowVisible"], ["true", "false"].contains(visible) else { return }
        if at >= focusObservedAt {
            if focused == "true" && visible == "true" {
                focusedWindow = window
                focusObservedAt = at
            } else if focusedWindow == window {
                focusedWindow = nil
                focusObservedAt = at
            }
        }
        guard body.hasPrefix("thread_stream_view_activity_changed "),
              let id = fields["conversationId"], UUID(uuidString: id) != nil else { return }
        if fields["active"] == "true" {
            selected[window] = id
        } else if fields["active"] == "false", selected[window] == id {
            selected.removeValue(forKey: window)
        }
    }

    public func session(now: Double) -> String? {
        // A stale focus observation must not silently dismiss an unseen completion.
        guard now >= focusObservedAt, now - focusObservedAt <= 10_000,
              let window = focusedWindow else { return nil }
        return selected[window]
    }
}

/// Incremental reader. Restrict logs to the currently running Codex PID, so an old
/// process cannot suppress cards after restart. IO runs on the player's utility queue.
public final class CodexOpenChat {
    public let logsDirectory: URL
    private var processID: Int32?
    private var state = CodexOpenChatState()
    private var offsets: [URL: UInt64] = [:]
    private var partial: [URL: Data] = [:]

    public init(logsDirectory: URL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Logs/com.openai.codex")) {
        self.logsDirectory = logsDirectory
    }

    public func focusedSession(processID: Int32, now: Double) -> String? {
        if self.processID != processID {
            self.processID = processID
            state = CodexOpenChatState()
            offsets.removeAll()
            partial.removeAll()
        }
        let fm = FileManager.default
        guard let iterator = fm.enumerator(at: logsDirectory,
            includingPropertiesForKeys: [.fileSizeKey], options: [.skipsHiddenFiles]) else { return nil }
        let marker = "-\(processID)-t0-"
        let files = iterator.compactMap { $0 as? URL }.filter {
            $0.pathExtension == "log" && $0.lastPathComponent.hasPrefix("codex-desktop-")
                && $0.lastPathComponent.contains(marker)
        }.sorted { $0.path < $1.path }.suffix(8)
        guard !files.isEmpty else { return nil }
        for file in files {
            guard let values = try? file.resourceValues(forKeys: [.fileSizeKey]),
                  let size = values.fileSize, let handle = try? FileHandle(forReadingFrom: file) else { continue }
            defer { try? handle.close() }
            let end = UInt64(size)
            var start = offsets[file] ?? 0
            if start > end {
                // Truncation means the cached view can no longer be trusted.
                state = CodexOpenChatState()
                partial.removeValue(forKey: file)
                start = 0
            }
            guard start < end else { continue }
            // Bound startup/rotation work. If the view event is outside this tail,
            // no session is inferred; a subsequent navigation restores detection.
            let limit: UInt64 = 4 << 20
            let skipped = end - start > limit
            if skipped {
                start = end - limit
                partial.removeValue(forKey: file)
                state = CodexOpenChatState()
            }
            do {
                try handle.seek(toOffset: start)
                var data = partial[file] ?? Data()
                data.append(try handle.read(upToCount: Int(end - start)) ?? Data())
                offsets[file] = try handle.offset()
                if skipped, let newline = data.firstIndex(of: 10) { data.removeSubrange(...newline) }
                while let newline = data.firstIndex(of: 10) {
                    state.ingest(String(decoding: data[..<newline], as: UTF8.self))
                    data.removeSubrange(...newline)
                }
                partial[file] = data
            } catch { return nil }
        }
        return state.session(now: now)
    }
}
