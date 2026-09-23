import Foundation

public enum ToolClassification: Equatable, Sendable {
    case activity(PetState)
    /// 轮询／结束后台命令等：延续该会话上一个工具的活动。
    case continuePrevious
}

/// Claude Code 工具 → 雪绪活动。
///
/// 规则有限且可测试：内置工具按名称映射；Bash 按命令首词和少量子命令判断；
/// MCP 工具按名称关键字判断。无法确定时一律回默认电脑桌，不猜测为测试。
public enum ClaudeToolClassifier {
    static let imageExtensions: Set<String> = [
        "png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "heic", "heif", "svg", "ico",
    ]

    /// 别家（Deep Code、Codex、各式 MCP 插件）用小写或别名写同一件事：统一成 Claude 的工具名再分类，
    /// 一套规则管三家。认不出的原样返回，落到 mcp__ 或默认电脑桌。
    public static func canonicalName(_ tool: String) -> String {
        if tool.hasPrefix("mcp__") { return tool }
        return aliases[tool.lowercased()] ?? tool
    }

    static let aliases: [String: String] = [
        "read": "Read", "readfile": "Read", "read_file": "Read", "view_file": "Read", "openfile": "Read",
        "readimage": "ReadImage", "understandimage": "UnderstandImage", "view_image": "ViewImage",
        "read_image": "ReadImage", "viewimage": "ViewImage",
        "write": "Write", "writefile": "Write", "write_file": "Write", "create_file": "Write", "createfile": "Write",
        "edit": "Edit", "editfile": "Edit", "edit_file": "Edit", "multiedit": "MultiEdit",
        "str_replace_editor": "Edit", "apply_patch": "Edit", "applypatch": "Edit",
        "notebookread": "NotebookRead", "notebookedit": "NotebookEdit",
        "bash": "Bash", "shell": "Bash", "run_command": "Bash", "runcommand": "Bash", "terminal": "Bash",
        "exec_command": "Bash", "run_terminal_cmd": "Bash", "powershell": "PowerShell",
        "glob": "Glob", "grep": "Grep", "ls": "LS", "listdir": "LS", "list_dir": "LS",
        "search": "Grep", "codebase_search": "Grep", "find": "Glob",
        "webfetch": "WebFetch", "web_fetch": "WebFetch", "fetch": "WebFetch",
        "websearch": "WebSearch", "web_search": "WebSearch",
        "bashoutput": "BashOutput", "readbashoutput": "BashOutput", "killshell": "KillShell", "killbash": "KillBash",
        "todowrite": "TodoWrite", "updateplan": "TodoWrite", "update_plan": "TodoWrite", "taskcreate": "TaskCreate",
        "taskupdate": "TaskUpdate", "tasklist": "TaskList", "taskget": "TaskGet",
        "enterplanmode": "EnterPlanMode", "exitplanmode": "ExitPlanMode", "exit_plan_mode": "ExitPlanMode",
        "toolsearch": "ToolSearch", "skill": "Skill", "task": "Task", "agent": "Agent",
        "askuserquestion": "AskUserQuestion", "ask_user_question": "AskUserQuestion",
        "request_user_input": "AskUserQuestion", "request_user_input_async": "AskUserQuestion",
    ]

    public static func classify(tool rawTool: String, input: [String: Any]) -> ToolClassification {
        let tool = canonicalName(rawTool)
        switch tool {
        case "ReadImage", "UnderstandImage", "ViewImage":
            return .activity(.view_image)
        case "Read":
            let path = (input["file_path"] as? String) ?? (input["path"] as? String) ?? ""
            let ext = (path as NSString).pathExtension.lowercased()
            return .activity(imageExtensions.contains(ext) ? .view_image : .read_file)
        case "Glob", "Grep", "LS", "NotebookRead":
            return .activity(.read_file)
        case "Write", "Edit", "MultiEdit", "NotebookEdit":
            return .activity(.write_file)
        case "WebFetch", "WebSearch":
            return .activity(.read_web)
        case "Bash", "PowerShell":
            return .activity(classifyShell((input["command"] as? String) ?? ""))
        case "BashOutput", "KillShell", "KillBash", "TaskOutput", "TaskStop":
            return .continuePrevious
        case "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet",
             "EnterPlanMode", "ExitPlanMode", "ToolSearch":
            return .activity(.thinking)
        case "AskUserQuestion":
            // 等待用户回答：不是在工作。
            return .activity(.question_for_user)
        default:
            break
        }
        if tool.hasPrefix("mcp__") {
            return .activity(classifyMCP(tool: tool, input: input))
        }
        return .activity(.default_work)
    }

