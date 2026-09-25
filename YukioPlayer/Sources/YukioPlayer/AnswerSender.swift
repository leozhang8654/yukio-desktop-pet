import AppKit
import ApplicationServices

/// 把你在雪绪这边写下的回答送进那条聊天里。
///
/// 做法就是替你按键：先用深链把那家的桌面版带到最前面，确认最前面的确实是它，
/// 再按 ⌘V 把答案粘进输入框、按一下回车。粘贴板会原样放回去。
///
/// 这需要系统的「辅助功能」权限（第一次会弹系统面板让你勾选）。没有权限、
/// 或者那个应用没被带到前面时，只把答案复制到粘贴板并打开聊天，你自己 ⌘V ——
/// 绝不会往别的应用里乱按键：最前面的应用不是预期的那个就立刻收手。
enum AnswerSender {
    enum Outcome {
        /// 已经替你按进去了。
        case typed
        /// 没有辅助功能权限：答案已复制，聊天也打开了，你按 ⌘V 回车。
        case needsPermission
        /// 那个应用没被带到最前面（或认不出那条聊天）：答案已复制。
        case copied
    }

    /// 本次运行内是否已经弹过一次系统权限面板：别每答一次弹一次。
    private static var askedForTrust = false

    static var hasPermission: Bool { AXIsProcessTrusted() }

    /// 送出。`bundleID` 是预期会跑到最前面的那个应用；`bringToFront` 通常是打开聊天的深链。
    /// 回调在主线程。
    static func send(_ answer: String, to bundleID: String?, bringToFront: @escaping () -> Void,
                     completion: @escaping (Outcome) -> Void) {
        let text = answer.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        let previous = copy(text)
        bringToFront()

        guard hasPermission else {
            requestPermissionOnce()
            completion(.needsPermission)
            return
        }
        guard let bundleID else {
            completion(.copied)
            return
        }
        waitForFront(bundleID, deadline: Date().addingTimeInterval(2.5)) { ready in
            guard ready else {
                restore(previous, ifStillOurs: text)
                completion(.copied)
                return
            }
            // 窗口刚被带到前面，输入框还要一瞬间才接得住键。
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                // 再确认一次：这半秒里人可能又切走了，那就不按键。
                guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier == bundleID else {
                    restore(previous, ifStillOurs: text)
                    completion(.copied)
                    return
                }
                press(keyV, flags: .maskCommand)
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
                    press(keyReturn)
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                        restore(previous, ifStillOurs: text)
                    }
                    completion(.typed)
                }
            }
        }
    }

    /// 只复制，不按键（没有聊天可跳时用）。
    @discardableResult
    static func copyOnly(_ answer: String) -> Bool {
        _ = copy(answer)
        return true
    }

    // MARK: 粘贴板

    /// 把答案放进粘贴板，返回原来那份纯文本（放回去用；原来不是文本时 nil）。
    private static func copy(_ text: String) -> String? {
        let pb = NSPasteboard.general
        let previous = pb.string(forType: .string)
        pb.clearContents()
        pb.setString(text, forType: .string)
        return previous
    }

    /// 放回原来的粘贴板内容——但只在里面还是我们刚放进去那份答案时放，
    /// 免得把你这会儿新复制的东西冲掉。
    private static func restore(_ previous: String?, ifStillOurs answer: String) {
        let pb = NSPasteboard.general
        guard pb.string(forType: .string) == answer else { return }
        pb.clearContents()
        if let previous { pb.setString(previous, forType: .string) }
    }

    // MARK: 等它到最前面

    private static func waitForFront(_ bundleID: String, deadline: Date, done: @escaping (Bool) -> Void) {
        if NSWorkspace.shared.frontmostApplication?.bundleIdentifier == bundleID {
            done(true)
            return
        }
        guard Date() < deadline else {
            done(false)
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            waitForFront(bundleID, deadline: deadline, done: done)
        }
    }

    // MARK: 按键

    private static let keyV: CGKeyCode = 9
    private static let keyReturn: CGKeyCode = 36

    private static func press(_ code: CGKeyCode, flags: CGEventFlags = []) {
        let source = CGEventSource(stateID: .hidSystemState)
        guard let down = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: true),
              let up = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: false) else { return }
        down.flags = flags
        up.flags = flags
        down.post(tap: .cghidEventTap)
        up.post(tap: .cghidEventTap)
    }

    /// 弹一次系统的「辅助功能」面板（本次运行只弹一次）。
    private static func requestPermissionOnce() {
        guard !askedForTrust else { return }
        askedForTrust = true
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
    }
}
