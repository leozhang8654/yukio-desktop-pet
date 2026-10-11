import AppKit
import ApplicationServices
import YukioCore

/// Reads on-screen document addresses and the official GPT selected-chat header.
/// Never reads message bodies, cookies, history or activates browser tabs.
enum BrowserOpenChat {
    static var notes: [String] = []
    static let supportedBundles: Set<String> = [
        "com.google.Chrome", "com.google.Chrome.beta", "com.google.Chrome.dev", "com.google.Chrome.canary",
        "org.chromium.Chromium", "com.microsoft.edgemac", "com.brave.Browser", "company.thebrowser.Browser",
        "com.apple.Safari", "com.openai.chat", "com.openai.codex", "com.anthropic.claudefordesktop",
    ]

    static var hasAccessibilityAccess: Bool { AXIsProcessTrusted() }

    static func openPermissionSettings() {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        _ = AXIsProcessTrustedWithOptions(options)
        if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
            NSWorkspace.shared.open(url)
        }
    }

    struct Window: Equatable {
        let id: Int
        let pid: pid_t
        let bounds: CGRect
        let layer: Int
    }
    struct Snapshot {
        let windows: [Window]
        let screens: [CGRect]
        static func capture() -> Snapshot {
            let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
            let windows = list.compactMap { row -> Window? in
                guard let id = row[kCGWindowNumber as String] as? Int,
                      let pid = row[kCGWindowOwnerPID as String] as? Int32,
                      let layer = row[kCGWindowLayer as String] as? Int,
                      let raw = row[kCGWindowBounds as String] as? [String: Any],
                      let bounds = CGRect(dictionaryRepresentation: raw as CFDictionary),
                      (row[kCGWindowAlpha as String] as? Double ?? 1) > 0.05,
                      pid != ProcessInfo.processInfo.processIdentifier else { return nil }
                return Window(id: id, pid: pid, bounds: bounds, layer: layer)
            }
            var ids = [CGDirectDisplayID](repeating: 0, count: 32)
            var count: UInt32 = 0
            CGGetActiveDisplayList(32, &ids, &count)
            return Snapshot(windows: windows, screens: ids.prefix(Int(count)).map(CGDisplayBounds))
        }
        func readable(_ rect: CGRect, in window: Window) -> Bool {
            guard let index = windows.firstIndex(of: window) else { return false }
            let covers = windows[..<index].map(\.bounds)
            return ChatWindowVisibility.canRead(rect.intersection(window.bounds), screens: screens, covers: covers)
        }
        func mainWindows(pid: pid_t) -> [Window] {
            windows.filter { $0.pid == pid && $0.layer == 0 && $0.bounds.width >= 160 && $0.bounds.height >= 120 }
        }
        func visibleSingleWindow(pid: pid_t) -> Bool {
            let main = mainWindows(pid: pid)
            guard main.count == 1, let window = main.first else { return false }
            return readable(window.bounds.insetBy(dx: 40, dy: 70), in: window)
        }
    }

    static func read(processID: pid_t) -> [VisibleChat] {
        read(processID: processID, snapshot: .capture())
    }

    static func read(processID: pid_t, snapshot: Snapshot, nativeGPT: Bool = false, gptTitles: [(id: String, title: String?)] = []) -> [VisibleChat] {
        guard hasAccessibilityAccess else { return [] }
        notes.append("read pid=\(processID) osWindows=\(snapshot.mainWindows(pid: processID).count)")
        let app = AXUIElementCreateApplication(processID)
        AXUIElementSetMessagingTimeout(app, 0.1)
        guard let windows = value(app, kAXWindowsAttribute) as? [AXUIElement] else { return [] }
        notes.append("axWindows=\(windows.count)")
        var chats: [VisibleChat] = []
        for window in windows {
            guard value(window, kAXMinimizedAttribute) as? Bool != true,
                  let rect = bounds(window) else { continue }
            let matches = snapshot.mainWindows(pid: processID).filter { equivalent($0.bounds, rect) }
            notes.append("axFrame=\(rect) matches=\(matches.count)")
            guard matches.count == 1, let onScreen = matches.first,
                  snapshot.readable(rect.insetBy(dx: 20, dy: 50), in: onScreen) else { continue }
            chats += documents(in: window, onScreen: onScreen, snapshot: snapshot, nativeGPT: nativeGPT, gptTitles: gptTitles)
        }
        // Window moves, tab changes are checked again at the next poll. Never use
        // a result after a window has vanished, moved or been covered meanwhile.
        guard Snapshot.capture().windows == snapshot.windows else { return [] }
        return chats
    }

    private static func documents(in window: AXUIElement, onScreen: Window, snapshot: Snapshot, nativeGPT: Bool, gptTitles: [(id: String, title: String?)]) -> [VisibleChat] {
        let deadline = ProcessInfo.processInfo.systemUptime + 0.8
        var queue: [(AXUIElement, Int)] = [(window, 0)]
        var cursor = 0
        var chats: [VisibleChat] = []
        while cursor < queue.count && cursor < 1024 && ProcessInfo.processInfo.systemUptime < deadline {
            let (node, depth) = queue[cursor]
            cursor += 1
            if value(node, "AXHidden") as? Bool == true { continue }
            let role = value(node, kAXRoleAttribute) as? String ?? ""
            if role == "AXWebArea" {
                let address = urlString(value(node, kAXURLAttribute))
                notes.append("document=\(address) frame=\(String(describing: bounds(node)))")
                if nativeGPT, address.hasPrefix("app://-/"),
                   let rect = bounds(node), snapshot.readable(rect, in: onScreen),
                   let title = value(node, kAXTitleAttribute) as? String,
                   let id = VisibleChatTitle.session(header: title, candidates: gptTitles),
                   let chat = VisibleChat(url: "codex://threads/" + id) {
                    chats.append(chat)
                }
                if let rect = bounds(node), snapshot.readable(rect, in: onScreen),
                   let chat = VisibleChat(url: address) { chats.append(chat) }
                if address == "chrome-extension://hehggadaopoacecdllhhajmbjkdcmajg/codex-sidepanel/index.html",
                   let rect = bounds(node), snapshot.readable(rect, in: onScreen),
                   let header = sidePanelHeader(node),
                   let id = VisibleChatTitle.session(header: header, candidates: gptTitles),
                   let chat = VisibleChat(url: "codex://threads/" + id) {
                    chats.append(chat)
                    continue
                }
                if !address.hasPrefix("chrome-extension://") { continue }
            } else if role == kAXWindowRole {
                if let chat = VisibleChat(url: urlString(value(node, kAXDocumentAttribute))) { chats.append(chat) }
            }
            if ["AXLink", kAXToolbarRole, kAXMenuRole, kAXTabGroupRole].contains(role) { continue }
            // Layout containers can have a zero frame even when children are visible.
            guard depth < 30, let children = value(node, kAXChildrenAttribute) as? [AXUIElement] else { continue }
            guard queue.count + children.count <= 1024 else { return [] }
            queue.append(contentsOf: children.map { ($0, depth + 1) })
        }
        notes.append("scan visited=\(cursor)/\(queue.count) found=\(chats.count) timedOut=\(ProcessInfo.processInfo.systemUptime >= deadline)")
        guard cursor >= queue.count, ProcessInfo.processInfo.systemUptime < deadline else { return [] }
        return chats
    }

    /// Only the first row of the official panel. Never traverse message contents,
    /// recent-chat menus or arbitrary buttons whose text happens to match a title.
    private static func sidePanelHeader(_ root: AXUIElement) -> String? {
        selectedHeader(root, children: { value($0, kAXChildrenAttribute) as? [AXUIElement] ?? [] },
            role: { value($0, kAXRoleAttribute) as? String ?? "" }, label: { item in
                for key in [kAXTitleAttribute, kAXDescriptionAttribute] {
                    if let text = value(item, key) as? String, !text.isEmpty { return text }
                }
                return ""
            })
    }

    // Chromium exposes anonymous layout groups omitted by some UI inspectors.
    // Follow only the leading group chain, stopping at the first button row;
    // never search later siblings (messages, recent-chat lists or menus).
    static func selectedHeader<Node>(_ root: Node, children: (Node) -> [Node],
                                     role: (Node) -> String, label: (Node) -> String) -> String? {
        var node = root
        for _ in 0..<16 {
            let items = children(node)
            let buttons = items.filter { role($0) == kAXButtonRole }
            if !buttons.isEmpty {
                guard buttons.count >= 3,
                      label(buttons[0]) == "New chat", label(buttons[2]) == "More actions" else { return nil }
                return label(buttons[1])
            }
            guard let next = items.first(where: { role($0) == kAXGroupRole }) else { return nil }
            node = next
        }
        return nil
    }

    private static func equivalent(_ a: CGRect, _ b: CGRect) -> Bool {
        abs(a.minX - b.minX) < 2 && abs(a.minY - b.minY) < 2 && abs(a.width - b.width) < 2 && abs(a.height - b.height) < 2
    }

    private static func bounds(_ node: AXUIElement) -> CGRect? {
        guard let position = value(node, kAXPositionAttribute), CFGetTypeID(position) == AXValueGetTypeID(),
              let size = value(node, kAXSizeAttribute), CFGetTypeID(size) == AXValueGetTypeID() else { return nil }
        var point = CGPoint.zero
        var dimensions = CGSize.zero
        guard AXValueGetValue(position as! AXValue, .cgPoint, &point),
              AXValueGetValue(size as! AXValue, .cgSize, &dimensions) else { return nil }
        return CGRect(origin: point, size: dimensions)
    }

    private static func value(_ element: AXUIElement, _ key: String) -> CFTypeRef? {
        var result: CFTypeRef?
        guard AXUIElementCopyAttributeValue(element, key as CFString, &result) == .success else { return nil }
        return result
    }

    private static func element(_ parent: AXUIElement, _ key: String) -> AXUIElement? {
        guard let result = value(parent, key), CFGetTypeID(result) == AXUIElementGetTypeID() else { return nil }
        return (result as! AXUIElement)
    }

    private static func urlString(_ value: CFTypeRef?) -> String {
        if let url = value as? URL { return url.absoluteString }
        return value as? String ?? ""
    }
}
