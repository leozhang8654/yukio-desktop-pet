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
    let specs = PetState.allCases.map { catalog.spec(for: $0) }
        + [catalog.specs[AnimationCatalog.runningLeftID]!, catalog.specs[AnimationCatalog.runningRightID]!]
    let cellW = 192, cellH = 208, labelH = 26, maxCols = 10
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
            ctx.draw(library.frame(spec.id, f).image, in: CGRect(x: i * cellW, y: top - labelH - cellH, width: cellW, height: cellH))
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

/// --bubble <输出.png>：把几种头顶气泡画在对应动作上方，按 Retina 2 倍输出（检查排版、截断、位置）。
func runBubbleSnapshot(path: String) -> Never {
    let (catalog, root) = loadCatalogOrExit()
    let library: SpriteLibrary
    do { library = try SpriteLibrary(catalog: catalog, assetsRoot: root) } catch { print("失败：\(error)"); exit(1) }
    let samples: [(PetState, StatusLine)] = [
        (.write_file, StatusLine(title: "桌宠缺失状态", current: "实现头顶气泡", progress: .init(done: 3, total: 7))),
        (.verify, StatusLine(title: "修复登录页的表单校验问题并补充单元测试，顺便整理目录结构",
                             current: "$ swift test --filter RouterTests", progress: nil)),
        (.thinking, StatusLine(title: nil, current: "思考中", progress: nil)),
        (.failed, StatusLine(title: "桌宠缺失状态", current: "出错：$ swift test", progress: .init(done: 7, total: 7))),
        (.question_for_user, StatusLine(title: "桌宠缺失状态", current: "等你回答", progress: nil)),
        (.task_complete, StatusLine(title: "桌宠缺失状态", current: "已完成", progress: .init(done: 7, total: 7))),
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
        let origin = BubbleLayout.origin(size: layout.size, petFrame: pet, headTop: library.headTopInset)
        layout.draw(in: NSRect(origin: origin, size: layout.size))
    }
    NSGraphicsContext.current = nil
    exit(savePNG(ctx, to: path) ? 0 : 1)
}