    static func classifyMCP(tool: String, input: [String: Any]) -> PetState {
        let name = tool.lowercased()
        let action = (input["action"] as? String)?.lowercased()
        if name.contains("screenshot") || name.contains("view_image") || name.contains("read_image")
            || action == "screenshot" || action == "zoom" {
            return .view_image
        }
        let webHints = ["browser", "chrome", "navigate", "webfetch", "web_fetch", "fetch_url", "get_page", "read_page"]
        if webHints.contains(where: name.contains) {
            return .read_web
        }
        return .default_work
    }

    // MARK: Shell

    enum ShellKind: Int, Comparable {
        case neutral = 0, read, other, web, write, verify
        static func < (a: ShellKind, b: ShellKind) -> Bool { a.rawValue < b.rawValue }
    }

    /// 按命令判断活动。组合命令取最强类别：验证 > 写入 > 网页 > 其他 > 读取。
    public static func classifyShell(_ command: String) -> PetState {
        let (segments, writesViaRedirect) = ShellTokenizer.segments(command)
        var kinds = segments.map(kind(of:))
        if writesViaRedirect { kinds.append(.write) }
        switch kinds.max() ?? .neutral {
        case .verify: return .verify
        case .write: return .write_file
        case .web: return .read_web
        case .read: return .read_file
        case .other, .neutral: return .default_work
        }
    }

    static let neutralCommands: Set<String> = [
        "cd", "pushd", "popd", "export", "set", "unset", "source", ".", "echo", "printf", "true", "false",
        "sleep", "clear", "wait", "trap", "exit", "pwd", "date", "whoami",
    ]
    static let readCommands: Set<String> = [
        "cat", "head", "tail", "less", "more", "nl", "wc", "rg", "grep", "egrep", "fgrep", "ag", "ls", "find",
        "fd", "tree", "stat", "file", "du", "df", "which", "type", "jq", "yq", "diff", "cmp", "strings", "xxd",
        "hexdump", "od", "shasum", "md5", "sha256sum", "md5sum", "realpath", "readlink", "basename", "dirname",
        "awk", "sort", "uniq", "cut", "column", "mdls", "plutil", "sips", "otool", "lsof", "ps", "pgrep",
    ]
    static let writeCommands: Set<String> = [
        "tee", "touch", "mkdir", "cp", "mv", "rm", "rmdir", "ln", "chmod", "chown", "install", "patch",
        "unzip", "rsync", "apply_patch", "ditto", "trash",
    ]
    static let webCommands: Set<String> = ["curl", "wget", "http", "https", "xh", "lynx", "w3m"]
    static let verifyCommands: Set<String> = [
        "pytest", "jest", "vitest", "mocha", "ava", "tox", "nox", "rspec", "phpunit", "ctest", "bats",
        "shellcheck", "eslint", "mypy", "pyright", "flake8", "pylint", "swiftlint", "golangci-lint", "playwright",
    ]
    static let wrappers: Set<String> = ["sudo", "time", "env", "command", "exec", "nohup", "xargs", "caffeinate"]
    static let testWords = ["test", "tests", "spec", "verify", "check", "lint", "typecheck"]

    static func mentionsTestWord(_ s: String) -> Bool {
        let parts = s.lowercased().split(whereSeparator: { !$0.isLetter })
        return parts.contains(where: { testWords.contains(String($0)) })
    }

    // MARK: 给人看的说明

