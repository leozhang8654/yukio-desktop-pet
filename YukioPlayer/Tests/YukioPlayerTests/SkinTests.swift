import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct SkinTests {
    static var root: URL {
        URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("Resources/Assets")
    }

    @Test func switchPreservesActivityAndSettings() throws {
        _ = NSApplication.shared
        let catalog = try AnimationCatalog.load(assetsRoot: Self.root)
        let library = try SpriteLibrary(catalog: catalog, assetsRoot: Self.root)
        let suite = "local.yukio.skin-tests." + UUID().uuidString
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let controller = AppController(catalog: catalog, library: library, defaults: defaults, bundledAssets: Self.root)
        for (name, passed) in try controller.skinSwitchForCheck() {
            #expect(passed, "\(name)")
        }
    }

    @Test func settingsSelectsBothSkinsAndEmitsChoice() throws {
        _ = NSApplication.shared
        let controller = SettingsPanelController()
        defer { controller.close() }
        var snapshot = SettingsSnapshot(status: "Idle", following: true, hidden: false,
            provider: .auto, chats: [], showBubble: true, showCards: true, showQuestionCard: true,
            scale: 1, language: .english, demoPlaying: false)
        controller.apply(snapshot)
        func find(_ view: NSView) -> NSPopUpButton? {
            if let popup = view as? NSPopUpButton, popup.accessibilityIdentifier() == "skinPopup" { return popup }
            return view.subviews.compactMap { find($0) }.first
        }
        let view = try #require(controller.window?.contentView)
        let popup = try #require(find(view))
        #expect(popup.itemTitles == ["Yukio", "Qianxia"])
        #expect(popup.selectedItem?.representedObject as? String == "yukio")
        var received: PetSkin?
        controller.onChange = { if case .skin(let value) = $0 { received = value } }
        popup.selectItem(at: 1)
        _ = popup.sendAction(popup.action, to: popup.target)
        #expect(received == .qianxia)
        snapshot.skin = .qianxia
        snapshot = SettingsSnapshot(status: "Idle", following: true, hidden: false,
            provider: .auto, chats: [], showBubble: true, showCards: true, showQuestionCard: true,
            scale: 1, language: .chinese, demoPlaying: false, skin: .qianxia)
        L10n.language = .chinese
        controller.apply(snapshot)
        #expect(popup.itemTitles == ["雪绪", "千夏"])
        #expect(popup.selectedItem?.representedObject as? String == "qianxia")
    }

    @Test func qianxiaCatalogHasFullIndependentActions() throws {
        let root = PetSkin.qianxia.assetsRoot(in: Self.root)
        let catalog = try AnimationCatalog.load(assetsRoot: root)
        #expect(catalog.specs.count == 13)
        for state in PetState.allCases {
            let spec = catalog.spec(for: state)
            #expect(spec.id == state.rawValue)
            #expect(spec.assetPath.hasPrefix("motion/"))
            #expect(spec.frameWidth == 192 && spec.frameHeight == 208 && spec.pixelScale == 2)
            if let blink = spec.blink { #expect(blink.levels == 12) }
        }
        #expect(catalog.spec(for: .question_for_user).durationsMs.reduce(0, +) == 5000)
        #expect(PetSkin.identify(assetsRoot: root) == .qianxia)
    }
}
