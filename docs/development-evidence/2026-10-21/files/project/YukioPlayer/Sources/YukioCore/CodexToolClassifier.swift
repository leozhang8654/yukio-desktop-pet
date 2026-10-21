import Foundation

/// Codex（GPT）工具 → 雪绪活动。
///
/// Codex 的工具跟 Claude 的不是一套：一部分是普通的 `function_call`（`shell`、`apply_patch`、
/// `update_plan`、`view_image`…），桌面版还有一个万能的 `exec`——真正在干什么写在它的 JS 正文里
/// （`tools.exec_command({cmd:"…"})`、`tools.apply_patch(…)`、`tools.view_image({path:"…"})`）。
/// 命令本身的判断（读／写／跑测试／看网页）直接用 Claude 那一套 `classifyShell`，两边一致。
public enum CodexToolClassifier {
    /// 返回活动与气泡里那句简短说明。说明只含文件名、命令前几个词、网址域名，不含文件内容。
    public static func classify(tool: String, namespace: String? = nil,
                                arguments: [String: Any] = [:], script: String? = nil) -> (ToolClassification, String?) {
        let key = tool.lowercased()

        // 桌面版的 exec：正文里写着真正在干什么。
        if let script, !script.isEmpty, let hit = CodexExecScript.classify(script) { return hit }

        switch key {
        case "shell", "local_shell", "exec", "exec_command", "container.exec", "run_command", "run_terminal_cmd":
            let command = Self.command(from: arguments)
            guard !command.isEmpty else { return (.activity(.default_work), nil) }
            return (.activity(ClaudeToolClassifier.classifyShell(command)),
                    ClaudeToolClassifier.shellSummary(command).map { "$ \($0)" })

        case "apply_patch", "applypatch", "edit_file", "write_file", "create_file", "str_replace_editor":
            let patch = (arguments["input"] as? String) ?? (arguments["patch"] as? String) ?? script ?? ""
            let name = CodexExecScript.patchTarget(patch) ?? Self.path(from: arguments)
            return (.activity(.write_file), name.map { tr("Editing \($0)", "编辑 \($0)") })

        case "update_plan", "update_todo", "set_plan":
            return (.activity(.thinking), tr("Updating the task list", "整理任务清单"))

        case "view_image", "read_image", "show_image":
            let name = Self.path(from: arguments)
            return (.activity(.view_image), name.map { tr("Viewing \($0)", "查看 \($0)") })

        case "web_search", "search_web", "browser_search":
            let query = (arguments["query"] as? String) ?? (arguments["q"] as? String)
            return (.activity(.read_web), query.map { tr("Searching the web: \($0)", "搜索网页 \($0)") })

        case "wait", "wait_agent", "write_stdin", "read_output", "kill_command", "sleep", "clock":
            // 等一条还在跑的命令／等另一个智能体：延续上一个动作，别切回敲键盘。
            return (.continuePrevious, nil)

        case "request_user_input_async", "request_user_input", "ask_user", "ask_user_question":
            return (.activity(.question_for_user),
                    PetQuestion.from(input: arguments)?.shortLabel ?? tr("Needs your answer", "等你回答"))

        case "spawn_agent", "followup_task", "interrupt_agent", "list_agents":
            let what = (arguments["task"] as? String) ?? (arguments["prompt"] as? String) ?? (arguments["name"] as? String)
            return (.activity(.thinking), what.map { tr("Delegating: \($0)", "委派：\($0)") }
                    ?? tr("Delegating to a helper", "委派助手"))

        default:
            break
        }

        // 带命名空间的工具（MCP 插件）：按名字里的关键字判断，和 Claude 版同一套规则。
        if let namespace, !namespace.isEmpty {
            let full = namespace.hasPrefix("mcp__") ? "\(namespace)__\(tool)" : "mcp__\(namespace)__\(tool)"
            let code = (arguments["code"] as? String) ?? ""
            let state = code.isEmpty ? ClaudeToolClassifier.classifyMCP(tool: full, input: arguments)
                                     : CodexExecScript.browserState(code)
            let title = (arguments["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
            return (.activity(state), title?.isEmpty == false ? title : ClaudeToolClassifier.describe(tool: full, input: arguments))
        }

        // 兜底：认 Claude 那套工具名（大小写与别名都认）。
        return (ClaudeToolClassifier.classify(tool: tool, input: arguments),
                ClaudeToolClassifier.describe(tool: tool, input: arguments))
    }

    /// `command` 可能是字符串，也可能是 `["bash", "-lc", "…"]` 这样的数组。
    static func command(from arguments: [String: Any]) -> String {
        for key in ["command", "cmd", "script"] {
            if let s = arguments[key] as? String { return s }
            if let words = arguments[key] as? [String] {
                // bash -lc "…"：真正的命令是最后那一段。
                if words.count >= 2, ["bash", "sh", "zsh"].contains((words[0] as NSString).lastPathComponent),
                   let last = words.last { return last }
                return words.joined(separator: " ")
            }
        }
        return ""
    }

    static func path(from arguments: [String: Any]) -> String? {
        for key in ["path", "file_path", "filepath", "file", "image_path"] {
            if let p = arguments[key] as? String, !p.isEmpty { return CodexExecScript.displayName(p) }
        }
        return nil
    }

    /// `request_user_input_async` 的第一个问题标题。
    static func question(from arguments: [String: Any]) -> String? {
        PetQuestion.from(input: arguments)?.shortLabel
    }

    /// 这次调用是不是在问你话；是就把问题抄下来。工具名按 Codex 那几种写法认。
    public static func question(tool: String, arguments: [String: Any]) -> PetQuestion? {
        let name = tool.lowercased()
        guard ["request_user_input_async", "request_user_input", "ask_user", "ask_user_question"].contains(name)
                || ClaudeToolClassifier.canonicalName(tool) == "AskUserQuestion" else { return nil }
        return PetQuestion.from(input: arguments)
    }
}

/// 桌面版 Codex 的 `exec` 工具：参数是一段 JS，调用 `tools.*` 做事。
/// 这里只从正文里认出「在干什么」，不执行、不保存正文。
public enum CodexExecScript {
    /// 认不出来时返回 nil，交给调用方按工具名兜底。
    public static func classify(_ script: String) -> (ToolClassification, String?)? {
        if script.contains("view_image") {
            let name = stringValue(key: "path", in: script).map(displayName)
            return (.activity(.view_image), name.map { tr("Viewing \($0)", "查看 \($0)") })
        }
        if script.contains("apply_patch") || script.contains("*** Begin Patch") {
            let name = patchTarget(script)
            return (.activity(.write_file), name.map { tr("Editing \($0)", "编辑 \($0)") } ?? tr("Editing a file", "修改文件"))
        }
        if script.contains("write_stdin") || script.contains("tools.wait(") || script.contains("read_output") {
            return (.continuePrevious, nil)
        }
        if script.contains("exec_command") {
            guard let command = stringValue(key: "cmd", in: script) else { return (.activity(.default_work), nil) }
            return (.activity(ClaudeToolClassifier.classifyShell(command)),
                    ClaudeToolClassifier.shellSummary(command).map { "$ \($0)" })
        }
        if script.contains("imagegen") || script.contains("image_gen") {
            return (.activity(.default_work), tr("Drawing a picture", "画图"))
        }
        // tools.<插件>__<工具>(…) 与 cua.*（操作浏览器和别的应用）。
        if let call = firstCall(in: script) {
            if call.hasPrefix("cua.") || script.contains("cua.") {
                return (.activity(browserState(script)), nil)
            }
            if call.contains("__") {
                let short = call.components(separatedBy: ".").last ?? call
                return (.activity(ClaudeToolClassifier.classifyMCP(tool: "mcp__\(short)", input: [:])), nil)
            }
        }
        return nil
    }

    /// 计算机操作／浏览器脚本：截图算看图，开标签页与读页面算看网页，其余算工作。
    public static func browserState(_ code: String) -> PetState {
        let lower = code.lowercased()
        if lower.contains("screenshot") || lower.contains("captureimage") { return .view_image }
        let webHints = ["browsertab", "browser", "navigate", "openurl", "gettabcontext", "readpage", "chrome"]
        if webHints.contains(where: lower.contains) { return .read_web }
        return .default_work
    }

    /// 补丁正文里改的是哪个文件。
    public static func patchTarget(_ patch: String) -> String? {
        for marker in ["*** Update File: ", "*** Add File: ", "*** Delete File: ", "*** Move to: "] {
            guard let r = patch.range(of: marker) else { continue }
            let rest = patch[r.upperBound...]
            let line = rest.prefix(while: { !$0.isNewline })
            let path = line.trimmingCharacters(in: .whitespaces)
                .replacingOccurrences(of: "\\n", with: "")
            if !path.isEmpty { return displayName(path) }
        }
        return nil
    }

    /// 路径 → 文件名（file:// 与百分号转义也认）。
    public static func displayName(_ path: String) -> String {
        var text = path
        if text.hasPrefix("file://") { text = String(text.dropFirst(7)) }
        text = text.removingPercentEncoding ?? text
        return (text as NSString).lastPathComponent
    }

    /// 正文里第一个 `xxx.yyy(` 形式的调用名。
    static func firstCall(in script: String) -> String? {
        var current = ""
        for ch in script {
            if ch.isLetter || ch.isNumber || ch == "_" || ch == "." || ch == "$" {
                current.append(ch)
            } else if ch == "(" {
                if current.contains("."), !current.hasPrefix("."), current.count > 2 { return current }
                current = ""
            } else {
                current = ""
            }
        }
        return nil
    }

    /// 从 JS 正文里取 `key: "值"`（`{cmd:"…"}` 与 `{"cmd":"…"}` 都认），处理转义。
    public static func stringValue(key: String, in script: String) -> String? {
        let chars = Array(script)
        let needle = Array(key)
        var i = 0
        while i + needle.count < chars.count {
            defer { i += 1 }
            guard Array(chars[i..<(i + needle.count)]) == needle else { continue }
            // 前一个字符是字母数字时，命中的是更长的名字（max_output_tokens 里的 token…）。
            if i > 0, chars[i - 1].isLetter || chars[i - 1].isNumber || chars[i - 1] == "_" { continue }
            var j = i + needle.count
            if j < chars.count, chars[j] == "\"" || chars[j] == "'" { j += 1 }
            while j < chars.count, chars[j] == " " { j += 1 }
            guard j < chars.count, chars[j] == ":" else { continue }
            j += 1
            while j < chars.count, chars[j] == " " { j += 1 }
            guard j < chars.count, "\"'`".contains(chars[j]) else { continue }
            return literal(chars, from: j)
        }
        return nil
    }

    /// 读一段 JS 字符串字面量，解掉常见转义。
    static func literal(_ chars: [Character], from start: Int) -> String {
        let quote = chars[start]
        var out = ""
        var i = start + 1
        while i < chars.count {
            let c = chars[i]
            if c == "\\", i + 1 < chars.count {
                let next = chars[i + 1]
                switch next {
                case "n": out.append("\n")
                case "t": out.append("\t")
                case "r": break
                case "u":
                    // \uXXXX：跳过，分类用不上。
                    i += 4
                default: out.append(next)
                }
                i += 2
                continue
            }
            if c == quote { return out }
            out.append(c)
            i += 1
        }
        return out
    }
}
