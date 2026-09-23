import AppKit
import YukioCore

func nowMs() -> Double { Date().timeIntervalSince1970 * 1000 }

// MARK: - 命令行模式（无窗口）

func loadCatalogOrExit() -> (AnimationCatalog, URL) {
    guard let root = AssetLocator.assetsRoot() else {
        FileHandle.standardError.write(Data("找不到资源目录 Assets（可用 YUKIO_ASSETS 指定）\n".utf8))
        exit(1)
    }
    do {
        return (try AnimationCatalog.load(assetsRoot: root), root)
    } catch {
        FileHandle.standardError.write(Data("资源加载失败：\(error)\n".utf8))
        exit(1)
    }
}

func timeString(_ ms: Double) -> String {
    let f = DateFormatter()
    f.dateFormat = "HH:mm:ss.SSS"
    return f.string(from: Date(timeIntervalSince1970: ms / 1000))
}

func describe(_ e: PetEvent) -> String {
    var s = "\(e.kind.rawValue)"
    if let t = e.tool { s += " \(t)" }
    if let a = e.activity { s += " → \(a.rawValue)" } else if e.kind == .activityStart { s += " → (延续上一个)" }
    return s
}

/// 棋盘格背景：透明区域一目了然。
func fillCheckerboard(_ ctx: CGContext, width: Int, height: Int) {
    for y in stride(from: 0, to: height, by: 16) {
        for x in stride(from: 0, to: width, by: 16) {
            let dark = ((x / 16) + (y / 16)) % 2 == 0
            ctx.setFillColor(gray: dark ? 0.80 : 0.92, alpha: 1)
            ctx.fill(CGRect(x: x, y: y, width: 16, height: 16))
        }
    }
}

func savePNG(_ ctx: CGContext, to path: String) -> Bool {
    guard let image = ctx.makeImage(),
          let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: path) as CFURL, "public.png" as CFString, 1, nil) else { return false }
    CGImageDestinationAddImage(dest, image, nil)
    return CGImageDestinationFinalize(dest)
}

/// --check：加载并裁切全部资源，确认没有越界。
func runCheck() -> Never {
    let (catalog, root) = loadCatalogOrExit()
    do {
        _ = try SpriteLibrary(catalog: catalog, assetsRoot: root)
        print("OK：\(catalog.specs.count) 段动画，资源目录 \(root.path)")
        exit(0)
    } catch {
        print("失败：\(error)")
        exit(1)
    }
}

/// --snapshot <输出.png>：把播放器实际使用的动画画在棋盘格上（检查裁切、透明边缘、比例）。帧多的动画均匀抽 10 帧。
func runSnapshot(path: String) -> Never {
    let (catalog, root) = loadCatalogOrExit()
    let library: SpriteLibrary
    do { library = try SpriteLibrary(catalog: catalog, assetsRoot: root) } catch { print("失败：\(error)"); exit(1) }
    let specs = PetState.allCases.map { catalog.spec(for: $0) } + [catalog.specs[AnimationCatalog.heldID]!]
    // 「被拎起来」那一帧比常规帧高（领口的尖在头顶上方、腿垂下来），格子按最高的那段算。
    let cellW = 192, cellH = specs.map(\.frameHeight).max() ?? 208, labelH = 26, maxCols = 10
    let cols = min(maxCols, specs.map { library.frameCount($0.id) }.max() ?? 1)
    let width = cols * cellW, height = specs.count * (cellH + labelH)
    guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpace(name: CGColorSpace.sRGB)!,
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
    fillCheckerboard(ctx, width: width, height: height)
    NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
    for (row, spec) in specs.enumerated() {
        let top = height - row * (cellH + labelH)
        ctx.setFillColor(gray: 1, alpha: 1)
        ctx.fill(CGRect(x: 0, y: top - labelH, width: width, height: labelH))
        let count = library.frameCount(spec.id)
        let picks = count <= maxCols ? Array(0..<count) : (0..<maxCols).map { $0 * (count - 1) / (maxCols - 1) }
        let cycle = Int(spec.durationsMs.reduce(0, +))
        let title = "\(spec.id) · \(spec.label) · \(count) 帧 · \(spec.sequence.count) 步 · 一轮 \(cycle) ms · \(spec.loop ? "循环" : "播一次后停住")"
        (title as NSString).draw(at: NSPoint(x: 6, y: top - labelH + 6),
                                 withAttributes: [.font: NSFont.systemFont(ofSize: 13), .foregroundColor: NSColor.black])
        for (i, f) in picks.enumerated() {
            ctx.draw(library.frame(spec.id, f).image,
                     in: CGRect(x: i * cellW, y: top - labelH - spec.frameHeight,
                                width: spec.frameWidth, height: spec.frameHeight))
        }
    }
    // 第一行有空位时画菜单栏头像：放大版与实际 18 pt 大小（Retina 下 36 px）。
    if let avatar = library.avatarImage(), library.frameCount(specs[0].id) + 2 <= cols {
        let top = height - labelH
        ctx.draw(avatar, in: CGRect(x: 6 * cellW + 20, y: top - 120, width: 96, height: 96))
        ctx.draw(avatar, in: CGRect(x: 7 * cellW + 20, y: top - 60, width: 36, height: 36))
    }
    NSGraphicsContext.current = nil
    exit(savePNG(ctx, to: path) ? 0 : 1)
}

/// --hang <输出.png>：把「被大手拎着」按几个倾角画出来，外面套上实际会用的窗口框。
/// 用来核对：抓手点是不是在领口被捏起的那个尖上、晃到两边会不会被窗口切掉、上边缘是否与平时那块对齐。
func runHangSnapshot(path: String) -> Never {
    let (catalog, root) = loadCatalogOrExit()
    let library: SpriteLibrary
    do { library = try SpriteLibrary(catalog: catalog, assetsRoot: root) } catch { print("失败：\(error)"); exit(1) }
    let spec = catalog.specs[AnimationCatalog.heldID]!
    let pet = NSSize(width: 192, height: 208)
    let tuning = HangSwing.Tuning()
    let geo = HangGeometry.make(petSize: pet, held: spec, scale: 1,
                                sagRoom: library.hangLength * CGFloat(tuning.maxSagRatio))
    let maxAngle = tuning.maxAngleDeg
    let angles: [Double] = [-maxAngle, -maxAngle / 2, 0, maxAngle / 2, maxAngle]
    let labelH = 26
    let cellW = Int(geo.panelSize.width.rounded(.up)), cellH = Int(geo.panelSize.height.rounded(.up))
    let width = cellW * angles.count, height = cellH + labelH
    guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpace(name: CGColorSpace.sRGB)!,
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
    fillCheckerboard(ctx, width: width, height: height)
    NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
    ctx.setFillColor(gray: 1, alpha: 1)
    ctx.fill(CGRect(x: 0, y: height - labelH, width: width, height: labelH))
    let title = "held · 摆长 \(Int(library.hangLength)) px · 一摆 \(String(format: "%.2f", tuning.periodSec)) 秒 · " +
        "最多坠 \(Int(library.hangLength * CGFloat(tuning.maxSagRatio))) px · 窗口 \(cellW)×\(cellH)（平时 192×208）· 抓手点 " +
        "(\(Int(geo.pivot.x)), 上边下 \(Int(geo.panelSize.height - geo.pivot.y))) · 倾角 " +
        angles.map { "\(Int($0))°" }.joined(separator: " ")
    (title as NSString).draw(at: NSPoint(x: 6, y: height - labelH + 6),
                             withAttributes: [.font: NSFont.systemFont(ofSize: 13), .foregroundColor: NSColor.black])
    let frame = library.frame(spec.id, 0)
    for (i, deg) in angles.enumerated() {
        let dx = CGFloat(i * cellW)
        // 平时那块 192×208 的位置：窗口框减去放大时的偏移。
        let normal = NSRect(x: dx - geo.offset.x, y: -geo.offset.y, width: pet.width, height: pet.height)
        ctx.setStrokeColor(red: 0.2, green: 0.5, blue: 1, alpha: 0.8)
        ctx.setLineWidth(1)
        ctx.stroke(normal.insetBy(dx: 0.5, dy: 0.5))
        ctx.setStrokeColor(red: 1, green: 0.2, blue: 0.2, alpha: 0.6)
        ctx.stroke(CGRect(x: dx + 0.5, y: 0.5, width: CGFloat(cellW) - 1, height: CGFloat(cellH) - 1))
        let pivot = NSPoint(x: dx + geo.pivot.x, y: geo.pivot.y)
        ctx.saveGState()
        ctx.translateBy(x: pivot.x, y: pivot.y)
        ctx.rotate(by: CGFloat(deg * .pi / 180))
        ctx.translateBy(x: -pivot.x, y: -pivot.y)
        ctx.draw(frame.image, in: geo.spriteRect.offsetBy(dx: dx, dy: 0))
        ctx.restoreGState()
        ctx.setFillColor(red: 1, green: 0.4, blue: 0, alpha: 1)
        ctx.fillEllipse(in: CGRect(x: pivot.x - 3, y: pivot.y - 3, width: 6, height: 6))
    }
    NSGraphicsContext.current = nil
    guard savePNG(ctx, to: path) else { exit(1) }
    exit(checkSwingDirection(frame: frame, geo: geo) ? 0 : 1)
}