    /// 气泡里“当前活动”的简短说明。只取文件名、命令前几个词、网址域名，不含文件内容。
    public static func describe(tool rawTool: String, input: [String: Any]) -> String? {
        let tool = canonicalName(rawTool)
        func name(_ key: String) -> String? {
            guard let p = input[key] as? String, !p.isEmpty else { return nil }
            return (p as NSString).lastPathComponent
        }
        func text(_ key: String) -> String? {
            guard let s = input[key] as? String else { return nil }
            let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
            return t.isEmpty ? nil : t
        }
        func host(_ url: String) -> String {
            guard let h = URL(string: url)?.host else { return url }
            return h.hasPrefix("www.") ? String(h.dropFirst(4)) : h
        }
        switch tool {
        case "ReadImage", "UnderstandImage", "ViewImage":
            guard let f = name("file_path") ?? name("path") ?? name("image_path") else { return nil }
            return tr("Viewing \(f)", "查看 \(f)")
        case "Read":
            guard let f = name("file_path") ?? name("path") else { return nil }
            return imageExtensions.contains((f as NSString).pathExtension.lowercased()) ? tr("Viewing \(f)", "查看 \(f)") : tr("Reading \(f)", "阅读 \(f)")
        case "NotebookRead": return name("notebook_path").map { tr("Reading \($0)", "阅读 \($0)") }
        case "Write": return name("file_path").map { tr("Writing \($0)", "写入 \($0)") }
        case "Edit", "MultiEdit": return name("file_path").map { tr("Editing \($0)", "编辑 \($0)") }
        case "NotebookEdit": return name("notebook_path").map { tr("Editing \($0)", "编辑 \($0)") }
        case "Grep": return text("pattern").map { tr("Searching \($0)", "搜索 \($0)") }
        case "Glob": return text("pattern").map { tr("Finding \($0)", "查找 \($0)") }
        case "LS": return name("path").map { tr("Viewing \($0)", "查看 \($0)") }
        case "WebFetch": return text("url").map { tr("Browsing \(host($0))", "浏览 \(host($0))") }
        case "WebSearch": return text("query").map { tr("Searching the web: \($0)", "搜索网页 \($0)") }
        case "Bash", "PowerShell":
            let command = text("command") ?? ""
            // heredoc 脚本（python3 - <<EOF …）从命令本身看不出在做什么，优先用调用时附带的说明。
            if command.contains("<<"), let d = text("description") { return d }
            return shellSummary(command).map { "$ \($0)" } ?? text("description")
        case "BashOutput", "KillShell", "KillBash", "TaskOutput", "TaskStop":
            return nil
        case "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet":
            return tr("Updating the task list", "整理任务清单")
        case "EnterPlanMode", "ExitPlanMode":
            return tr("Planning", "制定计划")
        case "ToolSearch":
            return tr("Finding tools", "查找工具")
        case "AskUserQuestion":
            return tr("Needs your answer", "等你回答")
        case "Agent", "Task":
            return text("description").map { tr("Delegating: \($0)", "委派：\($0)") } ?? tr("Delegating to a helper", "委派助手")
        case "Skill":
            return text("skill").map { tr("Skill \($0)", "技能 \($0)") }
        default:
            break
        }
        if tool.hasPrefix("mcp__") {
            let short = tool.components(separatedBy: "__").last ?? tool
            switch classifyMCP(tool: tool, input: input) {
            case .view_image: return tr("Screenshot", "截图")
            case .read_web: return text("url").map { tr("Browsing \(host($0))", "浏览 \(host($0))") } ?? tr("Browser \(short)", "浏览器 \(short)")
            default: return short
            }
        }
        return tool
    }

    /// 命令摘要：取决定分类的那一段（跳过 cd、export 等），最多前三个词，命令名只留文件名。
    public static func shellSummary(_ command: String) -> String? {
        // heredoc 的正文和结束标记会被当成命令分段，只看 << 之前的部分。
        let text = command.range(of: "<<").map { String(command[..<$0.lowerBound]) } ?? command
        let segments = ShellTokenizer.segments(text).segments.map(stripPrefix).filter { !$0.isEmpty }
        guard !segments.isEmpty else { return nil }
        let kinds = segments.map { kind(of: $0) }
        var best = 0
        for (i, k) in kinds.enumerated() where k > kinds[best] { best = i }
        var words = segments[best]
        if ["bash", "sh", "zsh"].contains(words[0]),
           let i = words.firstIndex(where: { $0 == "-c" || $0 == "-lc" }), i + 1 < words.count {
            return shellSummary(words[i + 1])
        }
        words[0] = (words[0] as NSString).lastPathComponent
        return words.prefix(3).joined(separator: " ")
    }

