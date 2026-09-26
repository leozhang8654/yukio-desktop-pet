import AppKit
import Combine
import SwiftUI
import YukioCore

private enum AssistantPage: String, CaseIterable {
    case home = "首页", reminders = "提醒", personal = "个性化", extensions = "扩展"
    var icon: String {
        switch self {
        case .home: return "square.grid.2x2"
        case .reminders: return "bell"
        case .personal: return "slider.horizontal.3"
        case .extensions: return "square.stack.3d.up"
        }
    }
}

private let ink = Color(red: 0.13, green: 0.18, blue: 0.17)
private let green = Color(red: 0.20, green: 0.39, blue: 0.32)
private let pale = Color(red: 0.94, green: 0.97, blue: 0.95)

final class AssistantWindowController: NSWindowController, NSWindowDelegate {
    init(store: ReminderStore, openPetSettings: @escaping () -> Void) {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1040, height: 740),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Yukio · 个人助手"
        window.minSize = NSSize(width: 860, height: 620)
        window.isReleasedWhenClosed = false
        window.titlebarAppearsTransparent = true
        window.backgroundColor = .white
        window.appearance = NSAppearance(named: .aqua)
        window.contentView = NSHostingView(rootView: AssistantView(store: store, openPetSettings: openPetSettings))
        super.init(window: window)
        window.delegate = self
        window.center()
        window.setFrameAutosaveName("YukioAssistantWindow")
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    func present() {
        installMenuIfNeeded()
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
    }

    func windowWillClose(_ notification: Notification) {
        if !DockMode.isEnabled { NSApp.setActivationPolicy(.accessory) }
    }

    private func installMenuIfNeeded() {
        guard NSApp.mainMenu == nil else { return }
        let menu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "退出 Yukio", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        menu.addItem(appItem)
        let file = NSMenuItem(title: "文件", action: nil, keyEquivalent: "")
        file.submenu = NSMenu(title: "文件")
        file.submenu?.addItem(withTitle: "关闭窗口", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        menu.addItem(file)
        let edit = NSMenuItem(title: "编辑", action: nil, keyEquivalent: "")
        edit.submenu = NSMenu(title: "编辑")
        for (title, selector, key) in [("撤销", "undo:", "z"), ("剪切", "cut:", "x"), ("复制", "copy:", "c"), ("粘贴", "paste:", "v"), ("全选", "selectAll:", "a")] {
            edit.submenu?.addItem(withTitle: title, action: NSSelectorFromString(selector), keyEquivalent: key)
        }
        menu.addItem(edit)
        NSApp.mainMenu = menu
    }
}

private struct AssistantView: View {
    @ObservedObject var store: ReminderStore
    let openPetSettings: () -> Void
    @State private var page: AssistantPage = .home
    @State private var showEditor = false
    @State private var editing: Reminder?
    @State private var showCompleted = false
    @AppStorage("assistantName") private var name = "雪绪"
    @AppStorage("assistantUserName") private var userName = ""
    @AppStorage("assistantReminderSound") private var sound = true

