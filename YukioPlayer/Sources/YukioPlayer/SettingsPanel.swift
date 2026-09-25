import AppKit
import YukioCore

/// 设置面板只放文字与系统控件。没有角色图、头像、装饰图，也不自绘图标。
struct SettingsSnapshot {
    let status: String
    let following: Bool
    let hidden: Bool
    let provider: AgentProvider
    let chats: [SessionSummary]
    let showBubble: Bool
    let showCards: Bool
    let showQuestionCard: Bool
    let scale: CGFloat
    let language: UILanguage
    let demoPlaying: Bool
}

enum SettingsChange {
    case following(Bool)
    case provider(AgentProvider)
    case chat(String?)
    case showBubble(Bool)
    case showCards(Bool)
    case showQuestionCard(Bool)
    case scale(CGFloat)
    case language(UILanguage)
    case toggleHidden
    case resetPosition
    case toggleDemo
}

final class SettingsPanelController: NSWindowController, NSWindowDelegate, NSMenuDelegate {
    var onChange: ((SettingsChange) -> Void)?

    private let root = NSView()
    private let stack = NSStackView()
    private let brandLabel = NSTextField(labelWithString: "YUKIO")
    private let statusLabel = NSTextField(wrappingLabelWithString: "")

    private let followTitle = NSTextField(labelWithString: "")
    private let providerTitle = NSTextField(labelWithString: "")
    private let chatTitle = NSTextField(labelWithString: "")
    private let bubbleTitle = NSTextField(labelWithString: "")
    private let cardsTitle = NSTextField(labelWithString: "")
    private let questionTitle = NSTextField(labelWithString: "")
    private let scaleTitle = NSTextField(labelWithString: "")
    private let languageTitle = NSTextField(labelWithString: "")

    private let followSwitch = NSSwitch()
    private let providerPopup = NSPopUpButton()
    private let chatPopup = NSPopUpButton()
    private let bubbleSwitch = NSSwitch()
    private let cardsSwitch = NSSwitch()
    private let questionSwitch = NSSwitch()
    private let scaleSlider = NSSlider()
    private let scaleReadout = NSTextField(labelWithString: "100%")
    private let languagePopup = NSPopUpButton()
    private let hideButton = NSButton()
    private let resetButton = NSButton()
    private let demoButton = NSButton()
    private let doneButton = NSButton()

    private let followingHeading = NSTextField(labelWithString: "")
    private let displayHeading = NSTextField(labelWithString: "")
    private let interfaceHeading = NSTextField(labelWithString: "")
    private var updating = false
    /// NSPopUpButton 展开时不能删改它的菜单项；否则 AppKit 的菜单跟踪循环会卡住。
    private var trackingPopupMenu = false
    private var pendingSnapshot: SettingsSnapshot?

    init() {
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 420, height: 500),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isReleasedWhenClosed = false
        panel.isMovableByWindowBackground = true
        panel.appearance = NSAppearance(named: .darkAqua)
        panel.backgroundColor = NSColor(calibratedRed: 0.065, green: 0.105, blue: 0.165, alpha: 0.98)
        super.init(window: panel)
        panel.delegate = self
        buildUI()
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    func show(snapshot: SettingsSnapshot, near anchor: NSRect) {
        apply(snapshot)
        position(near: anchor)
        NSApp.activate(ignoringOtherApps: true)
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
    }

    func apply(_ snapshot: SettingsSnapshot) {
        guard !trackingPopupMenu else {
            pendingSnapshot = snapshot
            return
        }
        updating = true
        defer { updating = false }

        refreshLabels(language: snapshot.language)
        statusLabel.stringValue = snapshot.status
        followSwitch.state = snapshot.following ? .on : .off
        bubbleSwitch.state = snapshot.showBubble ? .on : .off
        cardsSwitch.state = snapshot.showCards ? .on : .off
        questionSwitch.state = snapshot.showQuestionCard ? .on : .off

        sync(providerPopup, items: AgentProvider.allCases.map { ($0.displayName, $0.rawValue) })
        select(providerPopup, value: snapshot.provider.rawValue)

        let chatItems = [(tr("Automatic", "自动选择"), "")]
            + snapshot.chats.map { ($0.menuLabel, $0.id) }
        sync(chatPopup, items: chatItems)
        if let pinned = snapshot.chats.first(where: \.pinned) {
            select(chatPopup, value: pinned.id)
        } else {
            select(chatPopup, value: "")
        }
        chatPopup.isEnabled = !snapshot.chats.isEmpty

        let snapped = ScaleSliderView.snap(Double(snapshot.scale))
        scaleSlider.doubleValue = snapped
        scaleReadout.stringValue = "\(Int((snapped * 100).rounded()))%"

        sync(languagePopup, items: [("English", UILanguage.english.rawValue),
                                    ("中文", UILanguage.chinese.rawValue)])
        select(languagePopup, value: snapshot.language.rawValue)
        demoButton.title = snapshot.demoPlaying ? tr("Stop demo", "停止演示") : tr("Play demo", "播放演示")
        hideButton.title = snapshot.hidden ? tr("Show Yukio", "显示雪绪") : tr("Hide Yukio", "收起雪绪")
    }

