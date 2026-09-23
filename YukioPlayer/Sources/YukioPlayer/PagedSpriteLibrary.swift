import AppKit
import CryptoKit
import ImageIO
import YukioCore

/// Optional build-time lossless pages shared with Windows. The original catalog
/// remains authoritative; stale or malformed page manifests fail closed.
final class PagedSpriteLibrary {
    struct Pages: Decodable {
        let count: Int
        let perPage: Int
        let columns: Int?
        let pages: [String]
    }
    struct State: Decodable { let body: Pages; let eyes: Pages? }
    private struct Manifest: Decodable {
        let version: Int
        let motionSha256: String
        let states: [String: State]
    }
    private let root: URL
    private let states: [String: State]
    private var cache: [String: CGImage] = [:]
    private var recent: [String] = []
    private var bytes = 0
    private let budget = 32 * 1024 * 1024

    static func load(assetsRoot: URL, catalog: AnimationCatalog) throws -> PagedSpriteLibrary? {
        let root = assetsRoot.appendingPathComponent("motion/windows-pages")
        let url = root.appendingPathComponent("manifest.json")
        guard FileManager.default.fileExists(atPath: url.path) else { return nil }
        let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: url))
        let motion = try Data(contentsOf: assetsRoot.appendingPathComponent("motion/motion.json"))
        let digest = SHA256.hash(data: motion).map { String(format: "%02x", $0) }.joined()
        guard manifest.version == 1, manifest.motionSha256 == digest else {
            throw SpriteLibrary.LoadError.outOfBounds("stale motion pages")
        }
        let result = PagedSpriteLibrary(root: root, states: manifest.states)
        for (id, state) in manifest.states {
            guard let spec = catalog.specs[id], id != AnimationCatalog.heldID else {
                throw SpriteLibrary.LoadError.outOfBounds("unknown paged state \(id)")
            }
            let scale = max(spec.pixelScale, 1)
            try result.validate(state.body, width: spec.frameWidth * scale,
                                height: spec.frameHeight * scale, minimum: spec.maxFrameIndex + 1, body: true)
            if let blink = spec.blink {
                guard let eyes = state.eyes else { throw SpriteLibrary.LoadError.outOfBounds("missing eye pages \(id)") }
                try result.validate(eyes, width: blink.width, height: blink.height,
                                    minimum: (blink.frames.flatMap { $0 }.max() ?? 0) + 1, body: false)
            }
        }
        return result
    }

    private init(root: URL, states: [String: State]) { self.root = root; self.states = states }
    func contains(_ id: String) -> Bool { states[id] != nil }
    func count(_ id: String) -> Int { states[id]?.body.count ?? 0 }

    private func validate(_ plan: Pages, width: Int, height: Int, minimum: Int, body: Bool) throws {
        guard plan.count == minimum, (1...256).contains(plan.perPage),
              plan.pages.count == (plan.count + plan.perPage - 1) / plan.perPage,
              body || (1...256).contains(plan.columns ?? 0) else {
            throw SpriteLibrary.LoadError.outOfBounds("page geometry")
        }
        for (index, name) in plan.pages.enumerated() {
            guard !name.hasPrefix("/"), !name.split(separator: "/").contains(".."),
                  let source = CGImageSourceCreateWithURL(root.appendingPathComponent(name) as CFURL, nil),
                  let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
                  let w = properties[kCGImagePropertyPixelWidth] as? Int,
                  let h = properties[kCGImagePropertyPixelHeight] as? Int else {
                throw SpriteLibrary.LoadError.unreadable(name)
            }
            let take = min(plan.perPage, plan.count - index * plan.perPage)
            let cols = body ? plan.perPage : plan.columns!
            guard w == min(cols, take) * width, h == ((take + cols - 1) / cols) * height else {
                throw SpriteLibrary.LoadError.outOfBounds(name)
            }
        }
    }

    private func raster(_ name: String) -> CGImage? {
        guard let source = CGImageSourceCreateWithURL(root.appendingPathComponent(name) as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, [kCGImageSourceShouldCache: false] as CFDictionary),
              let ctx = CGContext(data: nil, width: image.width, height: image.height, bitsPerComponent: 8,
                                  bytesPerRow: image.width * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return nil }
        ctx.draw(image, in: CGRect(x: 0, y: 0, width: image.width, height: image.height))
        return ctx.makeImage()
    }

    private func page(_ name: String) -> CGImage? {
        if let cached = cache[name] {
            recent.removeAll { $0 == name }; recent.append(name)
            return cached
        }
        guard let image = raster(name) else { return nil }
        let incoming = image.width * image.height * 4
        while bytes + incoming > budget, !recent.isEmpty {
            if let old = cache.removeValue(forKey: recent.removeFirst()) { bytes -= old.width * old.height * 4 }
        }
        cache[name] = image; recent.append(name); bytes += incoming
        return image
    }

    func bodyFrame(_ spec: AnimationSpec, index: Int) -> CGImage? {
        guard let plan = states[spec.id]?.body, (0..<plan.count).contains(index),
              let sheet = page(plan.pages[index / plan.perPage]) else { return nil }
        let w = spec.frameWidth * max(spec.pixelScale, 1), h = spec.frameHeight * max(spec.pixelScale, 1)
        return sheet.cropping(to: CGRect(x: index % plan.perPage * w, y: 0, width: w, height: h))
    }

    func eyePatch(_ id: String, index: Int, blink: BlinkOverlay) -> CGImage? {
        guard let plan = states[id]?.eyes, (0..<plan.count).contains(index),
              let sheet = page(plan.pages[index / plan.perPage]) else { return nil }
        let local = index % plan.perPage, cols = plan.columns!
        return sheet.cropping(to: CGRect(x: local % cols * blink.width, y: local / cols * blink.height,
                                        width: blink.width, height: blink.height))
    }

    /// The same minimum over every frame as the original full-atlas scan.
    func headTop(_ spec: AnimationSpec) throws -> CGFloat {
        var top = Int.max
        for name in states[spec.id]!.body.pages {
            let row: Int = try autoreleasepool {
                guard let image = raster(name) else { throw SpriteLibrary.LoadError.unreadable(name) }
                return SpriteLibrary.firstOpaqueRow(image, frameHeight: spec.frameHeight * max(spec.pixelScale, 1))
            }
            top = min(top, row)
        }
        return top == Int.max ? 0 : CGFloat(top) / CGFloat(max(spec.pixelScale, 1))
    }
}
