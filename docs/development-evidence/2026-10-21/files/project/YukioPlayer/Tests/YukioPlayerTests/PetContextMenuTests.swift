import AppKit
import Testing
@testable import YukioPlayer

@Suite @MainActor struct PetContextMenuTests {
    @Test func backgroundPanelRoutesSecondaryClickOnceWithoutBecomingKey() throws {
        _ = NSApplication.shared
        let panel = PetPanel(size: NSSize(width: 192, height: 208))
        defer { panel.close() }
        let view = PetView(frame: NSRect(x: 0, y: 0, width: 192, height: 208))
        panel.contentView = view
        var settingsOpened = 0
        var ordinaryClicks = 0
        panel.onContextMenu = { _ in settingsOpened += 1 }
        view.onContextMenu = { _ in settingsOpened += 1 }
        view.onClick = { ordinaryClicks += 1 }
        #expect(!panel.canBecomeKey)
        for (down, up, flags) in [(NSEvent.EventType.rightMouseDown, NSEvent.EventType.rightMouseUp, NSEvent.ModifierFlags()),
                                  (.leftMouseDown, .leftMouseUp, .control)] {
            for type in [down, up] {
                let event = try #require(NSEvent.mouseEvent(with: type, location: NSPoint(x: 96, y: 100),
                                                          modifierFlags: flags, timestamp: 0,
                                                          windowNumber: panel.windowNumber, context: nil,
                                                          eventNumber: 0, clickCount: 1, pressure: 1))
                panel.sendEvent(event)
            }
        }
        #expect(settingsOpened == 2)
        #expect(ordinaryClicks == 0)
    }
}
