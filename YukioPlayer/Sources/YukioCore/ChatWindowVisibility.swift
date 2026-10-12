import Foundation
import CoreGraphics

/// Screen coordinates remain in the system's global coordinate space, including
/// negative coordinates and displays above/below the primary screen.
public enum ChatWindowVisibility {
    /// The macOS Dock publishes a transparent, screen-sized input surface at
    /// layer 20 with window alpha 1. Its rectangle is not opaque content.
    /// Keep ordinary windows and the actual small Dock strip as occluders.
    public static func isDesktopOverlay(isDock: Bool, layer: Int, bounds: CGRect, screens: [CGRect]) -> Bool {
        isDock && layer == 20 && screens.contains {
            abs($0.minX - bounds.minX) < 2 && abs($0.minY - bounds.minY) < 2 &&
            abs($0.width - bounds.width) < 2 && abs($0.height - bounds.height) < 2
        }
    }

    public static func exposedParts(of rect: CGRect, screens: [CGRect], covers: [CGRect]) -> [CGRect] {
        guard !rect.isEmpty else { return [] }
        var parts = screens.map { rect.intersection($0) }.filter { !$0.isNull && !$0.isEmpty }
        for cover in covers {
            parts = parts.flatMap { part -> [CGRect] in
                let hit = part.intersection(cover)
                guard !hit.isNull && !hit.isEmpty else { return [part] }
                return [
                    CGRect(x: part.minX, y: part.minY, width: part.width, height: hit.minY - part.minY),
                    CGRect(x: part.minX, y: hit.maxY, width: part.width, height: part.maxY - hit.maxY),
                    CGRect(x: part.minX, y: hit.minY, width: hit.minX - part.minX, height: hit.height),
                    CGRect(x: hit.maxX, y: hit.minY, width: part.maxX - hit.maxX, height: hit.height),
                ].filter { !$0.isEmpty }
            }
        }
        return parts
    }

    /// A title bar or thin edge alone is not a visible conversation.
    public static func canRead(_ rect: CGRect, screens: [CGRect], covers: [CGRect]) -> Bool {
        exposedParts(of: rect, screens: screens, covers: covers).contains { $0.width >= 80 && $0.height >= 60 }
    }
}