    /// 定时刷新时大多数选项没有变化，不要反复拆掉 AppKit 正在使用的 NSMenu。
    private func sync(_ popup: NSPopUpButton, items: [(title: String, value: String)]) {
        let unchanged = popup.itemArray.count == items.count
            && zip(popup.itemArray, items).allSatisfy { item, expected in
                item.title == expected.title && item.representedObject as? String == expected.value
            }
        guard !unchanged else { return }
        popup.removeAllItems()
        for item in items {
            popup.addItem(withTitle: item.title)
            popup.lastItem?.representedObject = item.value
        }
    }

    private func select(_ popup: NSPopUpButton, value: String) {
        guard popup.selectedItem?.representedObject as? String != value,
              let item = popup.itemArray.first(where: { $0.representedObject as? String == value }) else { return }
        popup.select(item)
    }

    private func buildUI() {
        guard let window else { return }
        window.contentView = root
        root.translatesAutoresizingMaskIntoConstraints = false
        root.wantsLayer = true
        root.layer?.backgroundColor = NSColor(calibratedRed: 0.065, green: 0.105, blue: 0.165, alpha: 0.98).cgColor

        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 8
        stack.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: root.topAnchor, constant: 30),
            stack.bottomAnchor.constraint(lessThanOrEqualTo: root.bottomAnchor, constant: -20),
        ])

        brandLabel.font = .monospacedSystemFont(ofSize: 20, weight: .semibold)
        brandLabel.textColor = NSColor(calibratedRed: 0.76, green: 0.9, blue: 0.98, alpha: 1)
        statusLabel.font = .systemFont(ofSize: 12)
        statusLabel.textColor = .secondaryLabelColor
        statusLabel.maximumNumberOfLines = 2
        statusLabel.lineBreakMode = .byTruncatingTail
        statusLabel.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        stack.addArrangedSubview(brandLabel)
        stack.addArrangedSubview(statusLabel)
        stack.setCustomSpacing(18, after: statusLabel)

        stack.addArrangedSubview(followingHeading)
        stack.addArrangedSubview(row(title: followTitle, control: followSwitch))
        stack.addArrangedSubview(row(title: providerTitle, control: providerPopup, controlWidth: 210))
        stack.addArrangedSubview(row(title: chatTitle, control: chatPopup, controlWidth: 210))
        stack.setCustomSpacing(15, after: chatPopup.superview ?? chatPopup)

        stack.addArrangedSubview(separator())
        stack.addArrangedSubview(displayHeading)
        stack.addArrangedSubview(row(title: bubbleTitle, control: bubbleSwitch))
        stack.addArrangedSubview(row(title: cardsTitle, control: cardsSwitch))
        stack.addArrangedSubview(row(title: questionTitle, control: questionSwitch))
        let sliderGroup = NSStackView(views: [scaleSlider, scaleReadout])
        sliderGroup.orientation = .horizontal
        sliderGroup.alignment = .centerY
        sliderGroup.spacing = 10
        scaleSlider.widthAnchor.constraint(equalToConstant: 150).isActive = true
        scaleReadout.widthAnchor.constraint(equalToConstant: 46).isActive = true
        scaleReadout.alignment = .right
        scaleReadout.font = .monospacedDigitSystemFont(ofSize: 12, weight: .regular)
        scaleReadout.textColor = .secondaryLabelColor
        stack.addArrangedSubview(row(title: scaleTitle, control: sliderGroup, controlWidth: 210))

        stack.addArrangedSubview(separator())
        stack.addArrangedSubview(interfaceHeading)
        stack.addArrangedSubview(row(title: languageTitle, control: languagePopup, controlWidth: 210))

        let buttons = NSStackView(views: [hideButton, resetButton, demoButton, NSView(), doneButton])
        buttons.orientation = .horizontal
        buttons.alignment = .centerY
        buttons.spacing = 8
        buttons.translatesAutoresizingMaskIntoConstraints = false
        buttons.widthAnchor.constraint(equalToConstant: 372).isActive = true
        stack.setCustomSpacing(18, after: languagePopup.superview ?? languagePopup)
        stack.addArrangedSubview(buttons)

        configureActions()
    }

    private func configureActions() {
        followSwitch.target = self
        followSwitch.action = #selector(followChanged)
        providerPopup.target = self
        providerPopup.action = #selector(providerChanged)
        chatPopup.target = self
        chatPopup.action = #selector(chatChanged)
        bubbleSwitch.target = self
        bubbleSwitch.action = #selector(bubbleChanged)
        cardsSwitch.target = self
        cardsSwitch.action = #selector(cardsChanged)
        questionSwitch.target = self
        questionSwitch.action = #selector(questionChanged)

        scaleSlider.minValue = ScaleSliderView.range.lowerBound
        scaleSlider.maxValue = ScaleSliderView.range.upperBound
        scaleSlider.isContinuous = true
        scaleSlider.target = self
        scaleSlider.action = #selector(scaleChanged)

        languagePopup.target = self
        languagePopup.action = #selector(languageChanged)
        hideButton.bezelStyle = .rounded
        // 空格键：设置窗口在最前面时按一下就收起／显示。
        hideButton.keyEquivalent = " "
        hideButton.target = self
        hideButton.action = #selector(toggleHidden)
        hideButton.toolTip = tr("Shortcut: Space", "快捷键：空格")
        resetButton.bezelStyle = .rounded
        resetButton.target = self
        resetButton.action = #selector(resetPosition)
        demoButton.bezelStyle = .rounded
        demoButton.target = self
        demoButton.action = #selector(toggleDemo)
        doneButton.bezelStyle = .rounded
        doneButton.keyEquivalent = "\r"
        doneButton.target = self
        doneButton.action = #selector(closePanel)

        // 设置窗口会定时刷新状态；菜单展开时将刷新合并到关闭之后，避免菜单跟踪死锁。
        providerPopup.menu?.delegate = self
        chatPopup.menu?.delegate = self
        languagePopup.menu?.delegate = self
    }

    func menuWillOpen(_ menu: NSMenu) {
        trackingPopupMenu = true
    }

    func menuDidClose(_ menu: NSMenu) {
        trackingPopupMenu = false
        guard let snapshot = pendingSnapshot else { return }
        pendingSnapshot = nil
        apply(snapshot)
    }

    private func refreshLabels(language: UILanguage) {
        window?.title = tr("Yukio Settings", "雪绪设置")
        brandLabel.stringValue = tr("YUKIO SETTINGS", "雪绪设置")
        followingHeading.stringValue = tr("FOLLOWING", "跟随")
        displayHeading.stringValue = tr("DISPLAY", "显示")
        interfaceHeading.stringValue = tr("INTERFACE", "界面")
        followTitle.stringValue = tr("Follow activity", "跟随助手活动")
        providerTitle.stringValue = tr("Assistant", "跟随的助手")
        chatTitle.stringValue = tr("Chat", "跟随的聊天")
        bubbleTitle.stringValue = tr("Task bubble", "任务气泡")
        cardsTitle.stringValue = tr("Other chats", "其他聊天提醒")
        questionTitle.stringValue = tr("Answer here", "在这儿回答问题")
        scaleTitle.stringValue = tr("Size", "大小")
        languageTitle.stringValue = tr("Language", "语言")
        resetButton.title = tr("Reset position", "复位位置")
        doneButton.title = tr("Done", "完成")

        for heading in [followingHeading, displayHeading, interfaceHeading] {
            heading.font = .systemFont(ofSize: 11, weight: .semibold)
            heading.textColor = NSColor(calibratedRed: 0.48, green: 0.77, blue: 0.92, alpha: 1)
        }
    }

    private func row(title: NSTextField, control: NSView, controlWidth: CGFloat? = nil) -> NSView {
        title.font = .systemFont(ofSize: 13)
        title.textColor = .labelColor
        title.setContentCompressionResistancePriority(.defaultHigh, for: .horizontal)
        title.widthAnchor.constraint(equalToConstant: 150).isActive = true
        if let controlWidth { control.widthAnchor.constraint(equalToConstant: controlWidth).isActive = true }
        let row = NSStackView(views: [title, NSView(), control])
        row.orientation = .horizontal
        row.alignment = .centerY
        row.spacing = 8
        row.translatesAutoresizingMaskIntoConstraints = false
        row.widthAnchor.constraint(equalToConstant: 372).isActive = true
        row.heightAnchor.constraint(equalToConstant: 32).isActive = true
        return row
    }

    private func separator() -> NSBox {
        let box = NSBox()
        box.boxType = .separator
        box.translatesAutoresizingMaskIntoConstraints = false
        box.widthAnchor.constraint(equalToConstant: 372).isActive = true
        return box
    }

    private func position(near anchor: NSRect) {
        guard let window else { return }
        let screen = NSScreen.screens.first(where: { $0.visibleFrame.intersects(anchor) }) ?? NSScreen.main
        guard let visible = screen?.visibleFrame else { return }
        let size = window.frame.size
        let right = anchor.maxX + 12
        let left = anchor.minX - size.width - 12
        let x = left >= visible.minX ? left : min(right, visible.maxX - size.width)
        let y = min(max(anchor.midY - size.height / 2, visible.minY + 12), visible.maxY - size.height - 12)
        window.setFrameOrigin(NSPoint(x: x, y: y))
    }

    @objc private func followChanged() {
        guard !updating else { return }
        onChange?(.following(followSwitch.state == .on))
    }

    @objc private func providerChanged() {
        guard !updating else { return }
        let provider = AgentProvider(code: providerPopup.selectedItem?.representedObject as? String)
        // 先让 AppKit 结束下拉菜单跟踪，再扫描新来源并刷新设置内容。
        pendingSnapshot = nil
        DispatchQueue.main.async { [weak self] in self?.onChange?(.provider(provider)) }
    }

    @objc private func chatChanged() {
        guard !updating else { return }
        let value = chatPopup.selectedItem?.representedObject as? String
        onChange?(.chat(value?.isEmpty == false ? value : nil))
    }

    @objc private func bubbleChanged() {
        guard !updating else { return }
        onChange?(.showBubble(bubbleSwitch.state == .on))
    }

    @objc private func cardsChanged() {
        guard !updating else { return }
        onChange?(.showCards(cardsSwitch.state == .on))
    }

    @objc private func questionChanged() {
        guard !updating else { return }
        onChange?(.showQuestionCard(questionSwitch.state == .on))
    }

    @objc private func scaleChanged() {
        guard !updating else { return }
        let value = ScaleSliderView.snap(scaleSlider.doubleValue)
        scaleSlider.doubleValue = value
        scaleReadout.stringValue = "\(Int((value * 100).rounded()))%"
        onChange?(.scale(CGFloat(value)))
    }

    @objc private func languageChanged() {
        guard !updating else { return }
        onChange?(.language(UILanguage(code: languagePopup.selectedItem?.representedObject as? String)))
    }

    @objc private func toggleHidden() { onChange?(.toggleHidden) }
    @objc private func resetPosition() { onChange?(.resetPosition) }
    @objc private func toggleDemo() { onChange?(.toggleDemo) }
    @objc private func closePanel() { close() }
}

