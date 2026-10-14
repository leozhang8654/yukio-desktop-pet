import Foundation

/// Decisions are explicit, single-use, and never inferred from arbitrary text.
public enum ApprovalQuestion {
    public static let allow = "允许这一次 / Allow once"
    public static let deny = "拒绝 / Deny"
    public static func make(provider: String, details: String) -> PetQuestion {
        var q = PetQuestion(header: "\(provider) · 等你批准 / Approval", text: details,
                            options: [.init(label: allow), .init(label: deny)])
        q.approval = true
        return q
    }
    public static func accepts(_ answer: String) -> Bool { answer == allow || answer == deny }
}