/// 摆动方向自检：正角必须让脚偏向右边。
///
/// 这件事只错过一次就够难看的——曾经把旋转写成 -angle，屏幕上成了「脚朝着移动方向甩出去」，
/// 与真实的钟摆相反。所以这里两条路都量一遍：画到位图上量脚的位置，再直接算一次 PetView 用的那个矩阵。
func checkSwingDirection(frame: SpriteLibrary.Frame, geo: HangGeometry) -> Bool {
    /// 把图按给定角度绕抓手点画一遍，返回「下半身横向重心 − 上半身横向重心」（正数＝脚偏右）。
    func feetOffset(_ deg: Double) -> Double {
        let w = Int(geo.panelSize.width.rounded(.up)), h = Int(geo.panelSize.height.rounded(.up))
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return 0 }
        ctx.translateBy(x: geo.pivot.x, y: geo.pivot.y)
        ctx.rotate(by: CGFloat(deg * .pi / 180))
        ctx.translateBy(x: -geo.pivot.x, y: -geo.pivot.y)
        ctx.draw(frame.image, in: geo.spriteRect)
        guard let image = ctx.makeImage(), let data = image.dataProvider?.data,
              let bytes = CFDataGetBytePtr(data) else { return 0 }
        let stride = image.bytesPerRow
        var rows: [(y: Int, sum: Double, count: Double)] = []
        for y in 0..<h {
            var sum = 0.0, count = 0.0
            for x in 0..<w where bytes[y * stride + x * 4 + 3] > 24 { sum += Double(x); count += 1 }
            if count > 0 { rows.append((y, sum, count)) }
        }
        guard rows.count > 10 else { return 0 }
        // CGBitmapContext 的坐标系 y 向上，但缓冲区第一行是画面最**顶**上那行，所以 rows 开头是头、结尾是脚。
        let cut = max(1, rows.count / 5)
        func centroid(_ part: ArraySlice<(y: Int, sum: Double, count: Double)>) -> Double {
            let s = part.reduce(0.0) { $0 + $1.sum }, c = part.reduce(0.0) { $0 + $1.count }
            return c > 0 ? s / c : 0
        }
        return centroid(rows.suffix(cut)) - centroid(rows.prefix(cut))
    }

    var ok = true
    for deg in [-20.0, 20.0] {
        let drawn = feetOffset(deg)
        // PetView 用的就是这个矩阵，这里对「抓手点正下方 100 点」算一次。
        let t = CATransform3DGetAffineTransform(CATransform3DMakeRotation(CGFloat(deg * .pi / 180), 0, 0, 1))
        let layer = CGPoint(x: 0, y: -100).applying(t).x
        let good = drawn * deg > 0 && layer * deg > 0
        ok = ok && good
        print(String(format: "方向自检 %+.0f°：画出来脚偏%@ %.0f px，图层矩阵偏%@ %.0f px %@",
                     deg, drawn > 0 ? "右" : "左", abs(drawn),
                     layer > 0 ? "右" : "左", abs(layer), good ? "✓" : "✗ 反了"))
    }
    if !ok { print("摆动方向反了：正角必须让脚偏向右边（手往右甩时角度为负，脚应当落在后面）") }
    return ok
}

/// --hang-gif <输出.gif>：用真实的摆动逻辑演一遍「拎起来拖一段再放下」，存成 30 fps 的 GIF。
/// 本机没有录屏权限，这是唯一能直接看到晃动手感的方式：手的轨迹写死，角度由 HangSwing 算。
func runHangGIF(path: String) -> Never {
    let (catalog, root) = loadCatalogOrExit()
    let library: SpriteLibrary
    do { library = try SpriteLibrary(catalog: catalog, assetsRoot: root) } catch { print("失败：\(error)"); exit(1) }
    let spec = catalog.specs[AnimationCatalog.heldID]!
    let pet = NSSize(width: 192, height: 208)
    let tuning = HangSwing.Tuning()
    let geo = HangGeometry.make(petSize: pet, held: spec, scale: 1,
                                sagRoom: library.hangLength * CGFloat(tuning.maxSagRatio))

    // 手的轨迹（毫秒，速度 点/秒，y 向上为正）：
    // 停一下 → 往右拖 → 顿住 → 松手荡停 → 再抓住猛地往上一提（看「坠」）→ 往左甩 → 松手。
    let script: [(ms: Double, vx: Double, vy: Double, release: Bool)] = [
        (200, 0, 0, false), (450, 900, 0, false), (250, 0, 0, false), (900, 0, 0, true),
        (150, 0, 0, false), (220, 0, 700, false), (330, 0, 0, false),
        (250, -1500, 0, false), (200, 0, 0, false), (1200, 0, 0, true),
    ]
    let fps = 30.0, step = 1000.0 / fps
    var swing = HangSwing(now: 0, length: Double(library.hangLength))
    var now = 0.0, handX = 60.0, handY = 60.0
    var minX = handX, maxX = handX, minY = handY, maxY = handY
    var frames: [(x: CGFloat, y: CGFloat, angle: Double, sag: Double)] = []
    var grabbed = true
    for part in script {
        if part.release { swing.release(); grabbed = false } else if !grabbed { swing.grab(); grabbed = true }
        var left = part.ms
        while left > 0 {
            let h = min(step, left)
            left -= h
            now += h
            handX += part.vx * h / 1000
            handY += part.vy * h / 1000
            swing.advance(to: now, handX: handX, handY: handY)
            minX = min(minX, handX); maxX = max(maxX, handX)
            minY = min(minY, handY); maxY = max(maxY, handY)
            frames.append((CGFloat(handX), CGFloat(handY), swing.angle, swing.sag))
        }
    }

    let width = Int((maxX - minX + geo.panelSize.width).rounded(.up)) + 40
    let height = Int((maxY - minY + geo.panelSize.height).rounded(.up)) + 20
    guard let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: path) as CFURL,
                                                     "com.compuserve.gif" as CFString, frames.count, nil) else { exit(1) }
    CGImageDestinationSetProperties(dest, [kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFLoopCount: 0]] as CFDictionary)
    let frame = library.frame(spec.id, 0)
    for f in frames {
        guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
        ctx.setFillColor(gray: 0.96, alpha: 1)
        ctx.fill(CGRect(x: 0, y: 0, width: width, height: height))
        ctx.setFillColor(gray: 0.88, alpha: 1)
        ctx.fill(CGRect(x: 0, y: 0, width: width, height: 10))          // 一条“桌面”，好看出横向移动
        // 窗口左下角：手的位置减去抓手点在窗口里的位置。
        let origin = NSPoint(x: f.x - minX + 20 - geo.pivot.x, y: f.y - minY + 10)
        let pivot = NSPoint(x: origin.x + geo.pivot.x, y: origin.y + geo.pivot.y)
        ctx.saveGState()
        ctx.translateBy(x: pivot.x, y: pivot.y)
        ctx.rotate(by: CGFloat(f.angle))
        ctx.translateBy(x: -pivot.x, y: -pivot.y)
        ctx.draw(frame.image, in: geo.spriteRect.offsetBy(dx: origin.x, dy: origin.y - CGFloat(f.sag)))
        ctx.restoreGState()
        guard let image = ctx.makeImage() else { exit(1) }
        CGImageDestinationAddImage(dest, image, [kCGImagePropertyGIFDictionary:
            [kCGImagePropertyGIFUnclampedDelayTime: 1.0 / fps]] as CFDictionary)
    }
    guard CGImageDestinationFinalize(dest) else { exit(1) }
    print("\(path)：\(frames.count) 帧 / \(String(format: "%.1f", Double(frames.count) / fps)) 秒，\(width)×\(height)")
    exit(0)
}

/// --bubble <输出.png>：把几种头顶气泡画在对应动作上方，按 Retina 2 倍输出（检查排版、截断、位置）。
func runBubbleSnapshot(path: String) -> Never {
    let (catalog, root) = loadCatalogOrExit()
    let library: SpriteLibrary
    do { library = try SpriteLibrary(catalog: catalog, assetsRoot: root) } catch { print("失败：\(error)"); exit(1) }
    let samples: [(PetState, StatusLine)] = [
        (.write_file, StatusLine(title: tr("Desktop pet: missing states", "桌宠缺失状态"),
                                 current: tr("Add the head bubble", "实现头顶气泡"), progress: .init(done: 3, total: 7))),
        (.verify, StatusLine(title: tr("Fix the login form validation, add unit tests, and tidy up the folder layout",
                                       "修复登录页的表单校验问题并补充单元测试，顺便整理目录结构"),
                             current: "$ swift test --filter RouterTests", progress: nil)),
        (.thinking, StatusLine(title: nil, current: tr("Thinking", "思考中"), progress: nil)),
        (.failed, StatusLine(title: tr("Desktop pet: missing states", "桌宠缺失状态"),
                             current: tr("Error: $ swift test", "出错：$ swift test"), progress: .init(done: 7, total: 7))),
        (.question_for_user, StatusLine(title: tr("Desktop pet: missing states", "桌宠缺失状态"),
                                        current: tr("Your turn · click to open", "等你回答 · 点她跳过去"), progress: nil)),
        (.task_complete, StatusLine(title: tr("Desktop pet: missing states", "桌宠缺失状态"),
                                    current: tr("Done · click to open", "已完成 · 点她跳过去"), progress: .init(done: 7, total: 7))),
    ]
    let cellW: CGFloat = 240, cellH: CGFloat = 208 + 64, px: CGFloat = 2
    let width = Int(cellW * CGFloat(samples.count) * px), height = Int(cellH * px)
    guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpace(name: CGColorSpace.sRGB)!,
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
    fillCheckerboard(ctx, width: width, height: height)
    ctx.scaleBy(x: px, y: px)
    ctx.interpolationQuality = .high
    NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
    for (i, (state, line)) in samples.enumerated() {
        let spec = catalog.spec(for: state)
        let frame = library.frame(spec.id, spec.sequence.last ?? 0)
        let pet = CGRect(x: CGFloat(i) * cellW + (cellW - 192) / 2, y: 0, width: 192, height: 208)
        ctx.draw(frame.image, in: pet)
        let layout = BubbleLayout(line)
        let origin = BubbleLayout.origin(size: layout.size, petFrame: pet, headTop: library.headTopInset(for: spec.id))
        layout.draw(in: NSRect(origin: origin, size: layout.size))
    }
    NSGraphicsContext.current = nil
    exit(savePNG(ctx, to: path) ? 0 : 1)
}

