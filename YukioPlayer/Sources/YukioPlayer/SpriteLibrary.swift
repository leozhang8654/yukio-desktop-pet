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
    /// 各状态动作里人物最高点距帧顶的像素数（取最小）。没量到那一段时退回它。
    /// 不含「被拎起来」：那一帧领口的尖比头还高，算进来会把平时的气泡整体顶上去。
    let headTopInset: CGFloat
    /// 每一段各自的头顶线。站着的待机比坐着高一截，气泡要贴各自的头，不能共用一条线。
    private let headTops: [String: CGFloat]
    /// 「被拎起来」那一帧里，抓手点到人物重心的距离（像素）。摆动就是绕抓手点吊着这段长度。
    let hangLength: CGFloat
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
        var headTop = CGFloat.greatestFiniteMagnitude
        var headTops: [String: CGFloat] = [:]
        var hangLength: CGFloat = 0
        // 启动时逐段解码一次：检查尺寸与帧索引、量出头顶线与重心，然后丢掉，只记帧数和位置。
        for spec in catalog.specs.values {
            let url = assetsRoot.appendingPathComponent(spec.assetPath)
            let sheet = try Self.decodeSheet(url, spec)
            urls[spec.id] = url
            let cell = Self.cell(spec)
            counts[spec.id] = Self.frameCount(sheet, spec)
            // 量出来的是图里的像素；除以 pixelScale 换成点，和窗口、锚点用同一套单位。
            let k = CGFloat(max(spec.pixelScale, 1))
            if spec.id == AnimationCatalog.heldID, let anchors = spec.hang {
                // 重心按不透明像素取平均：图换了（重画、改姿势）摆长自己跟着变，不用手填数字。
                let center = Self.centroid(sheet, width: cell.width, height: cell.height)
                hangLength = max(hypot(center.x / k - CGFloat(anchors.gripX), center.y / k - CGFloat(anchors.gripY)), 1)
            } else {
                let row = Self.firstOpaqueRow(sheet, frameHeight: cell.height)
                if row != Int.max {
                    headTops[spec.id] = CGFloat(row) / k
                    headTop = min(headTop, CGFloat(row) / k)
                }
            }
        }
        self.urls = urls
        self.counts = counts
        headTopInset = headTop == .greatestFiniteMagnitude ? 0 : headTop
        self.headTops = headTops
        self.hangLength = hangLength
    }

    /// 这一段自己的头顶线（气泡与卡叠贴着它放）。
    func headTopInset(for specID: String) -> CGFloat { headTops[specID] ?? headTopInset }

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
        let cell = Self.cell(spec)
        let perRow = sheet.width / cell.width
        for i in 0..<Self.frameCount(sheet, spec) {
            let rect = CGRect(x: (i % perRow) * cell.width, y: (i / perRow) * cell.height,
                              width: cell.width, height: cell.height)
            // 每帧复制成独立的小位图，图层只持有这一帧（1 倍图 192×208、2 倍图 384×416）。直接用 cropping 的子图时，
            // 显示每一帧都会连带整条图条的解码结果，内存会涨到两三百 MB。
            guard let cropped = sheet.cropping(to: rect),
                  let ctx = CGContext(data: nil, width: cell.width, height: cell.height, bitsPerComponent: 8,
                                      bytesPerRow: cell.width * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { continue }
            ctx.draw(cropped, in: CGRect(x: 0, y: 0, width: cell.width, height: cell.height))
            guard let image = ctx.makeImage() else { continue }
            list.append(Frame(image: image, width: cell.width, height: cell.height, alpha: Self.alphaMask(image)))
        }
        return list
    }

    /// 图条里一格的像素尺寸：帧的点尺寸 × pixelScale。
    private static func cell(_ spec: AnimationSpec) -> (width: Int, height: Int) {
        let k = max(spec.pixelScale, 1)
        return (spec.frameWidth * k, spec.frameHeight * k)
    }

    /// 图条里真正的帧数。折成几行时最后一行不一定排满，空格不算帧：以序列里用到的最大帧号为准。
    private static func frameCount(_ sheet: CGImage, _ spec: AnimationSpec) -> Int {
        let cell = Self.cell(spec)
        let perRow = sheet.width / cell.width, rows = sheet.height / cell.height
        return rows > 1 ? min(perRow * rows, spec.maxFrameIndex + 1) : perRow * rows
    }

    private static func decodeSheet(_ url: URL, _ spec: AnimationSpec) throws -> CGImage {
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
              let sheet = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
            throw LoadError.unreadable(spec.assetPath)
        }
        // 图条可以排成几行（2 倍图太长时折行），按行优先编号。
        let cell = Self.cell(spec)
        let count = (sheet.width / cell.width) * (sheet.height / cell.height)
        guard sheet.height % cell.height == 0, sheet.width % cell.width == 0, spec.maxFrameIndex < count else {
            throw LoadError.outOfBounds("\(spec.id) \(sheet.width)×\(sheet.height)")
        }
        return sheet
    }

    /// 图条第一帧里不透明像素的重心（帧内像素，左上原点）。
    private static func centroid(_ image: CGImage, width frameWidth: Int, height frameHeight: Int,
                                 threshold: UInt8 = 24) -> CGPoint {
        let alpha = alphaMask(image)
        let w = image.width
        var sumX = 0.0, sumY = 0.0, count = 0.0
        for y in 0..<min(frameHeight, image.height) {
            for x in 0..<min(frameWidth, w) where alpha[y * w + x] > threshold {
                sumX += Double(x); sumY += Double(y); count += 1
            }
        }
        guard count > 0 else { return CGPoint(x: Double(frameWidth) / 2, y: Double(frameHeight) / 2) }
        return CGPoint(x: sumX / count, y: sumY / count)
    }

    /// 各帧最高点的最小值（帧内像素行号）。图条排成几行时逐行带扫，每一带里第一行有不透明像素的行号，取最小。
    private static func firstOpaqueRow(_ image: CGImage, frameHeight: Int, threshold: UInt8 = 24) -> Int {
        let alpha = alphaMask(image)
        let w = image.width
        var best = Int.max
        for band in stride(from: 0, to: image.height, by: max(frameHeight, 1)) {
            for y in band..<min(band + frameHeight, image.height) {
                if y - band >= best { break }
                if alpha[(y * w)..<((y + 1) * w)].contains(where: { $0 > threshold }) {
                    best = y - band
                    break
                }
            }
        }
        return best
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

/// 资源位置：环境变量 → 应用包内 → 开发时的工程目录（仅调试构建）。全部是相对工程或应用包的路径。
enum AssetLocator {
    static func assetsRoot() -> URL? {
        let fm = FileManager.default
        func valid(_ u: URL) -> Bool { fm.fileExists(atPath: u.appendingPathComponent("activities/activities.json").path) }
        if let env = ProcessInfo.processInfo.environment["YUKIO_ASSETS"] {
            let u = URL(fileURLWithPath: env)
            if valid(u) { return u }
        }
        if let res = Bundle.main.resourceURL?.appendingPathComponent("Assets"), valid(res) { return res }
        #if DEBUG
        // swift run：Sources/YukioPlayer/SpriteLibrary.swift → 工程根目录/Resources/Assets
        // 只留在调试构建里：#filePath 会把本机源码路径编进二进制，发行版不该带。
        let dev = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("Resources/Assets")
        return valid(dev) ? dev : nil
        #else
        return nil
        #endif
    }
}
