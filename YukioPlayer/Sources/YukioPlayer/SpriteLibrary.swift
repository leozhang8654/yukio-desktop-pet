import AppKit
import ImageIO
import YukioCore

/// 动画帧库。图条在要显示时才解码成一帧一张的独立小位图，最近用过的几段留在内存里，其余只记位置：
/// 动作图条帧数多，全部预先解码要一两百 MB。切到还没解码的动作时当场同步解码（几十毫秒），不会出现空白帧。
final class SpriteLibrary {
    struct Frame {
        let image: CGImage
        let width: Int
        let height: Int
        /// 自上而下逐行的 alpha，用于鼠标命中测试（透明处点击穿透）。
        let alpha: [UInt8]

        func isOpaque(x: Int, y: Int, threshold: UInt8 = 24) -> Bool {
            guard x >= 0, y >= 0, x < width, y < height else { return false }
            return alpha[y * width + x] > threshold
        }
    }

    enum LoadError: Error, CustomStringConvertible {
        case unreadable(String)
        case outOfBounds(String)

        var description: String {
            switch self {
            case .unreadable(let p): return "无法读取图片：\(p)"
            case .outOfBounds(let s): return "图格越界：\(s)"
            }
        }
    }

    let catalog: AnimationCatalog
    /// 各状态动作里人物最高点距帧顶的像素数（取最小）。头顶气泡贴着这条线放，换动作时气泡不上下跳。
    let headTopInset: CGFloat
    /// 拖动跑动时的最高点：跑起来头发扬起，比站姿高十来个像素，气泡要跟着抬高。
    let runningTopInset: CGFloat

    private static let runningIDs: Set<String> = [AnimationCatalog.runningLeftID, AnimationCatalog.runningRightID]
    /// 同时留在内存里的动画段数。
    private static let keepDecoded = 4

    private let urls: [String: URL]
    private let counts: [String: Int]
    private var decoded: [String: [Frame]] = [:]
    private var recent: [String] = []

    init(catalog: AnimationCatalog, assetsRoot: URL) throws {
        self.catalog = catalog
        var urls: [String: URL] = [:]
        var counts: [String: Int] = [:]
        var headTop = Int.max, runTop = Int.max
        // 启动时逐段解码一次：检查尺寸与帧索引、量出头顶线，然后丢掉，只记帧数和位置。
        for spec in catalog.specs.values {
            let url = assetsRoot.appendingPathComponent(spec.assetPath)
            let sheet = try Self.decodeSheet(url, spec)
            urls[spec.id] = url
            counts[spec.id] = sheet.width / spec.frameWidth
            let top = Self.firstOpaqueRow(sheet)
            if Self.runningIDs.contains(spec.id) { runTop = min(runTop, top) } else { headTop = min(headTop, top) }
        }
        self.urls = urls
        self.counts = counts
        headTopInset = headTop == .max ? 0 : CGFloat(headTop)
        runningTopInset = runTop == .max ? 0 : CGFloat(runTop)
    }

    func frameCount(_ specID: String) -> Int { counts[specID] ?? 0 }

    func frame(_ specID: String, _ index: Int) -> Frame {
        let id = urls[specID] != nil ? specID : PetState.default_work.rawValue
        let list: [Frame]
        if let cached = decoded[id] {
            list = cached
        } else {
            let fresh = decodeFrames(id)
            list = fresh.isEmpty ? [Self.blankFrame(catalog.specs[id])] : fresh
            decoded[id] = list
        }
        if recent.last != id {
            recent.removeAll { $0 == id }
            recent.append(id)
            while recent.count > Self.keepDecoded { decoded.removeValue(forKey: recent.removeFirst()) }
        }
        return list[min(max(index, 0), list.count - 1)]
    }