/// --cards <输出.png>：把雪绪旁边那叠通知卡画出来（收起与展开各一格），按 2 倍分辨率输出，
/// 检查排版、截断、状态颜色和与气泡的关系。
func runCardsSnapshot(path: String) -> Never {
    let (catalog, root) = loadCatalogOrExit()
    let library: SpriteLibrary
    do { library = try SpriteLibrary(catalog: catalog, assetsRoot: root) } catch { print("失败：\(error)"); exit(1) }
    let cards: [ActivityCard] = [
        .init(session: "a", title: tr("Question card opens the chat", "问题牌子点击跳转聊天"),
              subtitle: tr("Pick an option", "等你挑一个方案"), status: .waiting, quietMs: 20_000),
        .init(session: "b", title: tr("Run the Windows packaging", "跑一遍 Windows 打包"),
              subtitle: tr("Error: $ pwsh build.ps1", "出错：$ pwsh build.ps1"), status: .failed, quietMs: 60_000),
        .init(session: "c", title: tr("Write a backup script", "写个备份脚本"), subtitle: tr("Take a look", "点开看看"), status: .ready, quietMs: 8_000),
        .init(session: "d", title: tr("Pet drag animation and swing", "桌宠移动动画与晃动效果"),
              subtitle: tr("Editing HangSwing.swift", "编辑 HangSwing.swift"), status: .running, quietMs: 2_000),
        .init(session: "e", title: tr("Session 5c534545…", "会话 5c534545…"), subtitle: "$ swift test --filter RouterTests", status: .running, quietMs: 4_000),
    ]
    let line = StatusLine(title: tr("Picking a chat when several run at once", "多个聊天同时运行时的选择功能"),
                          current: tr("Editing main.swift", "编辑 main.swift"),
                          progress: .init(done: 3, total: 5))
    let px: CGFloat = 2, cellW: CGFloat = 260, cellH: CGFloat = 560
    let width = Int(cellW * 2 * px), height = Int(cellH * px)
    guard let ctx = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpace(name: CGColorSpace.sRGB)!,
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
    fillCheckerboard(ctx, width: width, height: height)
    ctx.scaleBy(x: px, y: px)
    ctx.interpolationQuality = .high
    NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
    for (i, expanded) in [false, true].enumerated() {   // 左：平时（收起）；右：点一下摊开
        let cell = NSRect(x: CGFloat(i) * cellW, y: 0, width: cellW, height: cellH)
        let spec = catalog.spec(for: expanded ? .thinking : .write_file)
        let pet = NSRect(x: cell.minX + (cellW - 192) / 2, y: 8, width: 192, height: 208)
        ctx.draw(library.frame(spec.id, spec.sequence.last ?? 0).image, in: pet)
        let bubble = BubbleLayout(line)
        let bubbleRect = NSRect(origin: BubbleLayout.origin(size: bubble.size, petFrame: pet,
                                                            headTop: library.headTopInset(for: spec.id)),
                                size: bubble.size)
        bubble.draw(in: bubbleRect)
        let layout = CardStackLayout(cards: cards, expanded: expanded, pinned: expanded)
        let origin = CardStackLayout.origin(size: layout.size, petFrame: pet,
                                            bubbleTop: bubbleRect.maxY, visible: cell)
        layout.draw(in: NSRect(origin: origin, size: layout.size))
    }
    NSGraphicsContext.current = nil
    // 顺便自查点击分区：摊开那摞里，每张卡中心该落在 card(i)，右上角该落在 dismiss(i)。
    let probe = CardStackLayout(cards: cards, expanded: true, pinned: true)
    let box = NSRect(origin: .zero, size: probe.size)
    var lines: [String] = []
    for (name, point) in CardStackLayout.probePoints(probe, in: box) {
        lines.append("\(name) → \(String(describing: probe.hit(at: point, in: box)))")
    }
    print("点击分区自查：\n  " + lines.joined(separator: "\n  "))
    exit(savePNG(ctx, to: path) ? 0 : 1)
}

/// 命令行 `--source claude|deepseek|gpt|auto`；没写就用设置里的（跟界面一致）。
func providerFromArgs() -> AgentProvider {
    let args = CommandLine.arguments
    if let i = args.firstIndex(of: "--source"), i + 1 < args.count {
        return AgentProvider(code: args[i + 1])
    }
    return AgentProvider(code: UserDefaults.standard.string(forKey: "source"))
}

/// 回放：按记录长什么样认出是哪一家写的，用对应的解析器。
func replayEvents(_ objects: [Data], fileName: String) -> [PetEvent] {
    func shape(_ data: Data) -> String? {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return nil }
        if obj["payload"] != nil || ["session_meta", "response_item", "event_msg"].contains(obj["type"] as? String ?? "") {
            return "codex"
        }
        if obj["messageParams"] != nil || obj["createTime"] != nil { return "deepcode" }
        if obj["sessionId"] != nil || obj["timestamp"] != nil { return "claude" }
        return nil
    }
    let kind = objects.prefix(40).compactMap(shape).first ?? "claude"
    print("记录格式：\(kind)")
    switch kind {
    case "codex":
        let parser = CodexRolloutParser(session: CodexSessionsSource.sessionID(fromFileName: fileName))
        return objects.flatMap { parser.events(fromLine: $0, now: 0) }
    case "deepcode":
        let parser = DeepCodeMessageParser()
        let session = (fileName as NSString).deletingPathExtension
        return objects.flatMap { parser.events(fromLine: $0, fallbackSession: session) }
    default:
        let parser = ClaudeTranscriptParser()
        return objects.flatMap { parser.events(fromLine: $0) }
    }
}

/// --replay <会话记录.jsonl> [--with-bubble]：用虚拟时钟回放一份真实记录，打印雪绪会显示的状态序列。
/// 加 --with-bubble 时同时打印头顶气泡的文字变化（含标题与文件名，只输出到本机终端）。
func runReplay(path: String) -> Never {
    let (catalog, _) = loadCatalogOrExit()
    guard let data = FileManager.default.contents(atPath: path) else {
        print("无法读取 \(path)"); exit(1)
    }
    var stream = JSONObjectStream()
    let objects = stream.append(data)
    let session = (path as NSString).lastPathComponent
    let events = replayEvents(objects, fileName: session).sorted { $0.ts < $1.ts }
    guard let first = events.first else { print("没有可用事件"); exit(0) }
    let config = RouterConfig()
    let router = ActivityRouter(config: config, now: first.ts)
    let withBubble = CommandLine.arguments.contains("--with-bubble")
    var bubble = HeldValue<StatusLine?>(nil, minHoldMs: 1200)
    var counts: [PetState: Int] = [:]
    func tick(_ t: Double) {
        if let s = router.tick(now: t) {
            counts[s, default: 0] += 1
            print("\(timeString(t))  显示 \(s.rawValue)（\(catalog.label(for: s))）")
        }
        guard withBubble else { return }
        let line = router.statusLine(now: t)
        guard bubble.update(line, now: t, immediate: (line == nil) != (bubble.value == nil)) else { return }
        if let l = bubble.value {
            let progress = l.progress.map { " \($0.done)/\($0.total)" } ?? ""
            print("\(timeString(t))  气泡 [\(l.title ?? "-")] \(l.current)\(progress)")
        } else {
            print("\(timeString(t))  气泡 隐藏")
        }
    }
    for (i, e) in events.enumerated() {
        router.ingest(e, now: e.ts)
        tick(e.ts)
        let next = i + 1 < events.count ? events[i + 1].ts : e.ts + config.completeArmMs + 3000
        // 事件之间：前 20 秒逐 100 ms 推进（覆盖防抖、保持、合并窗口、报告停留），之后跳到失联阈值。
        var t = e.ts + 100
        while t < next && t < e.ts + 20_000 { tick(t); t += 100 }
        let staleAt = e.ts + config.staleNoToolMs + 100
        if staleAt < next { tick(staleAt); tick(staleAt + config.debounceMs + 100) }
    }
    print("—— 共 \(events.count) 个事件；各状态出现次数：",
          PetState.allCases.compactMap { s in counts[s].map { "\(s.rawValue)=\($0)" } }.joined(separator: " "))
    exit(0)
}

/// --chat-link <会话 ID>：打印点举牌时会打开的链接（只查不开），用来确认转录会话认到了哪条聊天。
/// 会话 ID 就是 ~/.claude/projects/<项目>/<会话>.jsonl 的文件名。
func runChatLink(session: String) -> Never {
    let links = ClaudeSessionLinks()
    print("会话记录目录 \(links.sessionsDir.path)")
    guard let id = links.desktopSessionID(forTranscriptSession: session) else {
        print("没找到对应的聊天：点举牌只会把 Claude 带到前面（在终端里跑的会话就是这样）")
        exit(1)
    }
    print("对应聊天 \(id)")
    print("点击打开 \(ClaudeSessionLinks.chatURL(desktopSession: id)?.absoluteString ?? "-")")
    exit(0)
}

/// --open-chat：打印桌面版 Claude 此刻选中的那条聊天。
/// 这条聊天答完时雪绪不举牌——人已经看着它了，再举一块只是挡路。
/// 注意只有桌面版 Claude 在最前面时才算"开在眼前"，这里只查记录，不管谁在前台。
func runOpenChat() -> Never {
    let links = ClaudeSessionLinks()
    print("会话记录目录 \(links.sessionsDir.path)")
    guard let session = links.focusedTranscriptSession() else {
        print("认不出此刻开着哪条聊天：照常举牌")
        exit(1)
    }
    print("此刻开着的聊天 \(session)")
    let front = NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? "-"
    print("最前面的应用 \(front)\(front == "com.anthropic.claudefordesktop" ? "（算开在眼前，这条不举牌）" : "（没在看 Claude，照常举牌）")")
    exit(0)
}

/// --chats [秒]：列出最近的聊天（菜单“跟随的聊天”里的那一份），标出此刻会跟哪条。
/// 先跟着转录看几秒，免得只拿到启动那一瞬的样子。
func runChats(seconds: Double) -> Never {
    let feeds = AgentSources(provider: providerFromArgs())
    let start = nowMs()
    let router = ActivityRouter(now: start)
    for e in feeds.poll(now: start) { router.ingest(e, now: min(e.ts, start)) }
    router.settle(now: start)
    while nowMs() - start < seconds * 1000 {
        let now = nowMs()
        for e in feeds.poll(now: now) { router.ingest(e, now: min(e.ts, now)) }
        router.tick(now: now)
        Thread.sleep(forTimeInterval: 0.1)
    }
    let now = nowMs()
    for feed in feeds.statuses {
        print("\(feed.label)：目录 \(feed.path) 存在=\(feed.found) 追踪文件=\(feed.trackedFiles)")
    }
    let chats = router.sessionSummaries(now: now, quietWithinMs: 30 * 60 * 1000, limit: 10)
    if chats.isEmpty {
        print("最近没有聊天在跑")
        exit(0)
    }
    for c in chats {
        print("\(c.focused ? "→" : " ") \(c.id)  \(c.menuLabel)")
    }
    exit(0)
}