    var body: some View {
        HStack(spacing: 0) {
            sidebar
            Rectangle().fill(Color.black.opacity(0.06)).frame(width: 1)
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Text(page.rawValue).font(.system(size: 13, weight: .medium))
                    Spacer()
                    Label("个人空间", systemImage: "circle.inset.filled").font(.system(size: 11)).foregroundColor(green)
                }.padding(.horizontal, 36).padding(.vertical, 20)
                Divider().opacity(0.5)
                ScrollView {
                    VStack(alignment: .leading, spacing: 26) {
                        if let error = store.error {
                            Label(error, systemImage: "exclamationmark.triangle").font(.callout)
                                .foregroundColor(.red).padding(14).frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color.red.opacity(0.05)).cornerRadius(10)
                        }
                        switch page {
                        case .home: home
                        case .reminders: reminders
                        case .personal: personal
                        case .extensions: extensions
                        }
                    }.padding(36)
                }
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .foregroundColor(ink).background(Color.white).tint(green).preferredColorScheme(.light)
        .sheet(isPresented: $showEditor) { ReminderEditor(store: store, reminder: editing) }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 11) {
                Image(systemName: "sparkle").font(.system(size: 24, weight: .medium))
                    .foregroundColor(green).frame(width: 42, height: 42).background(Color.white).cornerRadius(13)
                VStack(alignment: .leading, spacing: 3) {
                    Text("Yukio").font(.system(size: 22, weight: .semibold, design: .rounded))
                    Text("一点陪伴，一点帮助").font(.system(size: 10)).foregroundColor(.secondary)
                }
            }.padding(.bottom, 44)
            Text("我的助手").font(.system(size: 10, weight: .medium)).foregroundColor(.secondary).padding(.leading, 12).padding(.bottom, 12)
            ForEach(AssistantPage.allCases, id: \.self) { item in
                Button { page = item } label: {
                    HStack(spacing: 12) {
                        Image(systemName: item.icon).frame(width: 18)
                        Text(item.rawValue)
                        Spacer()
                        if item == .reminders && !store.scheduled.isEmpty {
                            Text("\(store.scheduled.count)").font(.system(size: 11)).foregroundColor(.secondary)
                        }
                    }.font(.system(size: 13, weight: page == item ? .semibold : .regular))
                        .padding(.horizontal, 13).padding(.vertical, 13)
                        .background(page == item ? Color.white : Color.clear).cornerRadius(10)
                        .contentShape(Rectangle())
                }.buttonStyle(.plain).padding(.bottom, 5)
            }
            Spacer()
            VStack(alignment: .leading, spacing: 9) {
                Image(systemName: "leaf").font(.system(size: 19)).foregroundColor(green)
                Text("从一件小事开始").font(.system(size: 12, weight: .medium))
                Text("把要记得的事交给我，\n给自己留一点空间。")
                    .font(.system(size: 11)).foregroundColor(.secondary).lineSpacing(5)
            }.padding(15).frame(maxWidth: .infinity, alignment: .leading).background(Color.white.opacity(0.65)).cornerRadius(12)
            Divider().padding(.vertical, 20)
            Button { openPetSettings() } label: {
                Label("桌宠设置", systemImage: "gearshape").font(.system(size: 12)).foregroundColor(.secondary)
            }.buttonStyle(.plain)
            Text("YUKIO  /  起步版").font(.system(size: 9, weight: .medium)).tracking(1.3)
                .foregroundColor(.secondary).padding(.top, 17)
        }.padding(22).frame(width: 205).frame(maxHeight: .infinity)
            .background(Color(red: 0.965, green: 0.972, blue: 0.964))
    }

    private var home: some View {
        VStack(alignment: .leading, spacing: 26) {
            VStack(alignment: .leading, spacing: 10) {
                Text(Date(), format: .dateTime.month(.wide).day().weekday(.wide)).font(.system(size: 12)).foregroundColor(.secondary)
                Text(userName.isEmpty ? "今天，慢慢来。" : "\(userName)，今天慢慢来。")
                    .font(.system(size: 30, weight: .semibold))
                Text("我是\(name.isEmpty ? "雪绪" : name)。从记住你的小事开始。")
                    .font(.system(size: 13)).foregroundColor(.secondary)
            }
            HStack(spacing: 24) {
                VStack(alignment: .leading, spacing: 14) {
                    Label("留给之后的自己", systemImage: "bell.badge").font(.system(size: 12)).foregroundColor(green)
                    Text("有件事，想让我提醒你吗？").font(.system(size: 21, weight: .medium))
                    Text("喝杯水、出门赴约，或者起来走一走。")
                        .font(.system(size: 12)).foregroundColor(.secondary)
                    Button { newReminder() } label: { Label("创建提醒", systemImage: "plus").padding(.horizontal, 8).padding(.vertical, 5) }
                        .buttonStyle(.borderedProminent).disabled(!store.available).padding(.top, 4)
                }
                Spacer(minLength: 0)
                Image(systemName: "clock").font(.system(size: 58, weight: .ultraLight))
                    .foregroundColor(green.opacity(0.75)).frame(width: 110, height: 110)
                    .background(Color.white.opacity(0.65)).clipShape(Circle()).accessibilityHidden(true)
            }.padding(28).frame(maxWidth: .infinity, alignment: .leading).background(pale).cornerRadius(18)
            HStack(spacing: 14) {
                metric("待提醒", count: store.scheduled.count, icon: "bell")
                metric("待确认", count: store.ringing.count, icon: "clock.badge.exclamationmark")
                metric("已完成", count: store.completed.count, icon: "checkmark.circle")
            }
            HStack {
                Text("接下来").font(.system(size: 16, weight: .semibold))
                Spacer()
                Button("查看全部 →") { page = .reminders }.buttonStyle(.plain).font(.system(size: 12)).foregroundColor(green)
            }
            if store.scheduled.isEmpty && store.ringing.isEmpty {
                emptyState("还没有安排", detail: "不用急，等有件事想记住时，再来这里。", icon: "sun.horizon")
            } else {
                ForEach(Array((store.ringing + store.scheduled).prefix(3))) { reminder in row(reminder) }
            }
            runtimeNote
        }
    }

    private var reminders: some View {
        VStack(alignment: .leading, spacing: 22) {
            HStack {
                heading("把小事记在这里。", subtitle: "设好时间，到点我来提醒你。")
                Spacer()
                Button { newReminder() } label: { Label("新建提醒", systemImage: "plus") }
                    .buttonStyle(.borderedProminent).disabled(!store.available)
            }
            Picker("提醒状态", selection: $showCompleted) {
                Text("待提醒 · \(store.scheduled.count + store.ringing.count)").tag(false)
                Text("已完成 · \(store.completed.count)").tag(true)
            }.pickerStyle(.segmented).frame(width: 280)
            let items = showCompleted ? store.completed : store.ringing + store.scheduled
            if items.isEmpty {
                emptyState(showCompleted ? "还没有完成的提醒" : "第一件事，从这里开始", detail: showCompleted ? "确认过的提醒会留在这里。" : "点击「新建提醒」，选一个时间就好了。", icon: showCompleted ? "checkmark.circle" : "bell")
            } else {
                ForEach(items) { reminder in row(reminder) }
            }
            runtimeNote
        }
    }

    private var personal: some View {
        VStack(alignment: .leading, spacing: 24) {
            heading("让这里，更像你的。", subtitle: "先从名字和提醒习惯开始。")
            VStack(alignment: .leading, spacing: 20) {
                Text("我们怎么称呼彼此").font(.headline)
                LabeledContent("助手的名字") { TextField("雪绪", text: $name).frame(width: 220) }
                LabeledContent("怎么称呼你") { TextField("你的名字（可选）", text: $userName).frame(width: 220) }
                Divider()
                Toggle("提醒时播放提示音", isOn: $sound)
                Text("修改会自动保存在这台 Mac 上。").font(.system(size: 11)).foregroundColor(.secondary)
            }.textFieldStyle(.roundedBorder).padding(24).assistantCard()
            HStack(spacing: 18) {
                Image(systemName: "person.crop.square").font(.system(size: 25)).foregroundColor(green)
                VStack(alignment: .leading, spacing: 7) {
                    Text("桌面上的我").font(.headline)
                    Text("调整桌宠大小、显示方式和跟随的助手。").font(.system(size: 12)).foregroundColor(.secondary)
                }
                Spacer()
                Button("打开设置") { openPetSettings() }
            }.padding(24).assistantCard()
            planned("之后可以更懂你", detail: "说话风格、偏好记忆和更多角色外观，留给接下来的版本。", icon: "sparkles")
        }
    }

    private var extensions: some View {
        VStack(alignment: .leading, spacing: 24) {
            heading("慢慢长出新本领。", subtitle: "这里是之后的扩展位置，下面这些功能还没有接入。")
            planned("AI 对话", detail: "连接你选择的模型，先学会理解「半小时后提醒我」。", icon: "bubble.left.and.bubble.right")
            planned("桌面小组件", detail: "把下一条提醒和今天的安排，放在一眼能看到的地方。", icon: "rectangle.on.rectangle")
            planned("日历与更多连接", detail: "把已有的日程带进来，再逐步连接你常用的工具。", icon: "link")
            Text("先把提醒做好。新能力准备好之后，再由你决定要不要开启。")
                .font(.system(size: 12)).foregroundColor(.secondary).lineSpacing(5)
        }
    }

    private var runtimeNote: some View {
        Label("关闭主窗口后仍会提醒。请保持 Yukio 运行；电脑休眠或退出期间的提醒，会在唤醒或下次启动后补上。", systemImage: "info.circle")
            .font(.system(size: 11)).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true).lineSpacing(4)
    }

    private func heading(_ title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.system(size: 26, weight: .semibold))
            Text(subtitle).font(.system(size: 12)).foregroundColor(.secondary).lineSpacing(4)
        }
    }

    private func metric(_ title: String, count: Int, icon: String) -> some View {
        VStack(alignment: .leading, spacing: 15) {
            Label(title, systemImage: icon).font(.system(size: 12)).foregroundColor(.secondary)
            Text("\(count)").font(.system(size: 28, weight: .medium, design: .rounded))
        }.frame(maxWidth: .infinity, alignment: .leading).padding(20).assistantCard()
    }

    private func emptyState(_ title: String, detail: String, icon: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: icon).font(.system(size: 27, weight: .light)).foregroundColor(green.opacity(0.7))
            Text(title).font(.system(size: 14, weight: .medium))
            Text(detail).font(.system(size: 12)).foregroundColor(.secondary)
        }.frame(maxWidth: .infinity).padding(.vertical, 34).assistantCard()
    }

    private func planned(_ title: String, detail: String, icon: String) -> some View {
        HStack(alignment: .top, spacing: 18) {
            Image(systemName: icon).font(.system(size: 22)).foregroundColor(green).frame(width: 32)
            VStack(alignment: .leading, spacing: 9) {
                Text(title).font(.system(size: 15, weight: .medium))
                Text(detail).font(.system(size: 12)).foregroundColor(.secondary).lineSpacing(5)
            }
            Spacer(minLength: 8)
            Text("规划中").font(.system(size: 10)).foregroundColor(.secondary).padding(.horizontal, 9).padding(.vertical, 5).background(pale).cornerRadius(6)
        }.padding(24).assistantCard()
    }

    private func row(_ reminder: Reminder) -> some View {
        HStack(spacing: 16) {
            Image(systemName: reminder.status == .completed ? "checkmark.circle" : "bell")
                .foregroundColor(reminder.status == .ringing ? .orange : green)
                .frame(width: 36, height: 36).background(pale).cornerRadius(10)
            VStack(alignment: .leading, spacing: 6) {
                Text(reminder.title).font(.system(size: 14, weight: .medium)).lineLimit(2)
                HStack {
                    Text(reminder.dueAt, format: .dateTime.month().day().hour().minute())
                    if reminder.status == .ringing { Text("· 到时间了").foregroundColor(.orange) }
                }.font(.system(size: 11)).foregroundColor(.secondary)
            }
            Spacer()
            if reminder.status == .ringing {
                Button("稍后 5 分钟") { store.snooze(reminder.id) }
                Button("知道了") { store.complete(reminder.id) }.buttonStyle(.borderedProminent)
            } else if reminder.status == .scheduled {
                Button("编辑") { editing = reminder; showEditor = true }
            }
            Button { store.remove(reminder.id) } label: { Image(systemName: "trash").foregroundColor(.secondary) }
                .buttonStyle(.borderless).help("删除提醒").accessibilityLabel("删除提醒：\(reminder.title)")
        }.padding(18).assistantCard()
    }

    private func newReminder() { editing = nil; showEditor = true }
}

