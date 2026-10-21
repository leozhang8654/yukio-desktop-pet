import AppKit
import Testing
import YukioCore
@testable import YukioPlayer

@Suite @MainActor struct InteractionLifecycleTests {
    @Test func placementThrowCatchAndTaskReportUseRealWindows() throws {
        _ = NSApplication.shared
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Resources/Assets")
        let catalog = try AnimationCatalog.load(assetsRoot: root)
        let library = try SpriteLibrary(catalog: catalog, assetsRoot: root)
        let suite = "local.yukio.handfeel-tests." + UUID().uuidString
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let controller = AppController(catalog: catalog, library: library, defaults: defaults)
        let checks = controller.interactionLifecycleForCheck()
        for (name, passed) in checks.sorted(by: { $0.key < $1.key }) {
            #expect(passed, "\(name)")
        }
    }

    @Test func cancelledPressCannotLeaveADragOrOpenAChatOnLateRelease() throws {
        _ = NSApplication.shared
        let panel = PetPanel(size: NSSize(width: 192, height: 208))
        let view = PetView(frame: NSRect(x: 0, y: 0, width: 192, height: 208))
        panel.contentView = view
        defer { panel.close() }
        var cancelled = 0, released = 0, clicks = 0
        view.onCatch = { true }
        view.onDragCancelled = { cancelled += 1 }
        view.onDragEnded = { _ in released += 1 }
        view.onClick = { clicks += 1 }
        func event(_ type: NSEvent.EventType) throws -> NSEvent {
            try #require(NSEvent.mouseEvent(with: type, location: NSPoint(x: 90, y: 100),
                                            modifierFlags: [], timestamp: 1, windowNumber: panel.windowNumber,
                                            context: nil, eventNumber: 0, clickCount: 1, pressure: 1))
        }
        view.mouseDown(with: try event(.leftMouseDown))
        view.cancelDrag()
        view.mouseDragged(with: try event(.leftMouseDragged))
        view.mouseUp(with: try event(.leftMouseUp))
        #expect(cancelled == 1 && released == 0 && clicks == 0)
        #expect(!view.pressed && !view.dragging)
        view.mouseDown(with: try event(.leftMouseDown))
        view.mouseUp(with: try event(.leftMouseUp))
        #expect(released == 1 && clicks == 0)
    }
}
