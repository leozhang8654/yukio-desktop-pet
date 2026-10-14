import AppKit
import ApplicationServices

/// In-memory destinations learned only from an identified official side panel.
/// Keep the browser's own tab element, never substitute a Codex desktop deep link.
enum BrowserChatDestination {
    private struct Target {
        let pid: pid_t
        let window: AXUIElement
        let tabWindow: AXUIElement
        let tab: AXUIElement
        let title: String
    }
    private static let lock = NSLock()
    private static var targets: [String: Target] = [:]

    static var sessions: [String] {
        lock.lock(); defer { lock.unlock() }
        return targets.keys.sorted()
    }

    static func contains(_ session: String) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return targets[session] != nil
    }

    static func remember(session: String, window: AXUIElement, processID: pid_t) {
        var owners = [window]
        // Chrome can expose its full-screen tab strip as a separate AX window.
        // Only accept a strip touching the same content window, never another
        // browser window or another display's selected tab.
        if tabs(window).isEmpty, let content = bounds(window) {
            let app = AXUIElementCreateApplication(processID)
            let siblings = value(app, kAXWindowsAttribute) as? [AXUIElement] ?? []
            owners += siblings.filter { sibling in
                guard !CFEqual(sibling, window), let frame = bounds(sibling) else { return false }
                return isAttachedTabStrip(frame, content: content)
            }
        }
        let selected = owners.flatMap { owner in
            tabs(owner).filter { (value($0, kAXValueAttribute) as? NSNumber)?.boolValue == true }
                .map { (owner, $0) }
        }
        BrowserOpenChat.notes.append("browserTabOwners=\(owners.count) selectedTabs=\(selected.count)")
        guard selected.count == 1, let (owner, tab) = selected.first,
              let title = tabTitle(tab) else { return }
        lock.lock(); defer { lock.unlock() }
        targets[session] = Target(pid: processID, window: window, tabWindow: owner, tab: tab, title: normalizedTitle(title))
    }

    /// The exact observed tab must still belong to that window. Closed/replaced
    /// tabs and unavailable accessibility never redirect to an unrelated app.
    static func open(session: String) -> Bool {
        lock.lock(); let target = targets[session]; lock.unlock()
        guard let target, let app = NSRunningApplication(processIdentifier: target.pid),
              !app.isTerminated,
              tabs(target.tabWindow).contains(where: { CFEqual($0, target.tab) }),
              let title = tabTitle(target.tab),
              normalizedTitle(title) == target.title else { return false }
        guard AXUIElementPerformAction(target.tab, kAXPressAction as CFString) == .success else { return false }
        guard AXUIElementPerformAction(target.window, kAXRaiseAction as CFString) == .success else { return false }
        return app.activate(options: [.activateIgnoringOtherApps])
    }

    static func normalizedTitle(_ text: String) -> String {
        // Chrome adds changing memory usage to the tab's accessibility label.
        text.replacingOccurrences(of: #" - (?:内存用量|Memory usage).*?$"#, with: "", options: .regularExpression)
    }

    static func isAttachedTabStrip(_ strip: CGRect, content: CGRect) -> Bool {
        abs(strip.minX - content.minX) <= 2 && abs(strip.width - content.width) <= 2
            && strip.height >= 20 && strip.height <= 100
            && strip.maxY <= content.minY + 2 && content.minY - strip.maxY <= 60
    }

    private static func tabTitle(_ tab: AXUIElement) -> String? {
        // Chromium exposes some tab labels as AXDescription, leaving AXTitle empty.
        for key in [kAXTitleAttribute, kAXDescriptionAttribute] {
            if let title = value(tab, key) as? String, !title.isEmpty { return title }
        }
        return nil
    }

    private static func bounds(_ node: AXUIElement) -> CGRect? {
        guard let position = value(node, kAXPositionAttribute), let size = value(node, kAXSizeAttribute),
              CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(size) == AXValueGetTypeID() else { return nil }
        var point = CGPoint.zero, extent = CGSize.zero
        guard AXValueGetValue(position as! AXValue, .cgPoint, &point),
              AXValueGetValue(size as! AXValue, .cgSize, &extent) else { return nil }
        return CGRect(origin: point, size: extent)
    }

    private static func tabs(_ root: AXUIElement) -> [AXUIElement] {
        collectTabs(root, children: { value($0, kAXChildrenAttribute) as? [AXUIElement] ?? [] },
                    role: { value($0, kAXRoleAttribute) as? String ?? "" },
                    same: { CFEqual($0, $1) })
    }

    static func collectTabs<Node>(_ root: Node, children: (Node) -> [Node],
                                  role: (Node) -> String, same: (Node, Node) -> Bool) -> [Node] {
        var queue = [(root, false)], cursor = 0
        var found: [Node] = [], visited: [Node] = []
        while cursor < queue.count && cursor < 512 {
            let (node, inTabs) = queue[cursor]; cursor += 1
            // Chrome's full-screen accessibility graph can reference the same
            // tab strip through several containers. It is not necessarily a tree.
            guard !visited.contains(where: { same($0, node) }) else { continue }
            visited.append(node)
            let kind = role(node)
            if kind == "AXWebArea" || kind == kAXToolbarRole || kind == kAXMenuRole { continue }
            if inTabs && ["AXRadioButton", "AXTab", "AXButton"].contains(kind) {
                found.append(node); continue
            }
            let items = children(node)
            guard queue.count + items.count <= 512 else { return [] }
            queue += items.map { ($0, inTabs || kind == kAXTabGroupRole) }
        }
        return cursor == queue.count ? found : []
    }

    private static func value(_ node: AXUIElement, _ key: String) -> CFTypeRef? {
        var output: CFTypeRef?
        guard AXUIElementCopyAttributeValue(node, key as CFString, &output) == .success else { return nil }
        return output
    }
}
