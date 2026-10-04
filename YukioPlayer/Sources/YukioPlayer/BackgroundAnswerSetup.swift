import Foundation
import YukioCore

enum BackgroundAnswerSetup {
    enum Failure: LocalizedError {
        case unavailable, deepSeekNotConnected
        var errorDescription: String? {
            switch self {
            case .unavailable: return tr("Could not configure Claude answers", "无法配置 Claude 回答通道")
            case .deepSeekNotConnected: return tr("DeepSeek adapter needed · see answer setup", "DeepSeek 未接入 · 请查看后台回答说明")
            }
        }
    }
    /// Merge only the AskUserQuestion hook; preserve all other user settings.
    static func mergedSettings(_ original: [String: Any], executable: String) -> [String: Any] {
        var result = original
        var hooks = result["hooks"] as? [String: Any] ?? [:]
        var pre = hooks["PreToolUse"] as? [[String: Any]] ?? []
        let quoted = "'" + executable.replacingOccurrences(of: "'", with: "'\\''") + "' --claude-answer-hook"
        for index in pre.indices {
            var commands = pre[index]["hooks"] as? [[String: Any]] ?? []
            commands.removeAll { $0["yukioAnswerBridge"] as? Bool == true || ($0["command"] as? String)?.contains("YukioAnswerBridge' --claude-answer-hook") == true }
            pre[index]["hooks"] = commands
        }
        pre.removeAll { ($0["hooks"] as? [Any])?.isEmpty == true }
        pre.append(["matcher": "AskUserQuestion", "hooks": [["type": "command", "command": quoted, "timeout": 600]]])
        hooks["PreToolUse"] = pre
        result["hooks"] = hooks
        return result
    }
    static func deepSeekInstaller() throws -> Process {
        let fm = FileManager.default
        let support = fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/YukioPlayer")
        try fm.createDirectory(at: support, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        guard let resources = Bundle.main.resourceURL,
              fm.fileExists(atPath: resources.appendingPathComponent("deepseek-answers/setup.mjs").path),
              let node = ["/opt/homebrew/bin/node", "/usr/local/bin/node"].first(where: { fm.isExecutableFile(atPath: $0) }) else { throw Failure.unavailable }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: node)
        process.arguments = [resources.appendingPathComponent("deepseek-answers/setup.mjs").path]
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = URL(fileURLWithPath: node).deletingLastPathComponent().path + ":/usr/bin:/bin:/usr/sbin:/sbin:" + (environment["PATH"] ?? "")
        process.environment = environment
        let log = support.appendingPathComponent("deepseek-setup.log")
        fm.createFile(atPath: log.path, contents: nil, attributes: [.posixPermissions: 0o600])
        let handle = try FileHandle(forWritingTo: log)
        process.standardOutput = handle
        process.standardError = handle
        return process
    }
    static func installClaude() throws {
        let fm = FileManager.default
        let support = fm.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/YukioPlayer")
        try fm.createDirectory(at: support, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        guard let executable = Bundle.main.executableURL else { throw Failure.unavailable }
        let helper = support.appendingPathComponent("YukioAnswerBridge")
        // Atomic replacement; an existing running hook keeps its original inode.
        try Data(contentsOf: executable).write(to: helper, options: .atomic)
        try fm.setAttributes([.posixPermissions: 0o700], ofItemAtPath: helper.path)
        let configRoot = ProcessInfo.processInfo.environment["CLAUDE_CONFIG_DIR"].map { URL(fileURLWithPath: $0) }
            ?? fm.homeDirectoryForCurrentUser.appendingPathComponent(".claude")
        try fm.createDirectory(at: configRoot, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let settings = configRoot.appendingPathComponent("settings.json")
        let exists = fm.fileExists(atPath: settings.path)
        let data = exists ? try Data(contentsOf: settings) : Data("{}".utf8)
        guard let original = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { throw Failure.unavailable }
        if exists {
            try data.write(to: support.appendingPathComponent("claude-settings-before-answers-\(Int(Date().timeIntervalSince1970)).json"), options: .atomic)
        }
        let output = mergedSettings(original, executable: helper.path)
        try JSONSerialization.data(withJSONObject: output, options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]).write(to: settings, options: .atomic)
    }
}