    /// 去掉前置环境变量与包装命令（sudo、time、timeout 30 …）。
    static func stripPrefix(_ rawWords: [String]) -> [String] {
        var words = rawWords
        while let w = words.first {
            if w.contains("="), !w.hasPrefix("-"), w.first?.isLetter == true || w.first == "_" {
                words.removeFirst()
            } else if wrappers.contains(w) {
                words.removeFirst()
            } else if w == "timeout" || w == "gtimeout" {
                words.removeFirst()
                if let n = words.first, Double(n.trimmingCharacters(in: .letters)) != nil { words.removeFirst() }
            } else {
                break
            }
        }
        return words
    }

    static func kind(of rawWords: [String]) -> ShellKind {
        let words = stripPrefix(rawWords)
        guard let first = words.first else { return .neutral }
        let cmd = (first as NSString).lastPathComponent
        let args = Array(words.dropFirst())
        let sub = args.first(where: { !$0.hasPrefix("-") }) ?? ""

        if neutralCommands.contains(cmd) { return .neutral }
        if verifyCommands.contains(cmd) { return .verify }
        if webCommands.contains(cmd) { return .web }

        switch cmd {
        case "bash", "sh", "zsh":
            if let i = args.firstIndex(where: { $0 == "-c" || $0 == "-lc" }), i + 1 < args.count {
                let inner = classifyShell(args[i + 1])
                switch inner {
                case .verify: return .verify
                case .write_file: return .write
                case .read_web: return .web
                case .read_file: return .read
                default: return .other
                }
            }
            if let script = args.first(where: { !$0.hasPrefix("-") }) {
                return mentionsTestWord((script as NSString).lastPathComponent) ? .verify : .other
            }
            return .other
        case "python", "python3", "node", "ruby", "deno", "bun", "php":
            if let i = args.firstIndex(of: "-m"), i + 1 < args.count {
                return ["pytest", "unittest", "mypy", "pyflakes", "ruff"].contains(args[i + 1]) ? .verify : .other
            }
            if args.contains("--test") || (cmd == "deno" && sub == "test") || (cmd == "bun" && sub == "test") {
                return .verify
            }
            if args.first == "-c" || args.first == "-e" { return .other }
            if let script = args.first(where: { !$0.hasPrefix("-") }) {
                return mentionsTestWord((script as NSString).lastPathComponent) ? .verify : .other
            }
            return .other
        case "npm", "pnpm", "yarn":
            if sub == "test" || sub == "t" { return .verify }
            if sub == "run" || cmd == "yarn" {
                let script = sub == "run" ? (args.drop(while: { $0 != "run" }).dropFirst().first ?? "") : sub
                return mentionsTestWord(script) ? .verify : .other
            }
            return .other
        case "npx", "bunx":
            let tool = sub
            if verifyCommands.contains(tool) || tool == "tsc" && args.contains("--noEmit") { return .verify }
            if tool == "prettier" && args.contains("--check") { return .verify }
            return .other
        case "tsc":
            return args.contains("--noEmit") ? .verify : .other
        case "ruff":
            return sub == "check" ? .verify : .other
        case "make", "just", "gmake":
            return mentionsTestWord(sub) ? .verify : .other
        case "swift":
            return sub == "test" ? .verify : .other
        case "xcodebuild":
            return args.contains("test") || args.contains("test-without-building") ? .verify : .other
        case "cargo":
            return ["test", "check", "clippy", "nextest"].contains(sub) ? .verify : .other
        case "go":
            return ["test", "vet"].contains(sub) ? .verify : .other
        case "dotnet", "mvn", "gradle", "gradlew", "./gradlew":
            return ["test", "verify", "check"].contains(sub) ? .verify : .other
        case "git":
            let readSubs: Set<String> = ["status", "log", "show", "diff", "blame", "branch", "ls-files",
                                         "rev-parse", "grep", "remote", "describe", "shortlog", "reflog"]
            let writeSubs: Set<String> = ["add", "commit", "checkout", "switch", "restore", "stash", "merge",
                                          "rebase", "reset", "apply", "mv", "rm", "cherry-pick", "pull", "revert", "tag"]
            if readSubs.contains(sub) { return .read }
            if writeSubs.contains(sub) { return .write }
            return .other
        case "sed":
            return args.contains(where: { $0 == "-i" || $0.hasPrefix("-i") || $0 == "--in-place" }) ? .write : .read
        case "perl":
            return args.contains(where: { $0.hasPrefix("-") && $0.contains("i") && $0.contains("p") || $0 == "-i" }) ? .write : .other
        case "tar":
            return args.contains(where: { $0.hasPrefix("-") ? $0.contains("x") : $0.hasPrefix("x") }) ? .write : .other
        case "open":
            return args.contains(where: { $0.hasPrefix("http://") || $0.hasPrefix("https://") }) ? .web : .other
        default:
            break
        }
        if readCommands.contains(cmd) { return .read }
        if writeCommands.contains(cmd) { return .write }
        if mentionsTestWord(cmd) && (first.hasPrefix("./") || first.contains("/")) { return .verify }
        return .other
    }
}

