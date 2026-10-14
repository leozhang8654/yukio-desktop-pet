import AppKit
import ApplicationServices

/// In-memory destinations learned only from an identified official side panel.
/// Keep the browser's own tab element, never substitute a Codex desktop deep link.
enum BrowserChatDestination {
    private struct Target {
        let pid: pid_t
        let window: AXUIElement
        let tab: AXUIElement
        let title: String
    }
    private static let lock = NSLock()
    private static var targets: [String: Target] = [:]

    static func contains(_ session: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return targets[session] != nil
    }

    static func remember(session: String, window: AXUIElement, processID: pid_t) {
        let selected = tabs(window).filter { (value($0, kAXValueAttribute) as? NSNumber)?.boolValue == true }
        guard selected.count == 1, let tab = selected.first,
              let title = value(tab, kAXTitleAttribute) as? String, !title.isEmpty else { return }
        lock.lock(); defer { lock.unlock() }
        targets[session] = Target(pid: processID, window: window, tab: tab, title: normalizedTitle(title))
    }

    /// The exact observed tab must still belong to that window. Closed/replaced
    /// tabs and unavailable accessibility never redirect to an unrelated app.
    static func open(session: String) -> Bool {
        lock.lock(); let target = targets[session]; lock.unlock()
        guard let target, let app = NSRunningApplication(processIdentifier: target.pid),
              !app.isTerminated,
              tabs(target.window).contains(where: { CFEqual($0, target.tab) }),
              let title = value(target.tab, kAXTitleAttribute) as? String,
              normalizedTitle(title) == target.title else { return false }
        guard AXUIElementPerformAction(target.tab, kAXPressAction as CFString) == .success else { return false }
        guard AXUIElementPerformAction(target.window, kAXRaiseAction as CFString) == .success else { return false }
        return app.activate(options: [.activateIgnoringOtherApps])
    }

    static func normalizedTitle(_ text: String) -> String {
        // Chrome adds changing memory usage to the tab's accessibility label.
        text.replacingOccurrences(of: #" - (?:内存用量|Memory usage).*?$"#, with: "", options: .regularExpression)
    }

    private static func tabs(_ root: AXUIElement) -> [AXUIElement] {
        var queue = [(root, false)], cursor = 0
        var found: [AXUIElement] = []
        while cursor < queue.count && cursor < 512 {
            let (node, inTabs) = queue[cursor]; cursor += 1
            let role = value(node, kAXRoleAttribute) as? String ?? ""
            if role == "AXWebArea" || role == kAXToolbarRole || role == kAXMenuRole { continue }
            if inTabs && ["AXRadioButton", "AXTab", "AXButton"].contains(role) {
                found.append(node); continue
            }
            let children = value(node, kAXChildrenAttribute) as? [AXUIElement] ?? []
            guard queue.count + children.count <= 512 else { return [] }
            queue += children.map { ($0, inTabs || role == kAXTabGroupRole) }
        }
        return cursor == queue.count ? found : []
    }

    private static func value(_ node: AXUIElement, _ key: String) -> CFTypeRef? {
        var output: CFTypeRef?
        guard AXUIElementCopyAttributeValue(node, key as CFString, &output) == .success else { return nil }
        return output
    }
}