private extension View {
    func assistantCard() -> some View {
        background(Color.white).cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.black.opacity(0.08), lineWidth: 1))
    }
}

private struct ReminderEditor: View {
    @ObservedObject var store: ReminderStore
    let reminder: Reminder?
    @Environment(\.dismiss) private var dismiss
    @State private var title: String
    @State private var dueAt: Date
    @FocusState private var titleFocused: Bool

    init(store: ReminderStore, reminder: Reminder?) {
        self.store = store
        self.reminder = reminder
        _title = State(initialValue: reminder?.title ?? "")
        _dueAt = State(initialValue: reminder?.dueAt ?? Date().addingTimeInterval(25 * 60))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            Label(reminder == nil ? "新建提醒" : "编辑提醒", systemImage: "bell.badge").font(.system(size: 22, weight: .semibold))
            VStack(alignment: .leading, spacing: 9) {
                Text("提醒你做什么？").font(.system(size: 12)).foregroundColor(.secondary)
                TextField("比如：起来走一走", text: $title).textFieldStyle(.roundedBorder).focused($titleFocused)
            }
            DatePicker("什么时候", selection: $dueAt, displayedComponents: [.date, .hourAndMinute])
                .datePickerStyle(.field)
            HStack {
                ForEach([1, 5, 25, 60], id: \.self) { minutes in
                    Button("\(minutes) 分钟后") { dueAt = Date().addingTimeInterval(Double(minutes * 60)) }
                }
            }
            Text("这是一条单次提醒。到点会弹出提醒卡片。")
                .font(.system(size: 11)).foregroundColor(.secondary)
            if let error = store.error { Text(error).font(.callout).foregroundColor(.red) }
            Divider()
            HStack {
                Spacer()
                Button("取消") { dismiss() }.keyboardShortcut(.cancelAction)
                Button("保存提醒") {
                    if store.save(id: reminder?.id, title: title, dueAt: dueAt) { dismiss() }
                }.buttonStyle(.borderedProminent).keyboardShortcut(.defaultAction)
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !store.available)
            }
        }.padding(30).frame(width: 440).tint(green).preferredColorScheme(.light)
            .onAppear { titleFocused = true }
    }
}