/// --watch <秒>：无窗口地实时跟随 Claude 转录，打印事件与状态切换（不打印任何对话内容）。
func runWatch(seconds: Double) -> Never {
    let (catalog, _) = loadCatalogOrExit()
    let feeds = AgentSources(provider: providerFromArgs())
    let start = nowMs()
    let router = ActivityRouter(now: start)
    for e in feeds.poll(now: start) { router.ingest(e, now: min(e.ts, start)) }
    router.settle(now: start)
    for feed in feeds.statuses {
        print("\(timeString(start))  \(feed.label)：目录 \(feed.path) 存在=\(feed.found) 追踪文件=\(feed.trackedFiles)")
    }
    print("\(timeString(start))  启动状态 \(router.displayed.rawValue)（\(catalog.label(for: router.displayed))） 会话 \(router.focusedSession?.prefix(8) ?? "-")")
    var focus = router.focusedSession
    while nowMs() - start < seconds * 1000 {
        let now = nowMs()
        for e in feeds.poll(now: now) {
            router.ingest(e, now: min(e.ts, now))
            let lag = now - e.ts
            print("\(timeString(now))  事件 [\(e.source) \(e.session.prefix(8))] \(describe(e))  写入延迟≈\(Int(lag)) ms")
        }
        if let s = router.tick(now: now) {
            print("\(timeString(now))  显示 \(s.rawValue)（\(catalog.label(for: s))）")
        }
        if router.focusedSession != focus {
            focus = router.focusedSession
            print("\(timeString(now))  跟随切到 [\(focus?.prefix(8) ?? "-")]")
        }
        Thread.sleep(forTimeInterval: 0.1)
    }
    exit(0)
}

// MARK: - 桌面播放器

/// 拎起来时那张图与窗口的摆放。图比常规帧高：领口被捏起的尖在头顶上方，两条腿垂到下面；
/// 上边缘与平时那块 192×208 对齐，所以抓起来的一瞬间头不会跳。窗口按最大倾角扫过的范围放大，
/// 晃到两边也不会被窗口切掉（多出来的部分是透明的，看不见）。
struct HangGeometry {
    let panelSize: NSSize
    /// 放大后的窗口左下角相对平时窗口左下角的位移（通常是负数）。
    let offset: NSPoint
    /// 图在视图里占的矩形，以及绕着转的那一点（都是视图坐标）。
    let spriteRect: NSRect
    let pivot: NSPoint

    /// sagRoom：身体最多能往下坠多少点，窗口底下要留出这段。
    static func make(petSize pet: NSSize, held spec: AnimationSpec, scale s: CGFloat, sagRoom: CGFloat = 0,
                     maxAngleDeg: Double = HangSwing.Tuning().maxAngleDeg) -> HangGeometry {
        let anchors = spec.hang ?? HangAnchors(gripX: Double(spec.frameWidth) / 2, gripY: 0, headTop: 0)
        let sprite = NSRect(x: (pet.width - CGFloat(spec.frameWidth) * s) / 2,
                            y: pet.height - CGFloat(spec.frameHeight) * s,
                            width: CGFloat(spec.frameWidth) * s,
                            height: CGFloat(spec.frameHeight) * s)
        let pivot = NSPoint(x: sprite.minX + CGFloat(anchors.gripX) * s,
                            y: sprite.maxY - CGFloat(anchors.gripY) * s)
        let limit = CGFloat(maxAngleDeg * .pi / 180)
        var box = sprite
        for i in -12...12 {
            box = box.union(rotate(sprite, around: pivot, by: limit * CGFloat(i) / 12))
        }
        box = box.insetBy(dx: -1, dy: -1)
        box = NSRect(x: box.minX, y: box.minY - sagRoom, width: box.width, height: box.height + sagRoom)
        return HangGeometry(panelSize: box.size,
                            offset: NSPoint(x: box.minX, y: box.minY),
                            spriteRect: sprite.offsetBy(dx: -box.minX, dy: -box.minY),
                            pivot: NSPoint(x: pivot.x - box.minX, y: pivot.y - box.minY))
    }

    /// 矩形绕一点旋转后的外接矩形。
    static func rotate(_ rect: NSRect, around p: NSPoint, by angle: CGFloat) -> NSRect {
        let c = cos(angle), s = sin(angle)
        var minX = CGFloat.greatestFiniteMagnitude, minY = minX
        var maxX = -CGFloat.greatestFiniteMagnitude, maxY = maxX
        for corner in [NSPoint(x: rect.minX, y: rect.minY), NSPoint(x: rect.maxX, y: rect.minY),
                       NSPoint(x: rect.minX, y: rect.maxY), NSPoint(x: rect.maxX, y: rect.maxY)] {
            let dx = corner.x - p.x, dy = corner.y - p.y
            let x = p.x + dx * c - dy * s, y = p.y + dx * s + dy * c
            minX = min(minX, x); maxX = max(maxX, x)
            minY = min(minY, y); maxY = max(maxY, y)
        }
        return NSRect(x: minX, y: minY, width: maxX - minX, height: maxY - minY)
    }
}


