import Foundation

/// Only known providers and genuine, paired decision controls can produce a card.
/// Text that merely mentions approval, links, menus and ordinary Send buttons cannot.
public enum ApprovalSurface {
    public static func provider(url: String) -> String? {
        guard let u = URLComponents(string: url), u.user == nil, u.password == nil, u.port == nil else { return nil }
        if u.scheme == "https" {
            guard !u.path.hasPrefix("/artifact"), !u.path.hasPrefix("/share"), !u.path.hasPrefix("/public") else { return nil }
            switch u.host {
            case "chatgpt.com", "chat.openai.com": return "gpt"
            case "claude.ai": return "claude"
            case "chat.deepseek.com": return "deepseek"
            default: return nil
            }
        }
        if u.scheme == "chrome-extension" {
            switch u.host {
            case "hehggadaopoacecdllhhajmbjkdcmajg": return "gpt"
            case "fcoeoabgfenejglbffodgkkbkcdhcgfn": return "claude"
            default: return nil
            }
        }
        return nil
    }
    public static func decision(_ label: String) -> Bool? {
        let text = label.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if ["allow", "allow once", "allow this time", "approve", "approve once", "yes", "允许", "允许一次", "仅允许这一次", "批准", "同意", "是"].contains(text) { return true }
        if ["deny", "reject", "decline", "cancel", "no", "拒绝", "不允许", "取消", "否"].contains(text) { return false }
        return nil
    }
    public static func isRequest(text: String, buttons: [String]) -> Bool {
        guard text.utf8.count < 60000, text.count > 8, buttons.count >= 2, buttons.count <= 6,
              Set(buttons).count == buttons.count,
              buttons.contains(where: { decision($0) == true }), buttons.contains(where: { decision($0) == false }) else { return false }
        let value = text.lowercased()
        return ["approval", "permission", "allow", "approve", "run this command", "execute", "申请", "批准", "权限", "允许", "执行", "授权"].contains(where: { value.contains($0) })
    }
}
