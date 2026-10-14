import Foundation

/// Built-in skins have independent catalogs, so switching never mixes characters.
public enum PetSkin: String, CaseIterable, Sendable {
    case yukio
    case qianxia

    public func name(chinese: Bool) -> String {
        switch self {
        case .yukio: return chinese ? "雪绪" : "Yukio"
        case .qianxia: return chinese ? "千夏" : "Qianxia"
        }
    }

    public func assetsRoot(in root: URL) -> URL {
        self == .yukio ? root : root.appendingPathComponent("skins/\(rawValue)")
    }

    public static func identify(assetsRoot: URL) -> PetSkin {
        assetsRoot.deletingLastPathComponent().lastPathComponent == "skins"
            ? PetSkin(rawValue: assetsRoot.lastPathComponent) ?? .yukio : .yukio
    }
}
