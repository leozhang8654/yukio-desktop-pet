import Foundation

/// 从 AskUserQuestion（以及各家的同类工具）里抄下来的那道题。
///
/// 只抄问题本身与选项文字：举牌时原样显示在她身边，选项可以直接点。
/// 抄的是工具调用的参数，和其余说明文字一样只留在本机。
public struct PetQuestion: Codable, Equatable, Sendable {
    /// 一个选项：`label` 是送回去的答案，`detail` 是选项下面那行小字说明。
    public struct Option: Codable, Equatable, Sendable {
        public let label: String
        public let detail: String?

        public init(label: String, detail: String? = nil) {
            self.label = label
            self.detail = detail
        }
    }

    /// 问题的小标题（AskUserQuestion 的 header），没有时 nil。
    public let header: String?
    /// 问题正文。
    public let text: String
    public let options: [Option]
    /// 可以多选：送回去时把选中的几项用「、」连起来。
    public let multiSelect: Bool

    public init(header: String? = nil, text: String, options: [Option] = [], multiSelect: Bool = false) {
        self.header = header
        self.text = text
        self.options = options
        self.multiSelect = multiSelect
    }

    /// 气泡和卡片上那一行短说明：有小标题用小标题，否则截问题正文。
    public var shortLabel: String {
        let one = Self.oneLine(header?.isEmpty == false ? header! : text)
        return one.count > 40 ? String(one.prefix(40)) + "…" : one
    }

    /// 抄一道题下来。认得三种写法：
    /// - Claude 的 AskUserQuestion：`{"questions":[{"question":…,"header":…,"options":[{"label":…,"description":…}],"multiSelect":…}]}`
    /// - Codex 的 request_user_input：同样是 questions 数组，问题在 `title`，选项可能是字符串
    /// - 别家的简写：顶层直接 `question`／`prompt` 加 `options`
    ///
    /// 抄不到问题正文时返回 nil（调用方仍按“等你回答”处理，只是身边不立卡片）。
    public static func from(input: [String: Any]) -> PetQuestion? {
        if let questions = input["questions"] as? [[String: Any]], let first = questions.first {
            return from(one: first) ?? from(flat: input)
        }
        return from(one: input) ?? from(flat: input)
    }

    private static func from(one dict: [String: Any]) -> PetQuestion? {
        let text = string(dict["question"]) ?? string(dict["title"]) ?? string(dict["prompt"]) ?? string(dict["text"])
        guard let text else { return nil }
        let header = string(dict["header"]) ?? string(dict["label"])
        // 小标题和正文一样时只留正文，免得同一句话显示两遍。
        return PetQuestion(header: header == text ? nil : header,
                           text: oneLine(text),
                           options: options(dict["options"] ?? dict["choices"]),
                           multiSelect: (dict["multiSelect"] as? Bool) ?? (dict["multi_select"] as? Bool) ?? false)
    }

    /// 兜底：整个参数表就是一道题（没有 questions 数组也没认出正文）。
    private static func from(flat input: [String: Any]) -> PetQuestion? {
        guard let text = string(input["question"]) ?? string(input["prompt"]) else { return nil }
        return PetQuestion(header: string(input["header"]), text: oneLine(text),
                           options: options(input["options"] ?? input["choices"]),
                           multiSelect: (input["multiSelect"] as? Bool) ?? false)
    }

    static func options(_ value: Any?) -> [Option] {
        if let list = value as? [[String: Any]] {
            return list.compactMap { o in
                guard let label = string(o["label"]) ?? string(o["title"]) ?? string(o["value"]) ?? string(o["name"]) else { return nil }
                let detail = string(o["description"]) ?? string(o["detail"]) ?? string(o["hint"])
                return Option(label: oneLine(label), detail: detail.map(oneLine))
            }
        }
        if let list = value as? [String] {
            return list.compactMap { s in
                let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
                return t.isEmpty ? nil : Option(label: oneLine(t))
            }
        }
        return []
    }

    static func string(_ value: Any?) -> String? {
        guard let s = value as? String else { return nil }
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? nil : t
    }

    /// 折行换成空格：卡片自己会重新折行，原来的硬换行只会让排版难看。
    static func oneLine(_ s: String) -> String {
        s.split(whereSeparator: \.isNewline).map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }.joined(separator: " ")
    }
}
