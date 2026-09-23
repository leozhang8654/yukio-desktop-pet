import Foundation

/// 跟随哪个助手。三家在本机各写各的会话记录，格式不同，各有一个来源实现（见 LiveSources）。
///
/// 菜单「Assistant／跟随的助手」里切换，存在设置键 `source` 里（Windows 版用同一个键名）。
public enum AgentProvider: String, CaseIterable, Sendable {
    /// 三家都跟：谁有动静就跟谁（多条聊天之间的挑选规则见 ActivityRouter.updateFocus）。
    case auto
    case claude
    case deepseek
    case gpt

    /// 设置里存的值 → 枚举；认不出就 auto。旧设置与别名（codex、deepcode…）也认。
    public init(code: String?) {
        let key = (code ?? "").trimmingCharacters(in: .whitespaces).lowercased()
        self = AgentProvider(rawValue: key) ?? Self.aliases[key] ?? .auto
    }

    private static let aliases: [String: AgentProvider] = [
        "claude-code": .claude, "claudecode": .claude, "anthropic": .claude, "claude-transcript": .claude,
        "deepcode": .deepseek, "deep-code": .deepseek, "deep_code": .deepseek,
        "codex": .gpt, "openai": .gpt, "chatgpt": .gpt, "openai-codex": .gpt,
    ]

    /// 菜单里的名字。
    public var displayName: String {
        switch self {
        case .auto: return tr("Auto (whoever is working)", "自动（谁在干活跟谁）")
        case .claude: return tr("Claude Code", "Claude Code")
        case .deepseek: return tr("DeepSeek (Deep Code)", "DeepSeek（Deep Code）")
        case .gpt: return tr("GPT (Codex)", "GPT（Codex）")
        }
    }

    /// 这个选择要跟的事件来源标识（PetEvent.source）。auto 是全部。
    public var sourceIDs: Set<String> {
        switch self {
        case .auto: return [ClaudeTranscriptParser.source, ClaudeHookParser.source,
                            DeepCodeMessageParser.source, CodexRolloutParser.source]
        case .claude: return [ClaudeTranscriptParser.source, ClaudeHookParser.source]
        case .deepseek: return [DeepCodeMessageParser.source]
        case .gpt: return [CodexRolloutParser.source]
        }
    }

    /// 这个来源标识属于哪一家（举牌点击要按家分路：只有 Claude 有桌面版深链）。
    public static func owner(ofSource source: String) -> AgentProvider? {
        for p in [AgentProvider.claude, .deepseek, .gpt] where p.sourceIDs.contains(source) { return p }
        return nil
    }
}