/// --replay <转录.jsonl> [--with-bubble]：用虚拟时钟回放一份真实转录，打印雪绪会显示的状态序列。
/// 加 --with-bubble 时同时打印头顶气泡的文字变化（含标题与文件名，只输出到本机终端）。
func runReplay(path: String) -> Never {
    let (catalog, _) = loadCatalogOrExit()
    guard let data = FileManager.default.contents(atPath: path) else {
        print("无法读取 \(path)"); exit(1)
    }
    var stream = JSONObjectStream()
    let parser = ClaudeTranscriptParser()
    let events = stream.append(data).flatMap { parser.events(fromLine: $0) }.sorted { $0.ts < $1.ts }
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
        let next = i + 1 < events.count ? events[i + 1].ts : e.ts + config.respondLingerMs + 3000
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

/// --watch <秒>：无窗口地实时跟随 Claude 转录，打印事件与状态切换（不打印任何对话内容）。
func runWatch(seconds: Double) -> Never {
    let (catalog, _) = loadCatalogOrExit()
    let source = ClaudeTranscriptSource()
    let hooks = HookInboxSource()
    let start = nowMs()
    let router = ActivityRouter(now: start)
    for e in source.poll(now: start) { router.ingest(e, now: min(e.ts, start)) }
    router.settle(now: start)
    print("\(timeString(start))  目录 \(source.projectsDir.path) 存在=\(source.status.directoryFound) 追踪文件=\(source.status.trackedFiles)")
    print("\(timeString(start))  启动状态 \(router.displayed.rawValue)（\(catalog.label(for: router.displayed))） 会话 \(router.focusedSession?.prefix(8) ?? "-")")
    while nowMs() - start < seconds * 1000 {
        let now = nowMs()
        for e in source.poll(now: now) + hooks.poll(now: now) {
            router.ingest(e, now: min(e.ts, now))
            let lag = now - e.ts
            print("\(timeString(now))  事件 [\(e.session.prefix(8))] \(describe(e))  写入延迟≈\(Int(lag)) ms")
        }
        if let s = router.tick(now: now) {
            print("\(timeString(now))  显示 \(s.rawValue)（\(catalog.label(for: s))）")
        }
        Thread.sleep(forTimeInterval: 0.1)
    }
    exit(0)
}

// MARK: - 桌面播放器

final class AppController: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private let catalog: AnimationCatalog
    private let library: SpriteLibrary
    private let router = ActivityRouter(now: nowMs())
    private let transcript = ClaudeTranscriptSource()
    private let hooks = HookInboxSource()
    private let defaults = UserDefaults.standard

    private var panel: PetPanel!
    private var view: PetView!
    private var bubble: BubblePanel!
    private var statusItem: NSStatusItem!
    private var timer: Timer?
    private var tickCount = 0

    private var shownState: PetState = .idle
    private var stateTimeline: SpriteTimeline
    private var runTimeline: SpriteTimeline?
    private var runningRight = true
    private var directionAccum: CGFloat = 0
    private var directionDecided = false
    /// 气泡正在显示的内容。出现和消失立即生效；内容变化每段至少停留 1.2 秒，连续读几个文件时不逐个闪过。
    private var bubbleHold = HeldValue<StatusLine?>(nil, minHoldMs: 1200)

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
        get { CGFloat(defaults.object(forKey: "scale") as? Double ?? 1.0) }
        set { defaults.set(Double(newValue), forKey: "scale") }
    }
    private var showBubble: Bool {
        get { defaults.object(forKey: "showBubble") as? Bool ?? true }
        set { defaults.set(newValue, forKey: "showBubble") }
    }

    init(catalog: AnimationCatalog, library: SpriteLibrary) {
        self.catalog = catalog
        self.library = library
        self.stateTimeline = SpriteTimeline(spec: catalog.spec(for: .idle), now: nowMs())
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let now = nowMs()
        // 先恢复当前 Claude 活动，再显示窗口：第一帧就是正确动作。
        for e in transcript.poll(now: now) { router.ingest(e, now: min(e.ts, now)) }
        _ = hooks.poll(now: now)
        router.settle(now: now)
        shownState = following ? router.displayed : .idle
        stateTimeline = SpriteTimeline(spec: catalog.spec(for: shownState), now: now)

        setUpWindow()
        setUpStatusItem()
        render()
        panel.orderFrontRegardless()
        setUpBubble()
        updateBubble(now: now)

        // 30 Hz：小幅动作一帧约 67 ms、眨眼一帧 50–110 ms，都能按时换帧。
        let t = Timer(timeInterval: 1.0 / 30, repeats: true) { [weak self] _ in self?.tick() }
        t.tolerance = 0.005
        RunLoop.main.add(t, forMode: .common)
        timer = t

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

        view.onDragBegan = { [weak self] in self?.dragBegan() }
        view.onDragMoved = { [weak self] dx in self?.dragMoved(dx) }
        view.onDragEnded = { [weak self] in self?.dragEnded() }
        view.onContextMenu = { [weak self] event in
            guard let self else { return }
            NSMenu.popUpContextMenu(self.buildMenu(), with: event, for: self.view)
        }
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

    private func clampToScreen() {
        let f = panel.frame
        let center = NSPoint(x: f.midX, y: f.midY)
        let screen = NSScreen.screens.first(where: { $0.frame.contains(center) }) ?? NSScreen.main ?? NSScreen.screens[0]
        let vf = screen.visibleFrame
        let x = min(max(f.minX, vf.minX), vf.maxX - f.width)
        let y = min(max(f.minY, vf.minY), vf.maxY - f.height)
        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }

    private func savePosition() {
        defaults.set(Double(panel.frame.minX), forKey: "originX")
        defaults.set(Double(panel.frame.minY), forKey: "originY")
    }

    private func applyScale(_ s: CGFloat) {
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
    }

    // MARK: 拖动：复用原版左右跑动

    private func dragBegan() {
        directionDecided = false
        directionAccum = 0
        startRun(right: runningRight)
    }

    private func startRun(right: Bool) {
        runningRight = right
        let id = right ? AnimationCatalog.runningRightID : AnimationCatalog.runningLeftID
        runTimeline = SpriteTimeline(spec: catalog.specs[id]!, now: nowMs())
        render()
    }

    private func dragMoved(_ dx: CGFloat) {
        guard dx != 0 else { return }
        if !directionDecided {
            directionDecided = true
            if (dx > 0) != runningRight { startRun(right: dx > 0) }
            return
        }
        // 反向移动累计超过 6 pt 才转身，避免手抖来回翻转。
        if runningRight {
            directionAccum = min(0, directionAccum + dx)
            if directionAccum < -6 { directionAccum = 0; startRun(right: false) }
        } else {
            directionAccum = max(0, directionAccum + dx)
            if directionAccum > 6 { directionAccum = 0; startRun(right: true) }
        }
    }

    private func dragEnded() {
        runTimeline = nil
        clampToScreen()
        savePosition()
        positionBubble()
        render()
    }

    // MARK: 主循环

    private func tick() {
        let now = nowMs()
        tickCount += 1
        if tickCount % 8 == 0 {
            // 约每 0.27 秒读一次转录。事件始终进入路由器；暂停跟随只影响显示。
            for e in transcript.poll(now: now) + hooks.poll(now: now) { router.ingest(e, now: min(e.ts, now)) }
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
            updateStatusTitle()
        }
        stateTimeline.advance(to: now)
        runTimeline?.advance(to: now)
        render()
        updateMousePassThrough()
        updateBubble(now: now)
    }

    private func render() {
        let frame: SpriteLibrary.Frame
        if let run = runTimeline {
            frame = library.frame(run.spec.id, run.frame)
        } else {
            frame = library.frame(stateTimeline.spec.id, stateTimeline.frame)
        }
        view.show(frame)
    }

    private func updateMousePassThrough() {
        if view.dragging { panel.ignoresMouseEvents = false; return }
        let m = NSEvent.mouseLocation
        let f = panel.frame
        let over = f.contains(m) && view.isOpaque(at: NSPoint(x: m.x - f.minX, y: m.y - f.minY))
        if panel.ignoresMouseEvents == over { panel.ignoresMouseEvents = !over }
    }

    // MARK: 头顶气泡

    private func setUpBubble() {
        bubble = BubblePanel()
        // 子窗口：拖动雪绪时跟着走。
        panel.addChildWindow(bubble, ordered: .above)
    }

    /// 上次摆放气泡时是否在拖动。拖动开始和结束时各重新摆一次。
    private var bubblePlacedForDrag = false

    private func updateBubble(now: Double) {
        if view.dragging != bubblePlacedForDrag { positionBubble() }
        let source: ActivityRouter? = simulation?.router ?? (following ? router : nil)
        let line = showBubble ? source?.statusLine(now: now) : nil
        let visibilityChanged = (line == nil) != (bubbleHold.value == nil)
        guard bubbleHold.update(line, now: now, immediate: visibilityChanged) else { return }
        if let line = bubbleHold.value {
            bubble.bubbleView.layout = BubbleLayout(line)
            positionBubble()
            fadeBubble(to: 1)
        } else {
            fadeBubble(to: 0)
        }
    }

    private func positionBubble() {
        bubblePlacedForDrag = view.dragging
        guard let bubble, let size = bubble.bubbleView.layout?.size else { return }
        // 跑动时头发扬起，气泡抬高，免得压住头顶；松手后回到站姿／坐姿的高度。
        let headTop = view.dragging ? library.runningTopInset : library.headTopInset
        var origin = BubbleLayout.origin(size: size, petFrame: panel.frame, headTop: headTop * scale)
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
            button.title = simulation != nil ? "模拟" : ""
        } else {
            button.title = simulation != nil ? "雪绪·模拟" : "雪绪"
        }
        button.toolTip = "雪绪：\(catalog.label(for: shownState))"
    }

    /// 再次打开 Yukio.app（Finder、Spotlight、open 命令）时，在雪绪身旁弹出菜单。
    /// 菜单栏被挤满、图标被刘海遮住时，这是一定能用的入口；在雪绪身上右键也可以。
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

    private func action(_ title: String, _ selector: Selector, key: String = "", on: Bool? = nil) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: selector, keyEquivalent: key)
        item.target = self
        if let on { item.state = on ? .on : .off }
        return item
    }

    private func buildMenu() -> NSMenu {
        let menu = NSMenu()
        menu.addItem(info("雪绪 · \(catalog.label(for: shownState))"))
        if simulation != nil {
            menu.addItem(info("正在播放模拟演示（不是真实 Claude 活动）"))
        } else if !following {
            menu.addItem(info("已暂停跟随，保持空闲"))
        } else if !transcript.status.directoryFound {
            menu.addItem(info("未找到 \(transcript.projectsDir.path)"))
        } else {
            menu.addItem(info("跟随 Claude Code（只读会话转录）"))
            let snap = router.snapshot()
            if let s = snap.focusedSession {
                menu.addItem(info("会话 \(s.prefix(8))… · \(snap.taskActive ? "进行中" : "已结束") · 未完成工具 \(snap.openTools)"))
            }
            if hooks.isPresent {
                menu.addItem(info("Claude hooks 收件箱：已收到 \(hooks.eventsReceived) 个事件"))
            }
        }
        menu.addItem(.separator())
        if simulation == nil {
            menu.addItem(action("播放模拟演示", #selector(menuStartDemo)))
        } else {
            menu.addItem(action("停止模拟演示", #selector(menuStopDemo)))
        }
        menu.addItem(action("跟随 Claude 活动", #selector(menuToggleFollow), on: following))
        menu.addItem(action("头顶显示任务", #selector(menuToggleBubble), on: showBubble))

        let sizeItem = NSMenuItem(title: "大小", action: nil, keyEquivalent: "")
        let sizeMenu = NSMenu()
        for s in [1.0, 1.25, 1.5, 2.0] {
            let item = action("\(Int(s * 100))%", #selector(menuScale(_:)), on: abs(Double(scale) - s) < 0.01)
            item.representedObject = s
            sizeMenu.addItem(item)
        }
        sizeItem.submenu = sizeMenu
        menu.addItem(sizeItem)
        menu.addItem(action("回到屏幕右下角", #selector(menuResetPosition)))
        menu.addItem(.separator())
        menu.addItem(action("退出雪绪", #selector(menuQuit), key: "q"))
        return menu
    }

    @objc private func menuStartDemo() { startDemo() }
    @objc private func menuStopDemo() { stopDemo() }
    @objc private func menuToggleFollow() { following.toggle() }
    @objc private func menuToggleBubble() { showBubble.toggle() }
    @objc private func menuScale(_ sender: NSMenuItem) {
        if let s = sender.representedObject as? Double { applyScale(CGFloat(s)) }
    }
    @objc private func menuResetPosition() {
        panel.setFrameOrigin(defaultOrigin())
        savePosition()
        positionBubble()
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
if let i = args.firstIndex(of: "--replay"), i + 1 < args.count { runReplay(path: args[i + 1]) }
if let i = args.firstIndex(of: "--watch") {
    runWatch(seconds: i + 1 < args.count ? Double(args[i + 1]) ?? 60 : 60)
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
app.setActivationPolicy(.accessory)
let controller = AppController(catalog: catalog, library: library)
app.delegate = controller
app.run()
