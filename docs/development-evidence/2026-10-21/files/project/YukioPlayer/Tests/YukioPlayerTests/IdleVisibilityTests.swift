import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct IdleVisibilityTests {
    @Test func autoHideLifecycleUsesRealWindows() throws {
        _ = NSApplication.shared
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Resources/Assets")
        let catalog = try AnimationCatalog.load(assetsRoot: root)
        let library = try SpriteLibrary(catalog: catalog, assetsRoot: root)
        let suite = "local.yukio.idle-tests." + UUID().uuidString
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let controller = AppController(catalog: catalog, library: library, defaults: defaults)
        for (name, passed) in controller.idleVisibilityForCheck().sorted(by: { $0.key < $1.key }) {
            #expect(passed, "\(name)")
        }
    }

    @Test func settingsSwitchReflectsPreferenceAndEmitsChange() throws {
        _ = NSApplication.shared
        let controller = SettingsPanelController()
        defer { controller.close() }
        func find(_ view: NSView) -> NSSwitch? {
            if let toggle = view as? NSSwitch, toggle.accessibilityIdentifier() == "hideWhenIdleSwitch" { return toggle }
            return view.subviews.compactMap { find($0) }.first
        }
        var snapshot = SettingsSnapshot(status: "Idle", following: true, hidden: true,
            provider: .auto, chats: [], showBubble: true, showCards: true, showQuestionCard: true,
            scale: 1, language: .english, demoPlaying: false)
        controller.apply(snapshot)
        let root = try #require(controller.window?.contentView)
        let toggle = try #require(find(root))
        #expect(toggle.state == .on)
        snapshot.hideWhenIdle = false
        controller.apply(snapshot)
        #expect(toggle.state == .off)
        var received: Bool?
        controller.onChange = { if case .hideWhenIdle(let value) = $0 { received = value } }
        toggle.performClick(nil)
        #expect(received == true)
    }
}