/// 极简 shell 分词：按 && || ; | 换行 分段，处理引号与反斜杠；识别写入文件的重定向。
/// 不求完整 POSIX，只为分类服务。
enum ShellTokenizer {
    static func segments(_ command: String) -> (segments: [[String]], writesViaRedirect: Bool) {
        var segments: [[String]] = []
        var words: [String] = []
        var word = ""
        var hasWord = false
        var quote: Character?
        var escape = false
        var expectRedirectTarget = false
        var writes = false
        let chars = Array(command)
        var i = 0

        func endWord() {
            guard hasWord else { return }
            if expectRedirectTarget {
                if word != "/dev/null" && !word.hasPrefix("&") && word != "/dev/stderr" && word != "/dev/stdout" {
                    writes = true
                }
                expectRedirectTarget = false
            } else {
                words.append(word)
            }
            word = ""
            hasWord = false
        }
        func endSegment() {
            endWord()
            if !words.isEmpty { segments.append(words) }
            words = []
        }

        while i < chars.count {
            let c = chars[i]
            if escape {
                word.append(c); hasWord = true; escape = false; i += 1; continue
            }
            if let q = quote {
                if c == q { quote = nil } else if c == "\\" && q == "\"" { escape = true } else { word.append(c) }
                i += 1; continue
            }
            switch c {
            case "\\":
                escape = true
            case "'", "\"":
                quote = c; hasWord = true
            case " ", "\t":
                endWord()
            case "\n", ";":
                endSegment()
            case "&":
                if i + 1 < chars.count && chars[i + 1] == "&" { endSegment(); i += 1 }
                else if i + 1 < chars.count && chars[i + 1] == ">" {
                    // &> 或 &>> 重定向
                    endWord(); i += 1
                    if i + 1 < chars.count && chars[i + 1] == ">" { i += 1 }
                    expectRedirectTarget = true
                } else if hasWord && word.hasSuffix(">") {
                    word.append(c)
                } else { endSegment() }  // 后台运行 &
            case "|":
                if i + 1 < chars.count && chars[i + 1] == "|" { i += 1 }
                endSegment()
            case ">":
                // 2>&1、>&2 之类只是转移流，不写文件。
                let fdPrefix = hasWord && word.allSatisfy(\.isNumber)
                if hasWord && !fdPrefix { endWord() }
                if fdPrefix { word = ""; hasWord = false }
                if i + 1 < chars.count && chars[i + 1] == ">" { i += 1 }
                if i + 1 < chars.count && chars[i + 1] == "&" {
                    i += 1
                    while i + 1 < chars.count && (chars[i + 1].isNumber || chars[i + 1] == "-") { i += 1 }
                } else {
                    expectRedirectTarget = true
                }
            case "<":
                // 输入重定向与 heredoc：跳过标记本身。
                endWord()
                while i + 1 < chars.count && (chars[i + 1] == "<" || chars[i + 1] == "-") { i += 1 }
                expectRedirectTarget = false
            case "(", ")", "{", "}":
                // 子 shell 与分组当作分段边界处理（$() 中的命令也会被计入，可接受）。
                if c == "(" && word.hasSuffix("$") { word.removeLast() }
                endSegment()
            default:
                word.append(c); hasWord = true
            }
            i += 1
        }
        if expectRedirectTarget && hasWord { endWord() }
        endSegment()
        return (segments, writes)
    }
}
