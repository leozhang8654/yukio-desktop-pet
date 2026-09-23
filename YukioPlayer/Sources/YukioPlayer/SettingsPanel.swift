import AppKit
import YukioCore

/// 设置面板只放文字与系统控件。没有角色图、头像、装饰图，也不自绘图标。
struct SettingsSnapshot {
    let status: String
    let following: Bool
    let provider: AgentProvider
    let chats: [SessionSummary]
    let showBubble: Bool
    let showCards: Bool
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
    case scale(CGFloat)
    case language(UILanguage)
    case resetPosition
    case toggleDemo
}

final class SettingsPanelController: NSWindowController, NSWindowDelegate {
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
    private let scaleTitle = NSTextField(labelWithString: "")
    private let languageTitle = NSTextField(labelWithString: "")

    private let followSwitch = NSSwitch()
    private let providerPopup = NSPopUpButton()
    private let chatPopup = NSPopUpButton()
    private let bubbleSwitch = NSSwitch()
    private let cardsSwitch = NSSwitch()
    private let scaleSlider = NSSlider()
    private let scaleReadout = NSTextField(labelWithString: "100%")
    private let languagePopup = NSPopUpButton()
    private let resetButton = NSButton()
    private let demoButton = NSButton()
    private let doneButton = NSButton()

    private let followingHeading = NSTextField(labelWithString: "")
    private let displayHeading = NSTextField(labelWithString: "")
    private let interfaceHeading = NSTextField(labelWithString: "")
    private var updating = false

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
        updating = true
        defer { updating = false }

        refreshLabels(language: snapshot.language)
        statusLabel.stringValue = snapshot.status
        followSwitch.state = snapshot.following ? .on : .off
        bubbleSwitch.state = snapshot.showBubble ? .on : .off
        cardsSwitch.state = snapshot.showCards ? .on : .off

        providerPopup.removeAllItems()
        for provider in AgentProvider.allCases {
            providerPopup.addItem(withTitle: provider.displayName)
            providerPopup.lastItem?.representedObject = provider.rawValue
        }
        if let index = AgentProvider.allCases.firstIndex(of: snapshot.provider) {
            providerPopup.selectItem(at: index)
        }

        chatPopup.removeAllItems()
        chatPopup.addItem(withTitle: tr("Automatic", "自动选择"))
        chatPopup.lastItem?.representedObject = ""
        for chat in snapshot.chats {
            chatPopup.addItem(withTitle: chat.menuLabel)
            chatPopup.lastItem?.representedObject = chat.id
        }
        if let pinned = snapshot.chats.first(where: \.pinned),
           let item = chatPopup.itemArray.first(where: { $0.representedObject as? String == pinned.id }) {
            chatPopup.select(item)
        } else {
            chatPopup.selectItem(at: 0)
        }
        chatPopup.isEnabled = !snapshot.chats.isEmpty

        let snapped = ScaleSliderView.snap(Double(snapshot.scale))
        scaleSlider.doubleValue = snapped
        scaleReadout.stringValue = "\(Int((snapped * 100).rounded()))%"

        languagePopup.removeAllItems()
        for (language, title) in [(UILanguage.english, "English"), (.chinese, "中文")] {
            languagePopup.addItem(withTitle: title)
            languagePopup.lastItem?.representedObject = language.rawValue
        }
        languagePopup.selectItem(at: snapshot.language == .chinese ? 1 : 0)
        demoButton.title = snapshot.demoPlaying ? tr("Stop demo", "停止演示") : tr("Play demo", "播放演示")
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

        let buttons = NSStackView(views: [resetButton, demoButton, NSView(), doneButton])
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

        scaleSlider.minValue = ScaleSliderView.range.lowerBound
        scaleSlider.maxValue = ScaleSliderView.range.upperBound
        scaleSlider.isContinuous = true
        scaleSlider.target = self
        scaleSlider.action = #selector(scaleChanged)

        languagePopup.target = self
        languagePopup.action = #selector(languageChanged)
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
        onChange?(.provider(AgentProvider(code: providerPopup.selectedItem?.representedObject as? String)))
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
                                      provider: .gpt,
                                      chats: chats,
                                      showBubble: true,
                                      showCards: true,
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
