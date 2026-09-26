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
    enum Outcome: Equatable {
        /// 已经替你按进去了。
        case typed
        /// 没有辅助功能权限：答案已复制，聊天也打开了，你按 ⌘V 回车。
        case needsPermission
        /// 那个应用没被带到最前面（或认不出那条聊天）：答案已复制。
        case copied
        /// 用户复制了新内容；保留它，不再粘贴旧答案。
        case clipboardChanged
    }

    /// Injected in tests: no real keystrokes, permission prompts or system clipboard.
    struct Environment {
        var pasteboard: NSPasteboard = .general
        var hasPermission: () -> Bool = { AXIsProcessTrusted() }
        var requestPermission: () -> Void = { requestPermissionOnce() }
        var frontmost: () -> String? = { NSWorkspace.shared.frontmostApplication?.bundleIdentifier }
        var pressKey: (CGKeyCode, CGEventFlags) -> Bool = { press($0, flags: $1) }
        var schedule: (Double, @escaping () -> Void) -> Void = { delay, work in
            DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: work)
        }
    }

    /// 本次运行内是否已经弹过一次系统权限面板：别每答一次弹一次。
    private static var askedForTrust = false

    static var hasPermission: Bool { AXIsProcessTrusted() }

    /// 送出。`bundleID` 是预期会跑到最前面的那个应用；`bringToFront` 通常是打开聊天的深链。
    /// 回调在主线程。
    static func send(_ answer: String, to bundleID: String?, bringToFront: @escaping () -> Void,
                     completion: @escaping (Outcome) -> Void, environment env: Environment = Environment()) {
        let text = answer.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        let previous = copy(text, to: env.pasteboard)
        let changeCount = env.pasteboard.changeCount
        bringToFront()

        guard let bundleID else {
            completion(.copied)
            return
        }
        guard env.hasPermission() else {
            env.requestPermission()
            completion(.needsPermission)
            return
        }
        waitForFront(bundleID, attempts: 25, environment: env) { ready in
            guard ready else {
                completion(.copied)
                return
            }
            // 窗口刚被带到前面，输入框还要一瞬间才接得住键。
            env.schedule(0.35) {
                // 再确认一次：这半秒里人可能又切走了，那就不按键。
                guard env.pasteboard.changeCount == changeCount else { completion(.clipboardChanged); return }
                guard env.frontmost() == bundleID else {
                    completion(.copied)
                    return
                }
                guard env.pressKey(keyV, .maskCommand) else { completion(.copied); return }
                env.schedule(0.18) {
                    guard env.pasteboard.changeCount == changeCount else { completion(.clipboardChanged); return }
                    guard env.frontmost() == bundleID,
                          env.pressKey(keyReturn, []) else { completion(.copied); return }
                    env.schedule(0.6) {
                        restore(previous, to: env.pasteboard, changeCount: changeCount)
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

    private static func copy(_ text: String, to pb: NSPasteboard = .general) -> [[NSPasteboard.PasteboardType: Data]] {
        let previous = (pb.pasteboardItems ?? []).map { item in
            Dictionary(uniqueKeysWithValues: item.types.compactMap { type in
                item.data(forType: type).map { (type, $0) }
            })
        }
        pb.clearContents()
        pb.setString(text, forType: .string)
        return previous
    }

    private static func restore(_ previous: [[NSPasteboard.PasteboardType: Data]],
                                to pb: NSPasteboard, changeCount: Int) {
        guard pb.changeCount == changeCount else { return }
        pb.clearContents()
        let items = previous.map { values in
            let item = NSPasteboardItem()
            for (type, data) in values { item.setData(data, forType: type) }
            return item
        }
        if !items.isEmpty { pb.writeObjects(items) }
    }

    private static func waitForFront(_ bundleID: String, attempts: Int, environment env: Environment,
                                     done: @escaping (Bool) -> Void) {
        if env.frontmost() == bundleID { done(true); return }
        guard attempts > 0 else { done(false); return }
        env.schedule(0.1) {
            waitForFront(bundleID, attempts: attempts - 1, environment: env, done: done)
        }
    }

    // MARK: 按键

    private static let keyV: CGKeyCode = 9
    private static let keyReturn: CGKeyCode = 36

    private static func press(_ code: CGKeyCode, flags: CGEventFlags = []) -> Bool {
        let source = CGEventSource(stateID: .hidSystemState)
        guard let down = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: true),
              let up = CGEvent(keyboardEventSource: source, virtualKey: code, keyDown: false) else { return false }
        down.flags = flags
        up.flags = flags
        down.post(tap: .cghidEventTap)
        up.post(tap: .cghidEventTap)
        return true
    }

    /// 弹一次系统的「辅助功能」面板（本次运行只弹一次）。
    private static func requestPermissionOnce() {
        guard !askedForTrust else { return }
        askedForTrust = true
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
    }
}
