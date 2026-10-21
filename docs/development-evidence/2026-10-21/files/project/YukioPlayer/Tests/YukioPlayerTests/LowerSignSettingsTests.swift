import AppKit
import Testing
@testable import YukioPlayer

@Suite @MainActor struct LowerSignSettingsTests {
    @Test func largeIconButtonEmitsOnlyLowerSign() throws {
        _ = NSApplication.shared
        let controller = SettingsPanelController()
        defer { controller.close() }
        func find(_ view: NSView) -> NSButton? {
            if let button = view as? NSButton, button.accessibilityIdentifier() == "lowerSignButton" { return button }
            return view.subviews.compactMap { find($0) }.first
        }
        let root = try #require(controller.window?.contentView)
        root.layoutSubtreeIfNeeded()
        let button = try #require(find(root))
        #expect(button.image != nil)
        #expect(button.frame.height >= 64)
        var lowerCount = 0
        var otherCount = 0
        controller.onChange = { change in
            if case .lowerSign = change { lowerCount += 1 }
            else { otherCount += 1 }
        }
        button.performClick(nil)
        button.performClick(nil)
        #expect(lowerCount == 2)
        #expect(otherCount == 0)
    }
}
