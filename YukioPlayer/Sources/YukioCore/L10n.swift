import Foundation

/// 界面语言。默认英文；菜单「Language」里可切到中文，选择存在设置里。
/// 已经写进事件里的说明文字（如 “Reading main.swift”）不回溯翻译，下一条事件起换语言。
public enum UILanguage: String, CaseIterable, Sendable {
    case english = "en"
    case chinese = "zh"

    /// 设置里存的值、或环境变量 YUKIO_LANG（命令行渲染用）→ 语言；认不出就英文。
    public init(code: String?) {
        self = code?.lowercased().hasPrefix("zh") == true ? .chinese : .english
    }
}

public enum L10n {
    private static let lock = NSLock()
    private static var current = UILanguage(code: ProcessInfo.processInfo.environment["YUKIO_LANG"])

    /// 当前界面语言。主线程改、解析线程读，所以加锁。
    public static var language: UILanguage {
        get { lock.withLock { current } }
        set { lock.withLock { current = newValue } }
    }

    /// 菜单第一行与工具提示里的状态名（不是气泡文字）。
    public static func stateName(_ state: PetState) -> String {
        switch state {
        case .thinking: return tr("Thinking", "思考")
        case .read_file: return tr("Reading a file", "读文件")
        case .view_image: return tr("Viewing an image", "看图片")
        case .write_file: return tr("Editing a file", "写文件")
        case .verify: return tr("Running tests", "跑测试")
        case .read_web: return tr("Browsing the web", "看网页")
        case .respond: return tr("Handing in the answer", "递交回答")
        case .task_complete: return tr("Holding the done card", "举着勾选卡")
        case .question_for_user: return tr("Holding the question card", "立着问号卡")
        case .default_work: return tr("Working", "敲键盘")
        case .failed: return tr("Failed", "沮丧")
        case .idle: return tr("Idle", "空闲")
        }
    }

    /// 被大手拎着时的状态名。
    public static var heldName: String { tr("Picked up", "被大手拎着") }
}

/// 英文在前、中文在后，按当前界面语言取一个。
public func tr(_ en: String, _ zh: String) -> String {
    L10n.language == .chinese ? zh : en
}

/// 指定语言取（测试与命令行用）。
public func tr(_ en: String, _ zh: String, in language: UILanguage) -> String {
    language == .chinese ? zh : en
}