    private func decodeFrames(_ id: String) -> [Frame] {
        guard let spec = catalog.specs[id], let url = urls[id], let sheet = try? Self.decodeSheet(url, spec) else { return [] }
        var list: [Frame] = []
        for i in 0..<(sheet.width / spec.frameWidth) {
            let rect = CGRect(x: i * spec.frameWidth, y: 0, width: spec.frameWidth, height: spec.frameHeight)
            // 每帧复制成独立的小位图，图层只持有这一帧（192×208）。直接用 cropping 的子图时，
            // 显示每一帧都会连带整条图条的解码结果，内存会涨到两三百 MB。
            guard let cropped = sheet.cropping(to: rect),
                  let ctx = CGContext(data: nil, width: spec.frameWidth, height: spec.frameHeight, bitsPerComponent: 8,
                                      bytesPerRow: spec.frameWidth * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { continue }
            ctx.draw(cropped, in: CGRect(x: 0, y: 0, width: spec.frameWidth, height: spec.frameHeight))
            guard let image = ctx.makeImage() else { continue }
            list.append(Frame(image: image, width: spec.frameWidth, height: spec.frameHeight, alpha: Self.alphaMask(image)))
        }
        return list
    }

    private static func decodeSheet(_ url: URL, _ spec: AnimationSpec) throws -> CGImage {
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
              let sheet = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
            throw LoadError.unreadable(spec.assetPath)
        }
        let count = sheet.width / spec.frameWidth
        guard sheet.height == spec.frameHeight, spec.maxFrameIndex < count else {
            throw LoadError.outOfBounds("\(spec.id) \(sheet.width)×\(sheet.height)")
        }
        return sheet
    }

    /// 整条图条里第一行有不透明像素的行号（= 各帧最高点的最小值）。
    private static func firstOpaqueRow(_ image: CGImage, threshold: UInt8 = 24) -> Int {
        let alpha = alphaMask(image)
        let w = image.width
        for y in 0..<image.height where alpha[(y * w)..<((y + 1) * w)].contains(where: { $0 > threshold }) {
            return y
        }
        return Int.max
    }

    private static func blankFrame(_ spec: AnimationSpec?) -> Frame {
        let w = spec?.frameWidth ?? 192, h = spec?.frameHeight ?? 208
        let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                            space: CGColorSpace(name: CGColorSpace.sRGB)!,
                            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        return Frame(image: ctx.makeImage()!, width: w, height: h, alpha: [UInt8](repeating: 0, count: w * h))
    }

    private static func alphaMask(_ image: CGImage) -> [UInt8] {
        let w = image.width, h = image.height
        var buf = [UInt8](repeating: 0, count: w * h)
        buf.withUnsafeMutableBytes { raw in
            guard let ctx = CGContext(data: raw.baseAddress, width: w, height: h, bitsPerComponent: 8,
                                      bytesPerRow: w, space: CGColorSpaceCreateDeviceGray(),
                                      bitmapInfo: CGImageAlphaInfo.alphaOnly.rawValue) else { return }
            ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
        }
        return buf
    }
}

extension SpriteLibrary {
    /// 菜单栏小头像：取待机第一帧不透明区域顶部的正方形（头部）。比文字窄，菜单栏拥挤时更容易放下。
    func avatarImage() -> CGImage? {
        let f = frame("idle", 0)
        var minX = f.width, maxX = -1, minY = f.height
        for y in 0..<f.height {
            for x in 0..<f.width where f.isOpaque(x: x, y: y) {
                minX = min(minX, x); maxX = max(maxX, x); minY = min(minY, y)
            }
        }
        guard maxX > minX else { return nil }
        let side = Int(Double(maxX - minX + 1) * 0.75)
        let x = max(0, min(f.width - side, (minX + maxX) / 2 - side / 2))
        return f.image.cropping(to: CGRect(x: x, y: minY, width: side, height: min(side, f.height - minY)))
    }
}

/// 资源位置：环境变量 → 应用包内 → 开发时的工程目录。全部是相对工程或应用包的路径。
enum AssetLocator {
    static func assetsRoot() -> URL? {
        let fm = FileManager.default
        func valid(_ u: URL) -> Bool { fm.fileExists(atPath: u.appendingPathComponent("activities/activities.json").path) }
        if let env = ProcessInfo.processInfo.environment["YUKIO_ASSETS"] {
            let u = URL(fileURLWithPath: env)
            if valid(u) { return u }
        }
        if let res = Bundle.main.resourceURL?.appendingPathComponent("Assets"), valid(res) { return res }
        // swift run：Sources/YukioPlayer/SpriteLibrary.swift → 工程根目录/Resources/Assets
        let dev = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("Resources/Assets")
        return valid(dev) ? dev : nil
    }
}
