import AppKit

/// Mouse-only monitors need no accessibility permission and never consume the click.
final class SettingsOutsideClickMonitor {
    private var local: Any?
    private var global: Any?

    func start(window: NSWindow, isInteracting: @escaping () -> Bool,
               dismiss: @escaping () -> Void) {
        stop()
        let check: (NSEvent) -> Void = { [weak window] event in
            guard let window, window.isVisible, !isInteracting(),
                  window.attachedSheet == nil else { return }
            if event.window === window { return }
            // Include the title bar; menu tracking is handled by the controller.
            let point = event.window.map { $0.convertPoint(toScreen: event.locationInWindow) }
                ?? event.locationInWindow
            if !window.frame.contains(point) { dismiss() }
        }
        let mask: NSEvent.EventTypeMask = [.leftMouseDown, .rightMouseDown, .otherMouseDown]
        local = NSEvent.addLocalMonitorForEvents(matching: mask) { event in
            check(event)
            return event
        }
        global = NSEvent.addGlobalMonitorForEvents(matching: mask, handler: check)
    }

    func stop() {
        if let local { NSEvent.removeMonitor(local) }
        if let global { NSEvent.removeMonitor(global) }
        local = nil
        global = nil
    }

    deinit { stop() }
}