final class AppController: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private let catalog: AnimationCatalog
    private let library: SpriteLibrary
    private let router = ActivityRouter(now: nowMs())
    /// 跟着哪一家（Claude／DeepSeek／GPT，或三家都跟）的本机会话记录。菜单里换。
    private var feeds: AgentSources
    private let links = ClaudeSessionLinks()
    /// refreshOpenChat 的后台读取是否还在路上。
    private var openChatBusy = false
    private let defaults = UserDefaults.standard

    private var panel: PetPanel!
    private var view: PetView!
    private var bubble: BubblePanel!
    private var cardStack: CardStackPanel!
    private var statusItem: NSStatusItem!
    private var settingsWindow: SettingsPanelController?
    private var timer: Timer?
    private var tickCount = 0

    private var shownState: PetState = .idle
    private var stateTimeline: SpriteTimeline
    /// 被大手拎着时的摆动与图条；两个都是 nil 表示正常站／坐着。
    private var swing: HangSwing?
    private var heldTimeline: SpriteTimeline?
    private var hangGeo: HangGeometry?
    /// 松手的时刻；晃停或超时后放回原来的动作。
    private var releasedAt: Double?
    /// 气泡正在显示的内容。出现和消失立即生效；内容变化每段至少停留 1.2 秒，连续读几个文件时不逐个闪过。
    private var bubbleHold = HeldValue<StatusLine?>(nil, minHoldMs: 1200)
    /// 旁边那叠卡正在显示的内容。多一条少一条立刻生效，卡上的字跟气泡一样至少停留 1.2 秒。
    private var cardsHold = HeldValue<[ActivityCard]>([], minHoldMs: 1200)
    /// 这摞卡展开着没有（平时收起，只有头顶那张气泡）。
    private var cardsExpanded = false
    /// 展开的时刻：一阵没人点就自己收起来。
    private var cardsExpandedAt: Double = 0
    private static let cardsAutoCollapseMs: Double = 12_000

    private struct Simulation {
        let start: Double
        let steps: [DemoScript.Step]
        var next = 0
        let router: ActivityRouter
    }
    private var simulation: Simulation?

    private var following: Bool {
        get { defaults.object(forKey: "followClaude") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "followClaude") }
    }
    private var scale: CGFloat {
        // 设置坏掉或来自旧版本时夹回滑条的范围，不会出现 0 或大得离谱的雪绪。
        get { CGFloat(ScaleSliderView.snap(defaults.object(forKey: "scale") as? Double ?? 1.0)) }
        set { defaults.set(Double(newValue), forKey: "scale") }
    }
    private var showBubble: Bool {
        get { defaults.object(forKey: "showBubble") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "showBubble") }
    }
    private var showCards: Bool {
        get { defaults.object(forKey: "showCards") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "showCards") }
    }
    /// 跟随哪一家助手：默认三家都跟，菜单「Assistant」里挑。和 Windows 版用同一个设置键。
    private var provider: AgentProvider {
        get { AgentProvider(code: defaults.string(forKey: "source")) }
        set { defaults.set(newValue.rawValue, forKey: "source") }
    }
    /// 界面语言：默认英文，菜单「Language」里切换；已经写进事件里的说明到下一条事件才换。
    private var language: UILanguage {
        get { UILanguage(code: defaults.string(forKey: "language")) }
        set { defaults.set(newValue.rawValue, forKey: "language"); L10n.language = newValue }
    }

    init(catalog: AnimationCatalog, library: SpriteLibrary) {
        // 先定语言，再回放会话记录：回放时生成的说明文字才是对的语言。
        L10n.language = UILanguage(code: UserDefaults.standard.string(forKey: "language"))
        self.catalog = catalog
        self.library = library
        self.feeds = AgentSources(provider: AgentProvider(code: UserDefaults.standard.string(forKey: "source")))
        self.stateTimeline = SpriteTimeline(spec: catalog.spec(for: .idle), now: nowMs())
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let now = nowMs()
        // 先恢复此刻的活动，再显示窗口：第一帧就是正确动作。
        for e in feeds.poll(now: now) { router.ingest(e, now: min(e.ts, now)) }
        router.settle(now: now)
        shownState = following ? router.displayed : .idle
        stateTimeline = SpriteTimeline(spec: catalog.spec(for: shownState), now: now)

        setUpWindow()
        setUpStatusItem()
        render()
        panel.orderFrontRegardless()
        setUpBubble()
        updateBubble(now: now)
        setUpCards()
        updateCards(now: now)

        // 30 Hz：小幅动作一帧约 67 ms、眨眼一帧 50–110 ms，都能按时换帧。
        let t = Timer(timeInterval: 1.0 / 30, repeats: true) { [weak self] _ in self?.tick() }
        t.tolerance = 0.005
        RunLoop.main.add(t, forMode: .common)
        timer = t

        NotificationCenter.default.addObserver(
            forName: NSApplication.didChangeScreenParametersNotification, object: nil, queue: .main
        ) { [weak self] _ in self?.screensChanged() }

        if CommandLine.arguments.contains("--demo") { startDemo() }
    }

    // MARK: 窗口

    private var petSize: NSSize {
        NSSize(width: 192 * scale, height: 208 * scale)
    }

    private func setUpWindow() {
        panel = PetPanel(size: petSize)
        view = PetView(frame: NSRect(origin: .zero, size: petSize))
        panel.contentView = view
        panel.setFrameOrigin(restoredOrigin())

        view.onClick = { [weak self] in self?.petClicked() }
        view.onDragBegan = { [weak self] in self?.dragBegan() }
        view.onDragOriginChanged = { [weak self] in self?.panel.frame.origin ?? .zero }
        view.onDragEnded = { [weak self] in self?.dragEnded() }
        // 桌宠本体是设置的最快入口：右键或 Control-点击直接打开，不再多走一层菜单。
        // 完整操作菜单仍可从菜单栏头像或再次打开 App 进入。
        view.onContextMenu = { [weak self] _ in self?.showSettings() }
    }

    private func defaultOrigin() -> NSPoint {
        let vf = (NSScreen.main ?? NSScreen.screens[0]).visibleFrame
        return NSPoint(x: vf.maxX - petSize.width - 24, y: vf.minY + 12)
    }

    private func restoredOrigin() -> NSPoint {
        guard let x = defaults.object(forKey: "originX") as? Double,
              let y = defaults.object(forKey: "originY") as? Double else { return defaultOrigin() }
        let frame = NSRect(origin: NSPoint(x: x, y: y), size: petSize)
        // 显示器拔掉或排列变化后，保存的位置可能已不在任何屏幕上。
        return NSScreen.screens.contains(where: { $0.visibleFrame.intersects(frame) }) ? frame.origin : defaultOrigin()
    }

    /// 把一块窗口挪回它所在那块屏幕里。拎着时窗口是放大的，传入的始终是平时那块 192×208。
    private func clamped(_ f: NSRect) -> NSRect {
        let center = NSPoint(x: f.midX, y: f.midY)
        let screen = NSScreen.screens.first(where: { $0.frame.contains(center) }) ?? NSScreen.main ?? NSScreen.screens[0]
        let vf = screen.visibleFrame
        let x = min(max(f.minX, vf.minX), vf.maxX - f.width)
        let y = min(max(f.minY, vf.minY), vf.maxY - f.height)
        return NSRect(origin: NSPoint(x: x, y: y), size: f.size)
    }

    private func clampToScreen() {
        panel.setFrameOrigin(clamped(panel.frame).origin)
    }

    /// 接显示器、拔显示器、改分辨率：她可能整个落在屏幕外（拔掉外接屏最容易撞上），
    /// 那样点应用也只会被“单实例”挡掉，看着就像打不开。屏幕一变就把她挪回来。
    private func screensChanged() {
        finishHang()
        let f = panel.frame
        if !NSScreen.screens.contains(where: { $0.visibleFrame.intersects(f) }) {
            panel.setFrameOrigin(defaultOrigin())
        } else {
            clampToScreen()
        }
        savePosition()
        positionBubble()
        positionCards()
    }

    private func savePosition(_ origin: NSPoint? = nil) {
        let o = origin ?? panel.frame.origin
        defaults.set(Double(o.x), forKey: "originX")
        defaults.set(Double(o.y), forKey: "originY")
    }

    private func applyScale(_ s: CGFloat) {
        finishHang()
        let old = panel.frame
        scale = s
        let size = petSize
        // 以脚下中点为锚：缩放后落脚点不跳。
        let origin = NSPoint(x: old.midX - size.width / 2, y: old.minY)
        panel.setFrame(NSRect(origin: origin, size: size), display: true)
        view.frame = NSRect(origin: .zero, size: size)
        clampToScreen()
        savePosition()
        positionBubble()
        positionCards()
    }

    // MARK: 点击举着的牌子：跳到对应的聊天

    /// 举着牌子时点雪绪：打开这块牌子对应的那条 Claude 聊天。
    /// 勾选卡点完放下（那一轮已经结束）；问号卡不放下——问题还等着你答，卡片等你答完自己收。
    /// 其余状态点击不做事。
    private func petClicked() {
        let now = nowMs()
        if let sim = simulation {
            // 演示里没有真实会话可跳，只把牌子放下。
            sim.router.dismissCompletion(now: now)
            return
        }
        guard following else { return }
        if shownState == .task_complete, let session = router.completedSession {
            openChat(session: session)
            router.dismissCompletion(now: now)
            return
        }
        if shownState == .question_for_user, let session = router.askingSession {
            openChat(session: session)
        }
    }

    /// 用各家桌面版自己注册的深链打开这条聊天。认不出会话时（例如在终端里跑的），
    /// 至少把那个应用带到前面，不乱跳到别的聊天。
    private func openChat(session: String) {
        switch AgentProvider.owner(ofSource: router.sourceOfSession(session) ?? "") {
        case .gpt:
            // Codex 桌面版（ChatGPT.app，标识 com.openai.codex）注册的深链。
            // 会话 ID 就是记录文件名里的那个，应用自己的日志里叫 threadId，两边是同一个。
            if let url = URL(string: "codex://threads/\(session)") {
                NSWorkspace.shared.open(url)
                return
            }
            activate(Self.codexBundleID)
        case .deepseek:
            // Deep Code 跑在终端里，没有可跳的窗口：只放下牌子。
            break
        default:
            if let url = links.chatURL(forTranscriptSession: session) {
                NSWorkspace.shared.open(url)
                return
            }
            activate(Self.claudeBundleID)
        }
    }

    /// 举着的牌子能不能点回那条聊天（Deep Code 没有窗口可跳）。
    private func canOpenChat(session: String?) -> Bool {
        guard let session else { return false }
        return AgentProvider.owner(ofSource: router.sourceOfSession(session) ?? "") != .deepseek
    }

    private func activate(_ bundleID: String) {
        guard let app = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bundleID) else { return }
        NSWorkspace.shared.openApplication(at: app, configuration: NSWorkspace.OpenConfiguration())
    }

    private static let claudeBundleID = "com.anthropic.claudefordesktop"
    private static let codexBundleID = "com.openai.codex"

    // MARK: 拖动：被一只看不见的大手拎起来

    private var heldSpec: AnimationSpec { catalog.specs[AnimationCatalog.heldID]! }

    /// 松手后最多再晃这么久就放下：万一参数改得收敛很慢，也不会一直挂着。
    private static let hangSettleLimitMs: Double = 2400

    /// 放大的窗口换算回平时那块 192×208。
    private func normalFrame() -> NSRect {
        guard let geo = hangGeo else { return panel.frame }
        let f = panel.frame
        return NSRect(origin: NSPoint(x: f.minX - geo.offset.x, y: f.minY - geo.offset.y), size: petSize)
    }

    private func dragBegan() {
        let now = nowMs()
        // 上一次还在晃就又被抓住：窗口已经是放大的，只要把手重新握上。
        if swing != nil {
            releasedAt = nil
            swing?.grab()
            return
        }
        let geo = HangGeometry.make(petSize: petSize, held: heldSpec, scale: scale,
                                    sagRoom: library.hangLength * scale * CGFloat(HangSwing.Tuning().maxSagRatio))
        hangGeo = geo
        let f = panel.frame
        panel.setFrame(NSRect(origin: NSPoint(x: f.minX + geo.offset.x, y: f.minY + geo.offset.y),
                              size: geo.panelSize), display: false)
        view.frame = NSRect(origin: .zero, size: geo.panelSize)
        swing = HangSwing(now: now, length: Double(library.hangLength * scale))
        heldTimeline = SpriteTimeline(spec: heldSpec, now: now)
        releasedAt = nil
        render()
        positionBubble()
        positionCards()
        updateStatusTitle()
    }

    private func dragEnded() {
        guard swing != nil else { return }
        // 贴边和保存位置都按平时那块算；放大的窗口跟着挪同样的距离。
        let normal = clamped(normalFrame())
        if let geo = hangGeo {
            panel.setFrameOrigin(NSPoint(x: normal.minX + geo.offset.x, y: normal.minY + geo.offset.y))
        }
        savePosition(normal.origin)
        swing?.release()
        releasedAt = nowMs()
        positionBubble()
        positionCards()
    }

    /// 晃停了（或超时、要改大小了）：窗口还原成平时那块，切回当前活动的动作。
    private func finishHang() {
        guard swing != nil else { return }
        let normal = normalFrame()
        swing = nil
        heldTimeline = nil
        hangGeo = nil
        releasedAt = nil
        panel.setFrame(normal, display: false)
        view.frame = NSRect(origin: .zero, size: normal.size)
        render()
        positionBubble()
        positionCards()
        updateStatusTitle()
    }

    // MARK: 主循环

    /// 桌面版 Claude 就在最前面时，把它此刻选中的那条聊天告诉路由——那条不举牌。
    /// 人没在看 Claude 时直接给 nil，连记录都不用翻。
    ///
    /// 翻记录是文件读取，放到后台做，别让 30 Hz 的动作掉帧；上一次还没回来就跳过这一轮。
    private func refreshOpenChat() {
        let front = NSWorkspace.shared.frontmostApplication?.bundleIdentifier
        guard front == "com.anthropic.claudefordesktop" else {
            router.openChatSession = nil
            return
        }
        guard !openChatBusy else { return }
        openChatBusy = true
        let links = self.links
        DispatchQueue.global(qos: .utility).async {
            let session = links.focusedTranscriptSession()
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.openChatBusy = false
                // 回来的路上人可能已经切走了，那就不算"开在眼前"。
                if NSWorkspace.shared.frontmostApplication?.bundleIdentifier == "com.anthropic.claudefordesktop" {
                    self.router.openChatSession = session
                } else {
                    self.router.openChatSession = nil
                }
            }
        }
    }

    private func tick() {
        let now = nowMs()
        tickCount += 1
        // 约每 2 秒看一次"此刻开着哪条聊天"。
        if tickCount % 60 == 0 { refreshOpenChat() }
        if tickCount % 8 == 0 {
            // 约每 0.27 秒读一次会话记录。事件始终进入路由器；暂停跟随只影响显示。
            for e in feeds.poll(now: now) { router.ingest(e, now: min(e.ts, now)) }
        }
        router.tick(now: now)

        if var sim = simulation {
            let elapsed = now - sim.start
            while sim.next < sim.steps.count && sim.steps[sim.next].offsetMs <= elapsed {
                var e = sim.steps[sim.next].event
                e.ts = now
                sim.router.ingest(e, now: now)
                sim.next += 1
            }
            sim.router.tick(now: now)
            simulation = sim
            if elapsed > DemoScript.durationMs { stopDemo() }
        }

        let target: PetState = simulation?.router.displayed ?? (following ? router.displayed : .idle)
        if target != shownState {
            shownState = target
            stateTimeline = SpriteTimeline(spec: catalog.spec(for: target), now: now)
            // 站着和坐着的头顶线不一样（待机是站姿，比坐着高一截），气泡与卡叠跟着重贴。
            positionBubble()
            positionCards()
            updateStatusTitle()
        }
        stateTimeline.advance(to: now)
        if let geo = hangGeo {
            // 手的横向位置就是抓手那一点在屏幕上的位置；30 Hz 采一次，摆动按它的加速度算。
            swing?.advance(to: now,
                           handX: Double(panel.frame.minX + geo.pivot.x),
                           handY: Double(panel.frame.minY + geo.pivot.y))
            heldTimeline?.advance(to: now)
            if let released = releasedAt,
               swing?.settled == true || now - released > Self.hangSettleLimitMs {
                finishHang()
            }
        }
        render()
        updateMousePassThrough()
        updateBubble(now: now)
        updateCards(now: now)
        if tickCount % 15 == 0, settingsWindow?.window?.isVisible == true {
            refreshSettingsPanel()
        }
    }

    private func render() {
        if let held = heldTimeline, let geo = hangGeo, let swing {
            // 坠下去时整张图往下挪，旋转中心仍是抓手那一点（相当于那截布被拉长了）。
            view.show(library.frame(held.spec.id, held.frame),
                      SpritePlacement(rect: geo.spriteRect.offsetBy(dx: 0, dy: -CGFloat(swing.sag)),
                                      pivot: geo.pivot, angle: CGFloat(swing.angle)))
        } else {
            view.show(library.frame(stateTimeline.spec.id, stateTimeline.frame), .filling(view.bounds))
        }
    }

    private func updateMousePassThrough() {
        let m = NSEvent.mouseLocation
        if let bubble {
            // 平时气泡照旧穿透；有别的聊天可挑（或正摊开着）时才收点击。
            let canTap = following && simulation == nil && (cardsExpanded || !cardsHold.value.isEmpty)
            let overBubble = canTap && bubble.alphaValue > 0.5 && bubble.frame.contains(m)
            if bubble.ignoresMouseEvents == overBubble { bubble.ignoresMouseEvents = !overBubble }
        }
        if let cardStack {
            // 卡片上（含 ✕ 和“还有 N 条”）才收点击，卡与卡之间的缝隙照样穿透。
            let c = cardStack.frame
            let overCard = cardStack.alphaValue > 0.5 && c.contains(m)
                && cardStack.stackView.hit(at: NSPoint(x: m.x - c.minX, y: m.y - c.minY)) != nil
            if cardStack.ignoresMouseEvents == overCard { cardStack.ignoresMouseEvents = !overCard }
        }
        if view.dragging { panel.ignoresMouseEvents = false; return }
        let f = panel.frame
        let over = f.contains(m) && view.isOpaque(at: NSPoint(x: m.x - f.minX, y: m.y - f.minY))
        if panel.ignoresMouseEvents == over { panel.ignoresMouseEvents = !over }
    }

    // MARK: 头顶气泡

    private func setUpBubble() {
        bubble = BubblePanel()
        // 子窗口：拖动雪绪时跟着走。
        panel.addChildWindow(bubble, ordered: .above)
        // 点头顶这张卡＝摊开挑聊天。点雪绪本人仍是“跳到那条聊天并放下牌子”，两处不打架。
        bubble.bubbleView.onClick = { [weak self] in self?.toggleCards() }
    }

    /// 上次摆放气泡时是否被拎着。拎起和放下时各重新摆一次。
    private var bubblePlacedForHang = false

    private func updateBubble(now: Double) {
        if (swing != nil) != bubblePlacedForHang { positionBubble(); positionCards() }
        let source: ActivityRouter? = simulation?.router ?? (following ? router : nil)
        let line = showBubble ? source?.statusLine(now: now) : nil
        let visibilityChanged = (line == nil) != (bubbleHold.value == nil)
        guard bubbleHold.update(line, now: now, immediate: visibilityChanged) else { return }
        if let line = bubbleHold.value {
            bubble.bubbleView.layout = BubbleLayout(line)
            positionBubble()
            fadeBubble(to: 1)
        } else {
            fadeBubble(to: 0)   // 内容留着，让它淡出去而不是瞬间消失
        }
        // 上面那摞卡压着气泡放，气泡一变高矮或隐去就跟着挪。
        positionCards()
    }

    private func positionBubble() {
        bubblePlacedForHang = swing != nil
        guard let bubble, let size = bubble.bubbleView.layout?.size else { return }
        // 被拎着时图更高，气泡改贴在被捏起的领口上方；晃动时气泡不跟着歪，免得字在抖。
        var pet = panel.frame
        var headTop = library.headTopInset(for: stateTimeline.spec.id)
        if let geo = hangGeo, swing != nil {
            pet = geo.spriteRect.offsetBy(dx: panel.frame.minX, dy: panel.frame.minY)
            headTop = CGFloat(heldSpec.hang?.gripY ?? 0)
        }
        var origin = BubbleLayout.origin(size: size, petFrame: pet, headTop: headTop * scale)
        if let vf = (panel.screen ?? NSScreen.main)?.visibleFrame {
            // 雪绪靠近屏幕边缘时气泡仍留在屏幕内（顶到上边时会压在头上）。
            origin.x = min(max(origin.x, vf.minX + 4), vf.maxX - size.width - 4)
            origin.y = min(origin.y, vf.maxY - size.height - 2)
        }
        bubble.setFrame(NSRect(origin: origin, size: size), display: true)
    }

    private func fadeBubble(to alpha: CGFloat) {
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.18
            self.bubble.animator().alphaValue = alpha
        }
    }

    // MARK: 旁边那叠通知卡

    private func setUpCards() {
        cardStack = CardStackPanel()
        panel.addChildWindow(cardStack, ordered: .above)
        cardStack.stackView.onOpen = { [weak self] i in self?.cardTapped(i, pick: true) }
        cardStack.stackView.onDismiss = { [weak self] i in self?.cardTapped(i, pick: false) }
        cardStack.stackView.onToggleExpand = { [weak self] in self?.toggleCards() }
        cardStack.stackView.onPickAuto = { [weak self] in
            guard let self else { return }
            self.router.pinSession(nil, now: nowMs())
            self.collapseCards()
        }
        cardStack.stackView.onContextMenu = { [weak self] i, event in
            guard let self, let card = self.cardsHold.value[safe: i] else { return }
            let menu = NSMenu()
            menu.addItem(self.info(card.title))
            let open = self.action(tr("Open this chat", "打开这条聊天"), #selector(self.menuOpenListedChat(_:)))
            open.representedObject = card.session
            menu.addItem(open)
            let mute = self.action(tr("Stop reminding about this chat", "不再提醒这条聊天"), #selector(self.menuMuteChat(_:)))
            mute.representedObject = card.session
            menu.addItem(mute)
            NSMenu.popUpContextMenu(menu, with: event, for: self.cardStack.stackView)
        }
    }

    /// 点了摊开的第 i 张卡：pick=true 把她换到那条聊天（顶掉原来那条），否则只收起这一张提醒。
    private func cardTapped(_ i: Int, pick: Bool) {
        guard simulation == nil, let card = cardsHold.value[safe: i] else { return }
        let now = nowMs()
        if pick {
            router.pinSession(card.session, now: now)
            collapseCards()
            return
        }
        router.dismissCard(session: card.session, now: now)
        updateCards(now: now, immediate: true)
    }

    /// 点头顶那张卡（或“还有 N 条”）：摊开挑聊天；再点一下收起。
    /// 点雪绪本人还是“跳到那条聊天并放下牌子”，两处各管各的。
    private func toggleCards() {
        guard simulation == nil, following else { return }
        if cardsExpanded { collapseCards(); return }
        guard !router.cards(now: nowMs()).isEmpty else { return }
        cardsExpanded = true
        cardsExpandedAt = nowMs()
        updateCards(now: nowMs(), immediate: true)
    }

    private func collapseCards() {
        cardsExpanded = false
        updateCards(now: nowMs(), immediate: true)
    }

    private func updateCards(now: Double, immediate: Bool = false) {
        guard let cardStack else { return }
        let cards = (showCards && following && simulation == nil) ? router.cards(now: now) : []
        if cards.isEmpty { cardsExpanded = false }
        // 摊开后一阵没人点就自己收起来，免得一直挡着。
        if cardsExpanded, now - cardsExpandedAt > Self.cardsAutoCollapseMs { cardsExpanded = false }
        // 多一条少一条立刻生效；只是卡上的字变了就按最短停留，免得一直闪。
        let appeared = cards.map(\.session) != cardsHold.value.map(\.session)
        guard cardsHold.update(cards, now: now, immediate: immediate || appeared) else { return }
        let value = cardsHold.value
        guard !value.isEmpty else {
            fade(cardStack, to: 0)
            return
        }
        let anchor = cardsAnchor()
        let layout = CardStackLayout(cards: value, expanded: cardsExpanded,
                                     pinned: router.pinnedSession != nil,
                                     maxHeight: anchor.visible.maxY - anchor.bubbleTop - CardLook.stackGap - 6)
        cardStack.stackView.layout = layout
        positionCards(layout)
        fade(cardStack, to: 1)
    }

    /// 雪绪挪了、变大小了、被拎起放下了：照当前这叠重摆一次。
    private func positionCards() {
        guard let layout = cardStack?.stackView.layout else { return }
        positionCards(layout)
    }

    /// 这摞卡从哪儿往上长：气泡的上边（气泡关掉或没内容时用头顶线），以及这块屏幕的可见范围。
    private func cardsAnchor() -> (pet: NSRect, bubbleTop: CGFloat, visible: NSRect) {
        let visible = (panel.screen ?? NSScreen.main)?.visibleFrame
            ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
        var pet = panel.frame
        var headTop = library.headTopInset(for: stateTimeline.spec.id)
        if let geo = hangGeo, swing != nil {
            pet = geo.spriteRect.offsetBy(dx: panel.frame.minX, dy: panel.frame.minY)
            headTop = CGFloat(heldSpec.hang?.gripY ?? 0)
        }
        let bubbleTop = (bubble?.alphaValue ?? 0) > 0.01 && bubble.bubbleView.layout != nil
            ? bubble.frame.maxY : pet.maxY - headTop * scale + 3
        return (pet, bubbleTop, visible)
    }

    private func positionCards(_ layout: CardStackLayout) {
        guard let cardStack, layout.size.height > 0 else { return }
        let a = cardsAnchor()
        let origin = CardStackLayout.origin(size: layout.size, petFrame: a.pet,
                                            bubbleTop: a.bubbleTop, visible: a.visible)
        cardStack.setFrame(NSRect(origin: origin, size: layout.size), display: true)
    }

    private func fade(_ window: NSWindow, to alpha: CGFloat) {
        guard window.alphaValue != alpha else { return }
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.18
            window.animator().alphaValue = alpha
        }
    }

    @objc private func menuOpenListedChat(_ sender: NSMenuItem) {
        guard let id = sender.representedObject as? String else { return }
        openChat(session: id)
        collapseCards()
    }

    @objc private func menuMuteChat(_ sender: NSMenuItem) {
        guard let id = sender.representedObject as? String else { return }
        router.muteCards(session: id)
        updateCards(now: nowMs(), immediate: true)
    }

    // MARK: 模拟演示

    private func startDemo() {
        let now = nowMs()
        simulation = Simulation(start: now, steps: DemoScript.steps(session: "demo", start: now),
                                router: ActivityRouter(now: now))
        updateStatusTitle()
    }

    private func stopDemo() {
        simulation = nil
        updateStatusTitle()
    }

    // MARK: 菜单栏

    private func setUpStatusItem() {
        // 新图标默认排在最左边；刘海屏菜单栏满时会被系统挤到屏幕外（本机实测 x=0，不可见）。
        // 首次运行时把首选位置设在靠右处（距右边缘的点数）；之后用户按住 ⌘ 拖动的位置由系统记住。
        let autosave = "yukio"
        let key = "NSStatusItem Preferred Position \(autosave)"
        if defaults.object(forKey: key) == nil { defaults.set(260.0, forKey: key) }
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.autosaveName = autosave
        statusItem.isVisible = true
        let menu = NSMenu()
        menu.delegate = self
        statusItem.menu = menu
        updateStatusTitle()
    }

    private lazy var statusIcon: NSImage? = library.avatarImage().map {
        NSImage(cgImage: $0, size: NSSize(width: 18, height: 18))
    }

    private func updateStatusTitle() {
        guard let button = statusItem?.button else { return }
        if let icon = statusIcon {
            // 只放头像：比文字窄，刘海屏菜单栏拥挤时更不容易被挤到刘海下面。
            button.image = icon
            button.imagePosition = simulation != nil ? .imageLeft : .imageOnly
            button.title = simulation != nil ? tr("demo", "模拟") : ""
        } else {
            button.title = simulation != nil ? tr("Yukio · demo", "雪绪·模拟") : tr("Yukio", "雪绪")
        }
        button.toolTip = tr("Yukio: ", "雪绪：") + (swing != nil ? L10n.heldName : L10n.stateName(shownState))
    }

    /// 再次打开 Yukio.app（Finder、Spotlight、open 命令）时，在雪绪身旁弹出菜单。
    /// 菜单栏被挤满、图标被刘海遮住时，这是一定能用的完整菜单入口；右键雪绪则直接打开设置。
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        NSApp.activate(ignoringOtherApps: true)
        buildMenu().popUp(positioning: nil, at: NSPoint(x: view.bounds.midX, y: view.bounds.maxY), in: view)
        return false
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        for item in buildMenu().items {
            item.menu?.removeItem(item)
            menu.addItem(item)
        }
    }

    private func info(_ title: String) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        item.isEnabled = false
        return item
    }

    /// 菜单里列多久之内的聊天、最多几条。
    private static let chatListWindowMs: Double = 30 * 60 * 1000
    private static let chatListLimit = 10

    /// “跟随的聊天”子菜单：多个聊天同时跑时挑一条跟。
    /// 默认自动——谁答完、谁在等你拿主意就先给你看，都没有时跟最近在干活的那条。
    private func chatPickerItem(_ chats: [SessionSummary]) -> NSMenuItem {
        let live = chats.filter(\.live).count
        let wants = chats.filter(\.wantsYou).count
        // 标题顺带报数：有几条在等你，没人等你时报有几条在跑。
        let title: String
        if wants > 0 {
            title = tr("Chat to follow (\(wants) waiting for you)", "跟随的聊天（\(wants) 条等你）")
        } else if live > 1 {
            title = tr("Chat to follow (\(live) running)", "跟随的聊天（\(live) 条在跑）")
        } else {
            title = tr("Chat to follow", "跟随的聊天")
        }
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        let sub = NSMenu()
        let auto = action(tr("Auto (done and questions first)", "自动（完成和提问优先）"), #selector(menuPickChat(_:)), on: router.pinnedSession == nil)
        auto.representedObject = ""
        sub.addItem(auto)
        sub.addItem(.separator())
        if chats.isEmpty {
            sub.addItem(info(tr("No recent chats", "最近没有聊天在跑")))
        }
        for c in chats {
            let row = action(c.menuLabel, #selector(menuPickChat(_:)))
            row.representedObject = c.id
            // 挑定的那条打勾；自动模式下此刻跟着的那条画一横。
            row.state = c.pinned ? .on : (c.focused ? .mixed : .off)
            sub.addItem(row)
        }
        item.submenu = sub
        return item
    }

    /// 大小滑条那一行。菜单每次打开都重新建，滑块停在当前大小上。
    private func scaleSliderItem() -> NSMenuItem {
        let item = NSMenuItem()
        item.view = ScaleSliderView(scale: scale) { [weak self] s in self?.applyScale(s) }
        return item
    }

    /// 「Language」子菜单：English／中文，默认英文，选择存在设置里。
    /// 「跟随的助手」：Claude／DeepSeek／GPT，或三家都跟。换一家要把路由器清空重来。
    private func assistantItem() -> NSMenuItem {
        let item = NSMenuItem(title: tr("Assistant", "跟随的助手"), action: nil, keyEquivalent: "")
        let sub = NSMenu()
        let found = Dictionary(feeds.statuses.map { ($0.provider, $0.found) }, uniquingKeysWith: { a, _ in a })
        for p in AgentProvider.allCases {
            let row = action(p.displayName, #selector(menuSetProvider(_:)), on: provider == p)
            row.representedObject = p.rawValue
            // 这一家的记录目录不在（没装、或还没跑过）时标一下，免得以为坏了。
            if p != .auto, provider == p, found[p] == false {
                row.title += tr(" — no session logs yet", " — 还没有会话记录")
            }
            sub.addItem(row)
        }
        item.submenu = sub
        return item
    }

    private func languageItem() -> NSMenuItem {
        let item = NSMenuItem(title: tr("Language", "语言"), action: nil, keyEquivalent: "")
        let sub = NSMenu()
        for (code, name) in [(UILanguage.english, "English"), (UILanguage.chinese, "中文")] {
            let row = action(name, #selector(menuSetLanguage(_:)), on: language == code)
            row.representedObject = code.rawValue
            sub.addItem(row)
        }
        item.submenu = sub
        return item
    }

    private func currentSettingsSnapshot() -> SettingsSnapshot {
        let chats = simulation == nil
            ? router.sessionSummaries(now: nowMs(), quietWithinMs: Self.chatListWindowMs, limit: Self.chatListLimit)
            : []
        let activity = swing != nil ? L10n.heldName : L10n.stateName(shownState)
        let status: String
        if simulation != nil {
            status = tr("Demo · \(activity)", "模拟演示 · \(activity)")
        } else if !following {
            status = tr("Following paused", "已暂停跟随")
        } else {
            let names = feeds.statuses.filter(\.found).map(\.label).joined(separator: " + ")
            status = names.isEmpty
                ? tr("No local session logs found", "尚未找到本机会话记录")
                : tr("Following \(names) · \(activity)", "正在跟随 \(names) · \(activity)")
        }
        return SettingsSnapshot(status: status,
                                following: following,
                                provider: provider,
                                chats: chats,
                                showBubble: showBubble,
                                showCards: showCards,
                                scale: scale,
                                language: language,
                                demoPlaying: simulation != nil)
    }

    private func showSettings() {
        let controller: SettingsPanelController
        if let existing = settingsWindow {
            controller = existing
        } else {
            controller = SettingsPanelController()
            controller.onChange = { [weak self] change in self?.applySettings(change) }
            settingsWindow = controller
        }
        controller.show(snapshot: currentSettingsSnapshot(), near: panel.frame)
    }

    private func refreshSettingsPanel() {
        guard let controller = settingsWindow, controller.window?.isVisible == true else { return }
        controller.apply(currentSettingsSnapshot())
    }

    private func switchProvider(to picked: AgentProvider) {
        guard picked != provider else { return }
        provider = picked
        let now = nowMs()
        // 挑定的聊天、举着的牌子都属于上一家：整个清空，再从新的一家重新回放。
        router.reset(now: now)
        feeds.switchTo(picked)
        for e in feeds.poll(now: now) { router.ingest(e, now: min(e.ts, now)) }
        router.settle(now: now)
        cardsExpanded = false
        updateBubble(now: now)
        updateCards(now: now, immediate: true)
        updateStatusTitle()
    }

    private func resetPetPosition() {
        finishHang()
        panel.setFrameOrigin(defaultOrigin())
        savePosition()
        positionBubble()
        positionCards()
    }

    private func applySettings(_ change: SettingsChange) {
        switch change {
        case .following(let value):
            following = value
        case .provider(let picked):
            switchProvider(to: picked)
        case .chat(let id):
            _ = router.pinSession(id, now: nowMs())
        case .showBubble(let value):
            showBubble = value
            updateBubble(now: nowMs())
        case .showCards(let value):
            showCards = value
            updateCards(now: nowMs(), immediate: true)
        case .scale(let value):
            applyScale(value)
        case .language(let value):
            language = value
            updateStatusTitle()
        case .resetPosition:
            resetPetPosition()
        case .toggleDemo:
            simulation == nil ? startDemo() : stopDemo()
        }
        refreshSettingsPanel()
    }

    private func action(_ title: String, _ selector: Selector, key: String = "", on: Bool? = nil) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: selector, keyEquivalent: key)
        item.target = self
        if let on { item.state = on ? .on : .off }
        return item
    }

    private func buildMenu() -> NSMenu {
        let menu = NSMenu()
        let chats = simulation == nil ? router.sessionSummaries(now: nowMs(), quietWithinMs: Self.chatListWindowMs,
                                                                limit: Self.chatListLimit) : []
        menu.addItem(info(tr("Yukio", "雪绪") + " · " + (swing != nil ? L10n.heldName : L10n.stateName(shownState))))
        if simulation == nil, following, let done = router.completedSession {
            if canOpenChat(session: done) {
                menu.addItem(action(tr("Open this chat and lower the sign", "打开这条聊天并放下牌子"), #selector(menuOpenChat)))
            }
            menu.addItem(action(tr("Lower the sign, don't open the chat", "先放下牌子，不打开聊天"), #selector(menuDropSign)))
        } else if simulation == nil, following, canOpenChat(session: router.askingSession) {
            // 问号卡不收：答完之后它自己收，这里只把聊天打开。
            menu.addItem(action(tr("Open this chat to answer", "打开这条聊天去回答"), #selector(menuOpenChat)))
        }
        if simulation != nil {
            menu.addItem(info(tr("Playing the demo (not real Claude activity)", "正在播放模拟演示（不是真实 Claude 活动）")))
        } else if !following {
            menu.addItem(info(tr("Following paused, staying idle", "已暂停跟随，保持空闲")))
        } else if !feeds.anyFound {
            for feed in feeds.statuses {
                menu.addItem(info(tr("Not found: \(feed.path)", "未找到 \(feed.path)")))
            }
        } else {
            let names = feeds.statuses.filter(\.found).map(\.label).joined(separator: " + ")
            menu.addItem(info(tr("Following \(names) (read-only session logs)", "跟随 \(names)（只读本机会话记录）")))
            if let focused = chats.first(where: \.focused) {
                menu.addItem(info(tr("Following: ", "正在跟：") + focused.menuLabel + (focused.pinned ? tr(" (pinned)", "（挑定的）") : "")))
            }
            if let hooks = feeds.hooks, hooks.isPresent {
                menu.addItem(info(tr("Claude hooks inbox: \(hooks.eventsReceived) events received", "Claude hooks 收件箱：已收到 \(hooks.eventsReceived) 个事件")))
            }
        }
        menu.addItem(.separator())
        if simulation != nil {
            menu.addItem(action(tr("Stop demo", "停止模拟演示"), #selector(menuStopDemo)))
        }
        menu.addItem(action(tr("Follow assistant activity", "跟随助手活动"), #selector(menuToggleFollow), on: following))
        menu.addItem(action(tr("Settings…", "设置…"), #selector(menuShowSettings), key: ","))
        menu.addItem(.separator())
        menu.addItem(action(tr("Quit Yukio", "退出雪绪"), #selector(menuQuit), key: "q"))
        return menu
    }

    /// `--menu` 自查用：像启动时那样读一次会话记录。
    func pollOnceForCheck() {
        let now = nowMs()
        for e in feeds.poll(now: now) { router.ingest(e, now: min(e.ts, now)) }
        router.settle(now: now)
    }

    /// `--menu` 的离屏自查：把菜单（含子菜单）的文字列出来，不开窗口。
    func menuTitlesForCheck() -> [String] {
        func walk(_ menu: NSMenu, indent: String) -> [String] {
            var out: [String] = []
            for item in menu.items {
                if item.isSeparatorItem { out.append(indent + "—"); continue }
                let mark = item.state == .on ? " ✓" : ""
                // 大小是一条自带视图的滑条，没有文字。
                out.append(indent + (item.view != nil ? tr("Size (slider)", "大小（滑条）") : item.title) + mark)
                if let sub = item.submenu { out += walk(sub, indent: indent + "    ") }
            }
            return out
        }
        return walk(buildMenu(), indent: "")
    }

    @objc private func menuOpenChat() { petClicked() }
    @objc private func menuDropSign() { router.dismissCompletion(now: nowMs()) }
    /// 空的 representedObject 表示“自动”。
    @objc private func menuPickChat(_ sender: NSMenuItem) {
        let id = sender.representedObject as? String
        router.pinSession(id?.isEmpty == false ? id : nil, now: nowMs())
    }
    @objc private func menuSetProvider(_ sender: NSMenuItem) {
        let picked = AgentProvider(code: sender.representedObject as? String)
        switchProvider(to: picked)
    }

    @objc private func menuSetLanguage(_ sender: NSMenuItem) {
        language = UILanguage(code: sender.representedObject as? String)
        updateStatusTitle()
    }
    @objc private func menuStartDemo() { startDemo() }
    @objc private func menuStopDemo() { stopDemo() }
    @objc private func menuToggleFollow() { following.toggle() }
    @objc private func menuShowSettings() { showSettings() }
    @objc private func menuToggleBubble() { showBubble.toggle() }
    @objc private func menuToggleCards() {
        showCards.toggle()
        updateCards(now: nowMs(), immediate: true)
    }
    @objc private func menuResetPosition() {
        resetPetPosition()
    }
    @objc private func menuQuit() { NSApp.terminate(nil) }
}

// MARK: - 入口

// 输出重定向到文件时也逐行写出，便于实时查看 --watch。
setvbuf(stdout, nil, _IOLBF, 0)

let args = CommandLine.arguments
if args.contains("--check") { runCheck() }
if let i = args.firstIndex(of: "--snapshot"), i + 1 < args.count { runSnapshot(path: args[i + 1]) }
if let i = args.firstIndex(of: "--bubble"), i + 1 < args.count { runBubbleSnapshot(path: args[i + 1]) }
if let i = args.firstIndex(of: "--cards"), i + 1 < args.count { runCardsSnapshot(path: args[i + 1]) }
if let i = args.firstIndex(of: "--settings-snapshot"), i + 1 < args.count { runSettingsSnapshot(path: args[i + 1]) }
if let i = args.firstIndex(of: "--hang"), i + 1 < args.count { runHangSnapshot(path: args[i + 1]) }
if let i = args.firstIndex(of: "--hang-gif"), i + 1 < args.count { runHangGIF(path: args[i + 1]) }
if let i = args.firstIndex(of: "--replay"), i + 1 < args.count { runReplay(path: args[i + 1]) }
if let i = args.firstIndex(of: "--chat-link"), i + 1 < args.count { runChatLink(session: args[i + 1]) }
if args.contains("--open-chat") { runOpenChat() }
if let i = args.firstIndex(of: "--chats") {
    runChats(seconds: i + 1 < args.count ? Double(args[i + 1]) ?? 3 : 3)
}
if let i = args.firstIndex(of: "--watch") {
    runWatch(seconds: i + 1 < args.count ? Double(args[i + 1]) ?? 60 : 60)
}
// --menu：离屏列出菜单文字（含「跟随的助手」子菜单），不开窗口。
if args.contains("--menu") {
    let (catalog, assetsRoot) = loadCatalogOrExit()
    guard let library = try? SpriteLibrary(catalog: catalog, assetsRoot: assetsRoot) else {
        FileHandle.standardError.write(Data("资源加载失败\n".utf8)); exit(1)
    }
    let controller = AppController(catalog: catalog, library: library)
    controller.pollOnceForCheck()   // 先读一次记录，菜单里才是真实的「跟着谁 / 哪家没装」
    for line in controller.menuTitlesForCheck() { print(line) }
    exit(0)
}

// 只允许一个雪绪：已有实例在运行时直接退出。
let running = NSRunningApplication.runningApplications(withBundleIdentifier: Bundle.main.bundleIdentifier ?? "")
    .filter { $0.processIdentifier != ProcessInfo.processInfo.processIdentifier }
if Bundle.main.bundleIdentifier != nil && !running.isEmpty {
    running.first?.activate()
    exit(0)
}

let (catalog, assetsRoot) = loadCatalogOrExit()
let library: SpriteLibrary
do {
    library = try SpriteLibrary(catalog: catalog, assetsRoot: assetsRoot)
} catch {
    FileHandle.standardError.write(Data("资源加载失败：\(error)\n".utf8))
    exit(1)
}

let app = NSApplication.shared
// 平时是 .accessory（不进 Dock、不抢前台）；YUKIO_DOCK=1 时临时当普通 App，见 DockMode。
app.setActivationPolicy(DockMode.isEnabled ? .regular : .accessory)
let controller = AppController(catalog: catalog, library: library)
app.delegate = controller
DockMode.armIfEnabled()
app.run()
