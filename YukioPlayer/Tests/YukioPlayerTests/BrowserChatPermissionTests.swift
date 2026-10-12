import AppKit
import Testing
@testable import YukioPlayer

@Suite @MainActor struct BrowserChatPermissionTests {
    @Test func browserPermissionButtonRequiresAnExplicitClick() throws {
        _ = NSApplication.shared
        let controller = SettingsPanelController()
        defer { controller.close() }
        func find(_ view: NSView) -> NSButton? {
            if let button = view as? NSButton, button.accessibilityIdentifier() == "browserChatPermissionButton" { return button }
            return view.subviews.compactMap { find($0) }.first
        }
        let root = try #require(controller.window?.contentView)
        let button = try #require(find(root))
        var requests = 0
        controller.onChange = { if case .browserChatPermission = $0 { requests += 1 } }
        #expect(requests == 0)
        button.performClick(nil)
        #expect(requests == 1)
    }

}
