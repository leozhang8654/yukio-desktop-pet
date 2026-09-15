import AppKit
import ImageIO
import YukioCore

/// 预先裁好的全部帧。窗口显示前一次性加载完成，切换动作时不会出现空白帧或越界图格。
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
    private var frames: [String: [Frame]] = [:]

    /// 各状态动作里人物最高点距帧顶的像素数（取最小）。头顶气泡贴着这条线放，换动作时气泡不上下跳。
    private(set) lazy var headTopInset: CGFloat = self.topInset(where: { !Self.runningIDs.contains($0) })
    /// 拖动跑动时的最高点：跑起来头发扬起，比站姿高十来个像素，气泡要跟着抬高。
    private(set) lazy var runningTopInset: CGFloat = self.topInset(where: { Self.runningIDs.contains($0) })
    private static let runningIDs: Set<String> = [AnimationCatalog.runningLeftID, AnimationCatalog.runningRightID]

    private func topInset(where include: (String) -> Bool) -> CGFloat {
        var top = Int.max
        for (id, list) in frames where include(id) {
            for f in list {
                for y in 0..<f.height where (0..<f.width).contains(where: { f.isOpaque(x: $0, y: y) }) {
                    top = min(top, y)
                    break
                }
            }
        }
        return top == .max ? 0 : CGFloat(top)
    }

    init(catalog: AnimationCatalog, assetsRoot: URL) throws {
        self.catalog = catalog
        for spec in catalog.specs.values {
            let url = assetsRoot.appendingPathComponent(spec.assetPath)
            guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
                  let sheet = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
                throw LoadError.unreadable(spec.assetPath)
            }
            let count = sheet.width / spec.frameWidth
            guard sheet.height == spec.frameHeight, spec.maxFrameIndex < count else {
                throw LoadError.outOfBounds("\(spec.id) \(sheet.width)×\(sheet.height)")
            }
            var list: [Frame] = []
            for i in 0..<count {
                let rect = CGRect(x: i * spec.frameWidth, y: 0, width: spec.frameWidth, height: spec.frameHeight)
                // 每帧复制成独立的小位图，图层只持有这一帧（192×208）。直接用 cropping 的子图时，
                // 显示每一帧都会连带整条图条的解码结果，小幅动作的长图条会让内存涨到两三百 MB。
                guard let cropped = sheet.cropping(to: rect),
                      let ctx = CGContext(data: nil, width: spec.frameWidth, height: spec.frameHeight, bitsPerComponent: 8,
                                          bytesPerRow: spec.frameWidth * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else {
                    throw LoadError.outOfBounds("\(spec.id)#\(i)")
                }
                ctx.draw(cropped, in: CGRect(x: 0, y: 0, width: spec.frameWidth, height: spec.frameHeight))
                guard let image = ctx.makeImage() else { throw LoadError.outOfBounds("\(spec.id)#\(i)") }
                list.append(Frame(image: image, width: spec.frameWidth, height: spec.frameHeight,
                                  alpha: Self.alphaMask(image)))
            }
            frames[spec.id] = list
        }
    }

    func frameCount(_ specID: String) -> Int { frames[specID]?.count ?? 0 }

    func frame(_ specID: String, _ index: Int) -> Frame {
        let list = frames[specID] ?? frames[PetState.default_work.rawValue]!
        return list[min(max(index, 0), list.count - 1)]
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