/// The delivery surface is deliberately separate from both the pet and main window.
final class ReminderPanelController: NSWindowController {
    private var observation: AnyCancellable?

    init(store: ReminderStore) {
        let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: 390, height: 360),
                            styleMask: [.titled, .nonactivatingPanel], backing: .buffered, defer: false)
        panel.title = "Yukio · 到时间了"
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.hidesOnDeactivate = false
        panel.isReleasedWhenClosed = false
        panel.appearance = NSAppearance(named: .aqua)
        panel.contentView = NSHostingView(rootView: ReminderDeliveryView(store: store).frame(width: 390, height: 360))
        super.init(window: panel)
        observation = store.$book.sink { [weak self] book in
            if !book.items.contains(where: { $0.status == .ringing }) { self?.window?.orderOut(nil) }
        }
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    func present() {
        guard let window, let screen = NSScreen.main else { return }
        let frame = screen.visibleFrame
        window.setFrameOrigin(NSPoint(x: frame.maxX - window.frame.width - 24, y: frame.maxY - window.frame.height - 24))
        window.orderFrontRegardless()
    }
}

private struct ReminderDeliveryView: View {
    @ObservedObject var store: ReminderStore
    @AppStorage("assistantName") private var name = "雪绪"
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Label("\(name.isEmpty ? "雪绪" : name)来提醒你", systemImage: "bell.badge").font(.headline).foregroundColor(green)
                ForEach(store.ringing) { reminder in
                    VStack(alignment: .leading, spacing: 14) {
                        Text(reminder.title).font(.system(size: 21, weight: .medium)).fixedSize(horizontal: false, vertical: true)
                        Text(reminder.dueAt, format: .dateTime.month().day().hour().minute()).font(.caption).foregroundColor(.secondary)
                        HStack {
                            Button("稍后 5 分钟") { store.snooze(reminder.id) }
                            Spacer()
                            Button("知道了") { store.complete(reminder.id) }.buttonStyle(.borderedProminent)
                        }
                    }.padding(18).assistantCard()
                }
                if let error = store.error { Text(error).foregroundColor(.red).font(.caption) }
            }.padding(22)
        }.background(pale).tint(green).preferredColorScheme(.light)
    }
}
