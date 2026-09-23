import Foundation
import Testing
@testable import YukioCore

@Suite struct BlinkOverlayCatalogTests {
    static var assetsRoot: URL {
        if let candidate = ProcessInfo.processInfo.environment["YUKIO_TEST_ASSETS"] {
            return URL(fileURLWithPath: candidate)
        }
        return URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("Resources/Assets")
    }

    @Test func releasedStatesHaveIndependentEyepatchesButHeldDoesNot() throws {
        let catalog = try AnimationCatalog.load(assetsRoot: Self.assetsRoot)
        let animated = catalog.specs.values.filter { $0.id != AnimationCatalog.heldID }
        #expect(animated.count == 12)
        #expect(Set(animated.compactMap { $0.blink?.seed }).count == 12)
        for spec in animated {
            let blink = try #require(spec.blink)
            #expect(blink.levels == 6)
            #expect(blink.frames.count > spec.maxFrameIndex)
            #expect(blink.frames.allSatisfy { $0.count == 6 })
            #expect(spec.pixelScale == 2)
            #expect(spec.durationsMs.allSatisfy { $0 == 20 })
        }
        #expect(catalog.specs[AnimationCatalog.heldID]?.blink == nil)
    }

    @Test func malformedOverlayOutsideFrameIsRejected() throws {
        let fm = FileManager.default
        let root = fm.temporaryDirectory.appendingPathComponent("yukio-blink-validation-\(UUID().uuidString)")
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: root) }
        for relative in ["activities/activities.json", "base/base-animations.json"] {
            let destination = root.appendingPathComponent(relative)
            try fm.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
            try fm.copyItem(at: Self.assetsRoot.appendingPathComponent(relative), to: destination)
        }
        let data = try Data(contentsOf: Self.assetsRoot.appendingPathComponent("motion/motion.json"))
        var document = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        var states = try #require(document["states"] as? [[String: Any]])
        var blink = try #require(states[0]["blink"] as? [String: Any])
        blink["x"] = 100_000
        states[0]["blink"] = blink
        document["states"] = states
        try fm.createDirectory(at: root.appendingPathComponent("motion"), withIntermediateDirectories: true)
        try JSONSerialization.data(withJSONObject: document).write(to: root.appendingPathComponent("motion/motion.json"))
        #expect(throws: (any Error).self) { try AnimationCatalog.load(assetsRoot: root) }
    }
}
