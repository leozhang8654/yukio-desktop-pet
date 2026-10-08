import AppKit
import Testing
@testable import YukioPlayer

@Suite @MainActor struct SoftwareUpdateSettingsTests {
    @Test func updateControlsSendDistinctActionsAndFitInsideSettings() throws {
        _ = NSApplication.shared
        let panel = SettingsPanelController()
        defer { panel.close() }
        let root = try #require(panel.window?.contentView)
        root.layoutSubtreeIfNeeded()
        func find(_ id: String, in view: NSView) -> NSView? {
            if view.accessibilityIdentifier() == id { return view }
            return view.subviews.compactMap { find(id, in: $0) }.first
        }
        let stack = try #require(find("settingsContentStack", in: root))
        #expect(root.bounds.contains(stack.convert(stack.bounds, to: root)))
        let button = try #require(find("checkForUpdatesButton", in: root) as? NSButton)
        let toggle = try #require(find("automaticUpdatesSwitch", in: root) as? NSSwitch)
        var checks = 0
        var preference: Bool?
        panel.onChange = { change in
            switch change {
            case .checkForUpdates: checks += 1
            case .automaticUpdates(let enabled): preference = enabled
            default: break
            }
        }
        button.performClick(nil)
        #expect(checks == 1)
        toggle.state = .off
        _ = toggle.sendAction(toggle.action, to: toggle.target)
        #expect(preference == false)
        for control in [button as NSView, toggle as NSView] {
            let rect = control.convert(control.bounds, to: root)
            #expect(root.bounds.contains(rect))
        }
    }
}