/// `--settings-snapshot out.png`：离屏画出真实设置面板内容，供设计核查。
func runSettingsSnapshot(path: String) -> Never {
    _ = NSApplication.shared
    L10n.language = .chinese
    let controller = SettingsPanelController()
    let chats = [
        SessionSummary(id: "demo-running", title: "设置界面优化", state: .default_work,
                       live: true, raisedSign: false, quietMs: 0, focused: true, pinned: false),
        SessionSummary(id: "demo-ready", title: "动作素材检查", state: .task_complete,
                       live: false, wantsYou: true, raisedSign: true, quietMs: 20_000,
                       focused: false, pinned: false),
    ]
    controller.apply(SettingsSnapshot(status: "正在跟随 GPT（Codex） · 正在工作",
                                      following: true,
                                      hidden: false,
                                      provider: .gpt,
                                      chats: chats,
                                      showBubble: true,
                                      showCards: true,
                                      showQuestionCard: true,
                                      scale: 1.0,
                                      language: .chinese,
                                      demoPlaying: false))
    guard let view = controller.window?.contentView else { exit(1) }
    view.layoutSubtreeIfNeeded()
    guard let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) else { exit(1) }
    view.cacheDisplay(in: view.bounds, to: rep)
    guard let data = rep.representation(using: .png, properties: [:]) else { exit(1) }
    do {
        try data.write(to: URL(fileURLWithPath: path), options: .atomic)
        print(path)
        exit(0)
    } catch {
        fputs("无法写入设置预览：\(error)\n", stderr)
        exit(1)
    }
}
