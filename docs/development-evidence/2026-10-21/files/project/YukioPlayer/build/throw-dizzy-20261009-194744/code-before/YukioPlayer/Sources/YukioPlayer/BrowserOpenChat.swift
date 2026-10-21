import AppKit
import ApplicationServices
import YukioCore

/// Reads only document addresses in the foreground window. No page text, history,
/// cookies, tab activation, AppleScript permission, or browser debugging port.
enum BrowserOpenChat {
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

    static func read(processID: pid_t) -> [VisibleChat] {
        guard AXIsProcessTrusted() else { return [] }
        let app = AXUIElementCreateApplication(processID)
        AXUIElementSetMessagingTimeout(app, 0.15)
        guard let window = element(app, kAXFocusedWindowAttribute),
              value(window, kAXMinimizedAttribute) as? Bool != true else { return [] }
        let windowBounds = bounds(window)
        let deadline = ProcessInfo.processInfo.systemUptime + 0.35
        var queue: [(AXUIElement, Int)] = [(window, 0)]
        var cursor = 0
        var chats: [VisibleChat] = []
        while cursor < queue.count && cursor < 512 && ProcessInfo.processInfo.systemUptime < deadline {
            let (node, depth) = queue[cursor]
            cursor += 1
            if value(node, "AXHidden") as? Bool == true { continue }
            if let rect = bounds(node), let windowBounds,
               rect.isEmpty || !rect.intersects(windowBounds) { continue }
            let role = value(node, kAXRoleAttribute) as? String ?? ""
            if role == "AXWebArea" {
                let address = urlString(value(node, kAXURLAttribute))
                if let chat = VisibleChat(url: address) { chats.append(chat) }
                // Only extension wrappers may contain another chat document. Never
                // scan conversation links or messages inside an ordinary website.
                if !address.hasPrefix("chrome-extension://") { continue }
            } else if role == kAXWindowRole {
                if let chat = VisibleChat(url: urlString(value(node, kAXDocumentAttribute))) { chats.append(chat) }
            }
            // Tab/history/link trees cannot describe the currently open document.
            if ["AXLink", kAXToolbarRole, kAXMenuRole, kAXTabGroupRole].contains(role) { continue }
            guard depth < 20, let children = value(node, kAXChildrenAttribute) as? [AXUIElement] else { continue }
            guard queue.count + children.count <= 512 else { return [] }
            queue.append(contentsOf: children.map { ($0, depth + 1) })
        }
        // An incomplete or slow read cannot acknowledge an unseen completion.
        guard cursor >= queue.count, ProcessInfo.processInfo.systemUptime < deadline,
              let current = element(app, kAXFocusedWindowAttribute), CFEqual(window, current) else { return [] }
        return chats
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
